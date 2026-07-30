from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Response
from sqlalchemy.orm import Session
import pandas as pd
from io import BytesIO
from datetime import date, datetime
from database import get_db
from models import AttendanceRecord, UploadHistory, AuditLog
from services.attendance_processor import AttendanceProcessor
from services.sample_generator import generate_sample_attendance_excel

router = APIRouter(prefix="/api", tags=["Upload & Processing"])
processor = AttendanceProcessor()

@router.post("/upload")
async def upload_attendance_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="Only .xlsx and .xls Excel files are supported")

    contents = await file.read()
    excel_file = None
    processed_records = []
    excel_columns = []
    df = None

    try:
        engine_opt = 'openpyxl' if file.filename.endswith('.xlsx') else None
        excel_file = pd.ExcelFile(BytesIO(contents), engine=engine_opt) if engine_opt else pd.ExcelFile(BytesIO(contents))
        
        # Aggregate records across all valid sheets in workbook
        for sheet_name in excel_file.sheet_names:
            sheet_df = pd.read_excel(excel_file, sheet_name=sheet_name)
            if sheet_df is not None and not sheet_df.empty:
                records, cols = processor.process_dataframe(sheet_df)
                if records:
                    processed_records.extend(records)
                    for c in cols:
                        if c not in excel_columns:
                            excel_columns.append(c)
                    if df is None:
                        df = sheet_df
        
        if df is None and len(excel_file.sheet_names) > 0:
            df = pd.read_excel(excel_file, sheet_name=excel_file.sheet_names[0])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel file: {str(e)}")

    if not processed_records:
        if df is not None and not df.empty:
            raw_cols = [str(c).strip() for c in df.columns if not str(c).startswith("Unnamed")]
            for idx, row in df.iterrows():
                rec = {}
                for col in raw_cols:
                    val = row.get(col)
                    rec[col] = str(val).strip() if (pd.notna(val) and val is not None and str(val).strip() not in ["nan", "None", "NaT"]) else ""
                
                emp_id = str(row.iloc[0]).strip() if len(row) > 0 and pd.notna(row.iloc[0]) else f"EMP{idx+1:03d}"
                emp_name = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else f"Employee_{idx+1}"
                
                rec.update({
                    "employee_id": emp_id,
                    "employee_name": emp_name,
                    "gender": "Unspecified",
                    "department": "General",
                    "attendance_date": str(date.today()),
                    "weekday": date.today().strftime("%A"),
                    "shift": "A",
                    "first_check_in": "--",
                    "last_check_out": "--",
                    "working_hours": "00:00",
                    "working_hours_decimal": 0.0,
                    "status": "Present",
                    "remarks": "Raw record",
                    "is_overnight": False
                })
                processed_records.append(rec)
            excel_columns = list(raw_cols)
            for extra in ["Shift", "Working Hours", "Status"]:
                if extra not in excel_columns:
                    excel_columns.append(extra)
        else:
            raise HTTPException(status_code=400, detail=f"The uploaded Excel sheet '{file.filename}' is empty.")

    # In-memory processing (No DB storage required)
    formatted_records = []
    for r in processed_records:
        rec_copy = {}
        for k, v in r.items():
            if isinstance(v, (date, datetime)):
                rec_copy[k] = str(v)
            elif type(v).__name__ in ('int64', 'int32', 'int16', 'int8', 'integer'):
                rec_copy[k] = int(v)
            elif type(v).__name__ in ('float64', 'float32', 'float16', 'floating'):
                rec_copy[k] = float(v)
            else:
                rec_copy[k] = v
        rec_copy["attendance_date"] = str(r.get("attendance_date", ""))
        rec_copy["logout_date"] = str(r.get("logout_date", "")) if r.get("logout_date") else ""
        formatted_records.append(rec_copy)

    # Assign clean sequential S.No (1 to N) based on final sorted order
    for i, rec in enumerate(formatted_records, start=1):
        rec["NO."] = i

    total_records = len(formatted_records)
    unique_emp_set = set()
    for r in formatted_records:
        emp_key = str(r.get("employee_id") or r.get("employee_name") or r.get("EMPLOYEE ID") or r.get("FIRST NAME") or r.get("raw_idx") or "").strip()
        if emp_key and emp_key not in ("--", "None", "nan"):
            unique_emp_set.add(emp_key)
    unique_employees = len(unique_emp_set) if unique_emp_set else total_records

    present_count = sum(1 for r in formatted_records if r.get("status") in ["Present", "Overtime", "Late Login"])
    absent_count = sum(1 for r in formatted_records if r.get("status") == "Absent")
    night_shift_count = sum(1 for r in formatted_records if r.get("shift") == "C" or r.get("is_overnight", False))
    late_login_count = sum(1 for r in formatted_records if r.get("status") == "Late Login" or "Late" in (r.get("remarks") or ""))
    missing_logout_count = sum(1 for r in formatted_records if r.get("status") == "Missing Logout")
    missing_login_count = sum(1 for r in formatted_records if r.get("status") == "Missing Login")
    overtime_count = sum(1 for r in formatted_records if r.get("status") == "Overtime" or "Overtime" in (r.get("remarks") or ""))
    invalid_hours_count = sum(1 for r in formatted_records if r.get("status") == "Invalid Hours")

    summary = {
        "total_records": total_records,
        "total_employees": unique_employees,
        "present": present_count,
        "absent": absent_count,
        "night_shift": night_shift_count,
        "late_login": late_login_count,
        "missing_logout": missing_logout_count,
        "missing_login": missing_login_count,
        "overtime": overtime_count,
        "invalid_hours": invalid_hours_count
    }

    shifts = {
        "shift_a": sum(1 for r in formatted_records if r.get("shift") == "A"),
        "shift_b": sum(1 for r in formatted_records if r.get("shift") == "B"),
        "shift_c": sum(1 for r in formatted_records if r.get("shift") == "C")
    }

    return {
        "message": "File processed in memory successfully",
        "filename": file.filename,
        "processed_count": total_records,
        "exception_count": sum(1 for r in formatted_records if r.get("status") != "Present"),
        "columns": excel_columns,
        "records": formatted_records,
        "summary": summary,
        "shifts": shifts
    }

@router.get("/generate-sample")
def download_sample_excel():
    excel_buffer = generate_sample_attendance_excel()
    return Response(
        content=excel_buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Sample_Attendance.xlsx"}
    )
