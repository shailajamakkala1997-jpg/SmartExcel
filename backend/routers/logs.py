from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import UploadHistory, AuditLog
from schemas import UploadHistoryResponse, AuditLogResponse

router = APIRouter(prefix="/api", tags=["Logs & Audit Trail"])

@router.get("/upload-history", response_model=List[UploadHistoryResponse])
def get_upload_history(db: Session = Depends(get_db)):
    return db.query(UploadHistory).order_by(UploadHistory.uploaded_at.desc()).all()

@router.get("/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
