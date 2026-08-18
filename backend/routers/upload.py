from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Response
from sqlalchemy.orm import Session
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import date, datetime
import math
import logging
from database import get_db
from models import AttendanceRecord, UploadHistory, AuditLog
from services.attendance_processor import AttendanceProcessor
from services.sample_generator import generate_sample_attendance_excel

router = APIRouter(prefix="/api", tags=["Upload & Processing"])
processor = AttendanceProcessor()
logger = logging.getLogger("smart_excel_upload")

def sanitize_value(v):
    """Converts any value (including NaN, Inf, NaT, numpy types) to JSON-safe Python primitives."""
    if v is None:
        return ""
    if isinstance(v, (date, datetime)):
        return str(v)
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return 0.0
        return float(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (np.floating,)):
        val = float(v)
        return 0.0 if (math.isnan(val) or math.isinf(val)) else val
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    
    val_str = str(v).strip()
    if val_str.lower() in ["nan", "none", "nat", "<na>", "null", "undefined"]:
        return ""
    return val_str

from typing import Optional

@router.post("/upload")
def upload_attendance_excel(
    file: UploadFile = File(...),
    total_punches_file: Optional[UploadFile] = File(None)
):
    filename = file.filename or "uploaded_file.xlsx"
    filename_lower = filename.lower()

    # 1. Extension Validation
    valid_extensions = ('.xlsx', '.xls', '.xlsm', '.csv')
    if not any(filename_lower.endswith(ext) for ext in valid_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"File '{filename}' is not supported. Please upload an Excel (.xlsx, .xls, .xlsm) or CSV (.csv) file."
        )

    # 2. Read Main File Contents & Check Zero-Byte File
    try:
        contents = file.file.read()
    except Exception as read_err:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read uploaded file: {str(read_err)}"
        )

    if not contents or len(contents) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"The file '{filename}' is empty (0 bytes). Please upload a valid attendance file with data."
        )

    # Read optional total_punches_file if provided
    tp_contents = None
    if total_punches_file is not None and total_punches_file.filename:
        try:
            tp_contents = total_punches_file.file.read()
        except Exception as tp_read_err:
            logger.warning(f"Could not read total_punches_file: {tp_read_err}")

    processed_records = []
    excel_columns = []
    df = None

    try:
        df_raw = None
        df_punches = None

        # Parse total_punches_file if uploaded separately
        if tp_contents:
            try:
                if total_punches_file.filename.lower().endswith('.csv'):
                    df_punches = pd.read_csv(BytesIO(tp_contents))
                else:
                    tp_excel = pd.ExcelFile(BytesIO(tp_contents))
                    df_punches = pd.read_excel(tp_excel, sheet_name=0)
            except Exception as tp_err:
                logger.warning(f"Error reading total_punches_file: {tp_err}")

        # 3. CSV File Handling
        if filename_lower.endswith('.csv'):
            encodings = ['utf-8', 'latin-1', 'cp1252', 'utf-16']
            csv_df = None
            for enc in encodings:
                try:
                    csv_df = pd.read_csv(BytesIO(contents), encoding=enc, sep=None, engine='python')
                    break
                except Exception:
                    continue
            
            if csv_df is None or csv_df.empty:
                raise HTTPException(status_code=400, detail=f"Could not parse CSV file '{filename}'. Please check delimiter and encoding.")
            
            df_raw = csv_df
            records, cols = processor.process_dataframes(df_raw=df_raw, df_punches=df_punches)
            if records:
                processed_records.extend(records)
                excel_columns = cols
            df = csv_df

        # 4. Excel File Handling (.xlsx, .xls, .xlsm)
        else:
            excel_file = None
            try:
                if filename_lower.endswith('.xlsx') or filename_lower.endswith('.xlsm'):
                    try:
                        excel_file = pd.ExcelFile(BytesIO(contents), engine='openpyxl')
                    except Exception:
                        excel_file = pd.ExcelFile(BytesIO(contents))
                else:
                    try:
                        excel_file = pd.ExcelFile(BytesIO(contents), engine='xlrd')
                    except Exception:
                        excel_file = pd.ExcelFile(BytesIO(contents))
            except Exception as excel_err:
                err_msg = str(excel_err).lower()
                if "password" in err_msg or "encrypted" in err_msg:
                    raise HTTPException(status_code=400, detail="The Excel file is password protected. Please remove password protection and re-upload.")
                elif "zipfile" in err_msg or "corrupt" in err_msg or "not a valid" in err_msg:
                    raise HTTPException(status_code=400, detail="The Excel file appears to be corrupted or invalid. Please re-save as a standard .xlsx file.")
                else:
                    raise HTTPException(status_code=400, detail=f"Failed to open Excel file '{filename}': {str(excel_err)}")

            # Auto-detect sheets within single workbook (1st Sheet = Raw Data, 2nd Sheet = Total Punches)
            if excel_file and excel_file.sheet_names:
                sheet_names = excel_file.sheet_names

                # 1st sheet (Index 0) is strictly treated as Raw Data Sheet
                try:
                    df_raw = pd.read_excel(excel_file, sheet_name=0)
                except Exception as e:
                    logger.warning(f"Error reading 1st sheet '{sheet_names[0]}' as Raw Data: {e}")

                # If no separate 2nd file was provided, and workbook has a 2nd sheet (Index 1),
                # strictly treat 2nd sheet as Total Punches Sheet
                if df_punches is None and len(sheet_names) > 1:
                    try:
                        df_punches = pd.read_excel(excel_file, sheet_name=1)
                    except Exception as e:
                        logger.warning(f"Error reading 2nd sheet '{sheet_names[1]}' as Total Punches: {e}")

                records, cols = processor.process_dataframes(df_raw=df_raw, df_punches=df_punches)
                if records:
                    processed_records.extend(records)
                    excel_columns = cols
                df = df_raw if df_raw is not None else df_punches

    except HTTPException:
        raise
    except Exception as gen_err:
        raise HTTPException(
            status_code=400,
            detail=f"An unexpected error occurred while parsing '{filename}': {str(gen_err)}"
        )

    # 5. Raw Data Fallback if processor returned no records
    if not processed_records:
        if df is not None and not df.empty:
            raw_cols = [str(c).strip() for c in df.columns if not str(c).startswith("Unnamed")]
            for idx, row in df.iterrows():
                rec = {}
                for col in raw_cols:
                    val = row.get(col)
                    rec[col] = sanitize_value(val)
                
                emp_id = sanitize_value(row.iloc[0]) if len(row) > 0 else f"EMP{idx+1:03d}"
                emp_name = sanitize_value(row.iloc[1]) if len(row) > 1 else f"Employee_{idx+1}"
                if not emp_id: emp_id = f"EMP{idx+1:03d}"
                if not emp_name: emp_name = f"Employee_{idx+1}"

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
                    "overtime_hours": "00:00",
                    "overtime_hours_decimal": 0.0,
                    "status": "Present",
                    "remarks": "Raw record fallback",
                    "is_overnight": False
                })
                processed_records.append(rec)
            excel_columns = list(raw_cols)
            for extra in ["Shift", "Working Hours", "Overtime Hours", "Status"]:
                if extra not in excel_columns:
                    excel_columns.append(extra)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"No readable attendance records found in '{filename}'. Please ensure the sheet contains data."
            )

    # 6. Deep JSON Sanitization for all output records
    formatted_records = []
    for r in processed_records:
        rec_copy = {}
        for k, v in r.items():
            rec_copy[k] = sanitize_value(v)
        rec_copy["attendance_date"] = str(r.get("attendance_date", ""))
        rec_copy["logout_date"] = str(r.get("logout_date", "")) if r.get("logout_date") else ""
        formatted_records.append(rec_copy)

    # Assign sequential S.No (1 to N)
    for i, rec in enumerate(formatted_records, start=1):
        rec["NO."] = i

    total_records = len(formatted_records)
    unique_emp_set = set()
    for r in formatted_records:
        emp_key = str(r.get("employee_id") or r.get("employee_name") or r.get("EMPLOYEE ID") or r.get("FIRST NAME") or "").strip()
        if emp_key and emp_key not in ("--", "None", "nan", "0"):
            unique_emp_set.add(emp_key)
    unique_employees = len(unique_emp_set) if unique_emp_set else total_records

    present_count = sum(1 for r in formatted_records if any(term in str(r.get("status") or "") for term in ["Present", "Full Day", "Half Day", "Short Hours", "Overtime", "Late"]))
    absent_count = sum(1 for r in formatted_records if r.get("status") == "Absent")
    night_shift_count = sum(1 for r in formatted_records if r.get("shift") in ["C", "B1"] or r.get("is_overnight") is True)
    late_login_count = sum(1 for r in formatted_records if "Late" in str(r.get("status") or "") or "Late" in str(r.get("remarks") or ""))
    needs_manual_review_count = sum(1 for r in formatted_records if "manual review" in str(r.get("status") or "").lower() or "single punch" in str(r.get("status") or "").lower())
    overtime_count = sum(
        1 for r in formatted_records
        if (r.get("overtime_hours") and str(r.get("overtime_hours")).strip() not in ("00:00", "--", "0", "None", ""))
        or (r.get("overtime_hours_decimal") and float(r.get("overtime_hours_decimal") or 0) > 0)
        or (r.get("working_hours_decimal") and float(r.get("working_hours_decimal") or 0) > 8.0)
        or r.get("status") == "Overtime"
        or "Overtime" in str(r.get("remarks") or "")
    )
    invalid_hours_count = sum(1 for r in formatted_records if r.get("status") in ["Invalid Hours", "Short Hours"])

    summary = {
        "total_records": total_records,
        "total_employees": unique_employees,
        "present": present_count,
        "absent": absent_count,
        "night_shift": night_shift_count,
        "late_login": late_login_count,
        "needs_manual_review": needs_manual_review_count,
        "overtime": overtime_count,
        "invalid_hours": invalid_hours_count
    }

    shifts = {
        "shift_a": sum(1 for r in formatted_records if r.get("shift") == "A"),
        "shift_b": sum(1 for r in formatted_records if r.get("shift") == "B"),
        "shift_c": sum(1 for r in formatted_records if r.get("shift") == "C"),
        "general": sum(1 for r in formatted_records if r.get("shift") == "General"),
        "shift_b1": sum(1 for r in formatted_records if r.get("shift") == "B1")
    }

    return {
        "message": "File processed successfully",
        "filename": filename,
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
