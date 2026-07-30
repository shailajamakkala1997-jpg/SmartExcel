from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), index=True)
    employee_name = Column(String(100), index=True)
    gender = Column(String(20), nullable=True)
    department = Column(String(100), default="General", index=True)
    attendance_date = Column(Date, index=True)
    logout_date = Column(Date, nullable=True, index=True)
    weekday = Column(String(20), nullable=True)
    shift = Column(String(10), index=True)  # Shift A, B, C
    first_check_in = Column(String(10), nullable=True)
    last_check_out = Column(String(10), nullable=True)
    working_hours = Column(String(10), nullable=True)  # Format: "08:20"
    working_hours_decimal = Column(Float, default=0.0)  # Format: 8.33
    status = Column(String(50), index=True)  # Present, Missing Logout, Missing Login, Overtime, Late Login, Error
    remarks = Column(Text, nullable=True)
    is_overnight = Column(Boolean, default=False)
    upload_id = Column(Integer, ForeignKey("upload_history.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    upload = relationship("UploadHistory", back_populates="records")

class UploadHistory(Base):
    __tablename__ = "upload_history"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255))
    record_count = Column(Integer, default=0)
    processed_count = Column(Integer, default=0)
    exception_count = Column(Integer, default=0)
    uploaded_by = Column(String(100), default="Admin")
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default="Success")  # Success, Failed, Warning
    log_summary = Column(Text, nullable=True)

    records = relationship("AttendanceRecord", back_populates="upload")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(100))  # e.g., "UPLOAD_EXCEL", "EDIT_RECORD", "EXPORT_REPORT"
    entity_type = Column(String(50))  # "Attendance", "Upload"
    entity_id = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)
    performed_by = Column(String(100), default="Admin")
    timestamp = Column(DateTime, default=datetime.utcnow)
