from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

class AttendanceRecordBase(BaseModel):
    employee_id: str
    employee_name: str
    gender: Optional[str] = None
    department: Optional[str] = "General"
    attendance_date: date
    logout_date: Optional[date] = None
    weekday: Optional[str] = None
    shift: str
    first_check_in: Optional[str] = None
    last_check_out: Optional[str] = None
    single_punch: Optional[str] = "--"
    working_hours: Optional[str] = "00:00"
    working_hours_decimal: float = 0.0
    overtime_hours: Optional[str] = "00:00"
    overtime_hours_decimal: float = 0.0
    status: str
    remarks: Optional[str] = ""
    is_overnight: bool = False

class AttendanceRecordCreate(AttendanceRecordBase):
    pass

class AttendanceRecordResponse(AttendanceRecordBase):
    id: int
    upload_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

class SummaryMetrics(BaseModel):
    total_records: int
    total_employees: int
    present: int
    absent: int
    night_shift: int
    late_login: int
    missing_logout: int
    missing_login: int
    overtime: int
    invalid_hours: int
    needs_manual_review: int = 0

class ShiftBreakdown(BaseModel):
    shift_a: int
    shift_general: int = 0
    shift_b: int
    shift_b1: int = 0
    shift_c: int

class ChartDataPoint(BaseModel):
    date: str
    present: int
    late: int
    night_shift: int
    exceptions: int

class DashboardDataResponse(BaseModel):
    summary: SummaryMetrics
    shifts: ShiftBreakdown
    trends: List[ChartDataPoint]

class UploadHistoryResponse(BaseModel):
    id: int
    filename: str
    record_count: int
    processed_count: int
    exception_count: int
    uploaded_by: str
    uploaded_at: datetime
    status: str
    log_summary: Optional[str] = None

    class Config:
        from_attributes = True

class AuditLogResponse(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    details: Optional[str] = None
    performed_by: str
    timestamp: datetime

    class Config:
        from_attributes = True
