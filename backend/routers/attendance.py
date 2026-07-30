from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
from database import get_db
from models import AttendanceRecord, AuditLog, UploadHistory
from schemas import AttendanceRecordResponse

router = APIRouter(prefix="/api/attendance", tags=["Attendance Records"])

@router.get("", response_model=List[AttendanceRecordResponse])
def get_attendance_records(
    employee: Optional[str] = Query(None, description="Search employee name or ID"),
    shift: Optional[str] = Query(None, description="Filter by Shift: A, B, C"),
    status: Optional[str] = Query(None, description="Filter by Status"),
    department: Optional[str] = Query(None, description="Filter by Department"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    db: Session = Depends(get_db)
):
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
    if start_date:
        query = query.filter(AttendanceRecord.attendance_date >= start_date)
    if end_date:
        query = query.filter(AttendanceRecord.attendance_date <= end_date)

    records = query.order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.employee_name.asc()).all()
    return records

@router.put("/{record_id}", response_model=AttendanceRecordResponse)
def update_attendance_record(
    record_id: int,
    first_check_in: Optional[str] = None,
    last_check_out: Optional[str] = None,
    status: Optional[str] = None,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db)
):
    record = db.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    if first_check_in is not None:
        record.first_check_in = first_check_in
    if last_check_out is not None:
        record.last_check_out = last_check_out
    if status is not None:
        record.status = status
    if remarks is not None:
        record.remarks = remarks

    # Recalculate working hours if punches updated
    if record.first_check_in and record.last_check_out:
        from services.attendance_processor import AttendanceProcessor
        proc = AttendanceProcessor()
        wh_str, dec_hrs, is_overnight = proc.calculate_working_hours(record.first_check_in, record.last_check_out)
        record.working_hours = wh_str
        record.working_hours_decimal = dec_hrs
        record.is_overnight = is_overnight

    db.commit()
    db.refresh(record)

    # Audit log
    audit = AuditLog(
        action="UPDATE_RECORD",
        entity_type="AttendanceRecord",
        entity_id=str(record.id),
        details=f"Updated attendance for {record.employee_name} on {record.attendance_date}",
        performed_by="Admin"
    )
    db.add(audit)
    db.commit()

    return record

@router.delete("/clear-all")
def clear_all_attendance(db: Session = Depends(get_db)):
    db.query(AttendanceRecord).delete()
    db.query(UploadHistory).delete()
    db.query(AuditLog).delete()
    db.commit()
    return {"message": "All attendance records and history cleared successfully"}

@router.delete("/{record_id}")
def delete_attendance_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    db.delete(record)
    db.commit()
    return {"message": f"Record {record_id} deleted successfully"}
