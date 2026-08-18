from fastapi import APIRouter, Depends, Response, Query, Body
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from database import get_db
from models import AttendanceRecord
from services.exporter import AttendanceExporter
import csv
from io import StringIO

router = APIRouter(prefix="/api/export", tags=["Export Reports"])

def _get_filtered_records(db, employee, shift, status, department):
    query = db.query(AttendanceRecord)
    if employee:
        query = query.filter(
            (AttendanceRecord.employee_name.ilike(f"%{employee}%")) |
            (AttendanceRecord.employee_id.ilike(f"%{employee}%"))
        )
    if shift and shift != "ALL":
        query = query.filter(AttendanceRecord.shift == shift)
    if status and status != "ALL":
        query = query.filter(AttendanceRecord.status == status)
    if department and department != "ALL":
        query = query.filter(AttendanceRecord.department == department)

    return query.order_by(AttendanceRecord.attendance_date.asc(), AttendanceRecord.employee_name.asc()).all()

@router.post("/excel-direct")
def export_excel_direct(payload: Dict[str, Any] = Body(...)):
    """In-memory Excel export for direct processed records without database persistence."""
    records = payload.get("records", [])
    columns = payload.get("columns", None)
    excel_buffer = AttendanceExporter.export_to_excel(records, columns=columns)
    return Response(
        content=excel_buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Processed_Attendance_Report.xlsx"}
    )

@router.post("/excel-multisheet")
def export_excel_multisheet(payload: Dict[str, Any] = Body(...)):
    """3-sheet Excel export: Daily Detail + Monthly Summary + Manual Review."""
    records = payload.get("records", [])
    columns = payload.get("columns", None)
    excel_buffer = AttendanceExporter.export_to_excel_multisheet(records, columns=columns)
    return Response(
        content=excel_buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Attendance_Report_Full.xlsx"}
    )

@router.get("/excel")
def export_excel(
    employee: Optional[str] = None,
    shift: Optional[str] = None,
    status: Optional[str] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db)
):
    records = _get_filtered_records(db, employee, shift, status, department)
    excel_buffer = AttendanceExporter.export_to_excel(records)
    return Response(
        content=excel_buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Attendance_Report.xlsx"}
    )

@router.get("/pdf")
def export_pdf(
    employee: Optional[str] = None,
    shift: Optional[str] = None,
    status: Optional[str] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db)
):
    records = _get_filtered_records(db, employee, shift, status, department)
    pdf_buffer = AttendanceExporter.export_to_pdf(records)
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=Attendance_Report.pdf"}
    )

@router.get("/csv")
def export_csv(
    employee: Optional[str] = None,
    shift: Optional[str] = None,
    status: Optional[str] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db)
):
    records = _get_filtered_records(db, employee, shift, status, department)
    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Employee ID", "Employee Name", "Department", "Date", "Day",
        "Shift", "First Check In", "Last Check Out", "SINGLE PUNCH", "Working Hours", "Overtime Hours", "Status", "Remarks"
    ])

    for r in records:
        writer.writerow([
            r.employee_id, r.employee_name, r.department or "General",
            str(r.attendance_date), r.weekday or "", r.shift,
            r.first_check_in or "--", r.last_check_out or "--",
            getattr(r, "single_punch", "--") or "--",
            r.working_hours or "00:00", getattr(r, "overtime_hours", "00:00") or "00:00", r.status, r.remarks or ""
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=Attendance_Report.csv"}
    )
