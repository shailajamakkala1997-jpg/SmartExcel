from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base, SessionLocal
from models import AttendanceRecord, UploadHistory, AuditLog
from routers import upload, attendance, dashboard, export, logs
from services.sample_generator import generate_sample_attendance_excel
from services.attendance_processor import AttendanceProcessor
import pandas as pd
from io import BytesIO

# Initialize tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Smart Attendance Processing API",
    description="Automated Shift & Overnight Attendance Correction System",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(upload.router)
app.include_router(attendance.router)
app.include_router(dashboard.router)
app.include_router(export.router)
app.include_router(logs.router)

@app.on_event("startup")
def seed_sample_data_if_empty():
    """Startup tasks (auto-seeding disabled to maintain clean workspace for user data)."""
    pass

@app.get("/")
def read_root():
    return {
        "app": "Smart Attendance Excel Processing API",
        "status": "Online",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
