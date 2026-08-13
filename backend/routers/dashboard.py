from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from database import get_db
from models import AttendanceRecord
from schemas import DashboardDataResponse, SummaryMetrics, ShiftBreakdown, ChartDataPoint

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard Analytics"])

@router.get("", response_model=DashboardDataResponse)
def get_dashboard_summary(db: Session = Depends(get_db)):
    records = db.query(AttendanceRecord).all()

    total_records = len(records)
    unique_employees = db.query(func.count(func.distinct(AttendanceRecord.employee_id))).scalar() or 0

    present_count = sum(1 for r in records if r.status in ["Present", "Overtime", "Late Login"])
    absent_count = sum(1 for r in records if r.status == "Absent")
    night_shift_count = sum(1 for r in records if r.shift == "C" or r.is_overnight)
    late_login_count = sum(1 for r in records if r.status == "Late Login" or "Late" in (r.remarks or ""))
    missing_logout_count = sum(1 for r in records if r.status == "Missing Logout")
    missing_login_count = sum(1 for r in records if r.status == "Missing Login")
    overtime_count = sum(
        1 for r in records
        if (r.overtime_hours and str(r.overtime_hours).strip() not in ("00:00", "--", "0", "None", ""))
        or (r.overtime_hours_decimal and float(r.overtime_hours_decimal) > 0)
        or (r.working_hours_decimal and float(r.working_hours_decimal) > 8.0)
        or r.status == "Overtime"
        or "Overtime" in (r.remarks or "")
    )
    invalid_hours_count = sum(1 for r in records if r.status == "Invalid Hours")
    needs_manual_review_count = sum(1 for r in records if "manual review" in str(r.status or "").lower() or "single punch" in str(r.status or "").lower())

    summary = SummaryMetrics(
        total_records=total_records,
        total_employees=unique_employees,
        present=present_count,
        absent=absent_count,
        night_shift=night_shift_count,
        late_login=late_login_count,
        missing_logout=missing_logout_count,
        missing_login=missing_login_count,
        overtime=overtime_count,
        invalid_hours=invalid_hours_count,
        needs_manual_review=needs_manual_review_count
    )

    # Shift Breakdown
    shift_a = sum(1 for r in records if r.shift in ("A", "1"))
    shift_general = sum(1 for r in records if r.shift in ("General", "GENERAL", "4"))
    shift_b = sum(1 for r in records if r.shift in ("B", "2"))
    shift_b1 = sum(1 for r in records if r.shift in ("B1", "5"))
    shift_c = sum(1 for r in records if r.shift in ("C", "3") or r.is_overnight)

    shifts = ShiftBreakdown(
        shift_a=shift_a,
        shift_general=shift_general,
        shift_b=shift_b,
        shift_b1=shift_b1,
        shift_c=shift_c
    )

    # Group by date for trends chart
    dates_query = db.query(
        AttendanceRecord.attendance_date,
        func.count(AttendanceRecord.id).label("total"),
        func.sum(case((AttendanceRecord.status.in_(["Present", "Overtime"]), 1), else_=0)).label("present"),
        func.sum(case((AttendanceRecord.status == "Late Login", 1), else_=0)).label("late"),
        func.sum(case((AttendanceRecord.shift == "C", 1), else_=0)).label("night_shift"),
        func.sum(case((AttendanceRecord.status.in_(["Missing Logout", "Missing Login", "Invalid Hours"]), 1), else_=0)).label("exceptions")
    ).group_by(AttendanceRecord.attendance_date).order_by(AttendanceRecord.attendance_date.asc()).all()

    trends = []
    for d in dates_query:
        trends.append(ChartDataPoint(
            date=str(d.attendance_date),
            present=d.present or 0,
            late=d.late or 0,
            night_shift=d.night_shift or 0,
            exceptions=d.exceptions or 0
        ))

    return DashboardDataResponse(
        summary=summary,
        shifts=shifts,
        trends=trends
    )
