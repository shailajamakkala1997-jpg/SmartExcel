from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base, SessionLocal
from models import AttendanceRecord, UploadHistory, AuditLog
from routers import upload, attendance, dashboard, export, logs
from services.sample_generator import generate_sample_attendance_excel
from services.attendance_processor import AttendanceProcessor
import pandas as pd
from io import BytesIO

from sqlalchemy import inspect, text

# Initialize tables & auto-migrate missing columns
Base.metadata.create_all(bind=engine)
try:
    inspector = inspect(engine)
    if "attendance_records" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("attendance_records")]
        with engine.connect() as conn:
            if "overtime_hours" not in columns:
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN overtime_hours VARCHAR(10) DEFAULT '00:00';"))
            if "overtime_hours_decimal" not in columns:
                conn.execute(text("ALTER TABLE attendance_records ADD COLUMN overtime_hours_decimal FLOAT DEFAULT 0.0;"))
            conn.commit()
except Exception as e:
    print(f"[DB MIGRATION NOTICE] {e}")

app = FastAPI(
    title="Smart Attendance Processing API",
    description="Automated Shift & Overnight Attendance Correction System",
    version="1.0.0"
)

# Enable CORS for frontend integration
cors_origins_raw = os.getenv("CORS_ORIGINS", "*")
if cors_origins_raw.strip() == "*":
    allow_origins = ["*"]
else:
    allow_origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
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
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8005))
    uvicorn.run("main:app", host=host, port=port, reload=True)
