# -*- coding: utf-8 -*-
"""
test_total_punches_pipeline.py
Regression & Pipeline Test for Round 7: Chronological Punch-Stream Architecture
Run: venv\Scripts\python.exe -m pytest test_total_punches_pipeline.py -v
"""

import sys
import os
from datetime import date, datetime, timedelta
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services"))
from attendance_processor import AttendanceProcessor


@pytest.fixture
def processor():
    return AttendanceProcessor()


def test_dual_sheet_ingestion(processor):
    """Test ingestion of separate Raw Data and Total Punches DataFrames."""
    df_raw = pd.DataFrame({
        "Employee ID": ["A0001", "A0001"],
        "Employee Name": ["Alice", "Alice"],
        "Gender": ["Female", "Female"],
        "Department": ["IT", "IT"],
        "Attendance Date": ["2026-07-01", "2026-07-02"],
        "Weekday": ["Wednesday", "Thursday"],
        "First Check In": ["08:00", "22:00"],
        "Last Check Out": ["17:00", "06:00"],
    })

    df_punches = pd.DataFrame({
        "Emp ID": ["A0001", "A0001"],
        "Date": ["2026-07-01", "2026-07-02"],
        "No. of Punch(s)": [2, 2],
        "Time": ["08:00, 17:00", "22:00, 06:00"]
    })

    records, cols = processor.process_dataframes(df_raw=df_raw, df_punches=df_punches)
    assert len(records) >= 2, f"Expected at least 2 output records, got {len(records)}"

    r1 = records[0]
    assert r1["employee_id"] == "A0001"
    assert r1["first_check_in"] == "08:00"
    assert r1["last_check_out"] == "17:00"
    assert r1["working_hours"] == "09:00"
    assert r1["status"] == "Present (Full Day)"

    r2 = records[1]
    assert r2["employee_id"] == "A0001"
    assert r2["first_check_in"] == "22:00"
    assert r2["c_shift_exit"] == "06:00"
    assert r2["is_overnight"] is True
    assert r2["logout_date"] == "2026-07-03"


def test_intermediate_noise_filtering(processor):
    """Test filtering of noise/intermediate break punches (< 150 min gap)."""
    df_raw = pd.DataFrame({
        "Employee ID": ["A0002"],
        "Employee Name": ["Bob"],
        "Attendance Date": ["2026-07-01"],
        "First Check In": ["21:56"],
        "Last Check Out": ["06:11"],
    })

    # Noise punch 00:19 is within 2.5 hours of 21:56
    df_punches = pd.DataFrame({
        "Emp ID": ["A0002"],
        "Date": ["2026-07-01"],
        "Time": ["21:56, 00:19, 06:11"]
    })

    records, _ = processor.process_dataframes(df_raw=df_raw, df_punches=df_punches)
    assert len(records) >= 1
    rec = records[0]
    assert rec["first_check_in"] == "21:56"
    assert rec["c_shift_exit"] == "06:11"
    assert rec["is_overnight"] is True


def test_missing_punch_out_threshold(processor):
    """Test > 18 hour gap triggering Missing Punch-Out status."""
    df_raw = pd.DataFrame({
        "Employee ID": ["A0005"],
        "Employee Name": ["Eve"],
        "Attendance Date": ["2026-07-01"],
        "First Check In": ["08:00"],
    })

    # 08:00 July 1 to 08:00 July 2 = 24 hours (> 18 hours)
    df_punches = pd.DataFrame({
        "Emp ID": ["A0005", "A0005"],
        "Date": ["2026-07-01", "2026-07-02"],
        "Time": ["08:00", "08:00"]
    })

    records, _ = processor.process_dataframes(df_raw=df_raw, df_punches=df_punches)
    assert len(records) >= 1
    rec1 = records[0]
    assert rec1["status"] in ("Needs Manual Review", "Missing Punch-Out")


def test_auto_swap_reverse_inputs(processor):
    """Test auto-swapping when df_raw and df_punches are passed in reverse."""
    df_raw = pd.DataFrame({
        "Employee ID": ["A0001"],
        "Attendance Date": ["2026-07-01"],
        "First Check In": ["08:00"],
        "Last Check Out": ["17:00"],
    })

    df_punches = pd.DataFrame({
        "Emp ID": ["A0001"],
        "Date": ["2026-07-01"],
        "Time": ["08:00, 17:00"]
    })

    # Intentionally pass df_punches into df_raw slot and df_raw into df_punches slot
    records, _ = processor.process_dataframes(df_raw=df_punches, df_punches=df_raw)
    assert len(records) == 1
    assert records[0]["working_hours"] == "09:00"


def test_employee_A0003_full_month(processor):
    """Test full month regression suite for Employee A0003 across July 2026."""
    raw_rows = []
    punch_rows = []

    # Generate July 2026 dates (31 days)
    for day in range(1, 32):
        d_str = f"2026-07-{day:02d}"
        d_obj = date(2026, 7, day)
        wday = d_obj.strftime("%A")

        if wday == "Sunday":
            # Sunday Off
            raw_rows.append({
                "Employee ID": "A0003",
                "Employee Name": "Charlie",
                "Gender": "Male",
                "Department": "Production",
                "Attendance Date": d_str,
                "Weekday": wday,
                "First Check In": None,
                "Last Check Out": None
            })
        elif day % 2 == 1:
            # Day Shift (A): 08:00 - 17:00
            raw_rows.append({
                "Employee ID": "A0003",
                "Employee Name": "Charlie",
                "Gender": "Male",
                "Department": "Production",
                "Attendance Date": d_str,
                "Weekday": wday,
                "First Check In": "08:00",
                "Last Check Out": "17:00"
            })
            punch_rows.append({
                "Emp ID": "A0003",
                "Date": d_str,
                "Time": "08:00, 17:00"
            })
        else:
            # Night Shift (C): 22:00 - 06:00
            raw_rows.append({
                "Employee ID": "A0003",
                "Employee Name": "Charlie",
                "Gender": "Male",
                "Department": "Production",
                "Attendance Date": d_str,
                "Weekday": wday,
                "First Check In": "22:00",
                "Last Check Out": None
            })
            punch_rows.append({
                "Emp ID": "A0003",
                "Date": d_str,
                "Time": "22:00, 06:00"
            })

    df_raw = pd.DataFrame(raw_rows)
    df_punches = pd.DataFrame(punch_rows)

    records, cols = processor.process_dataframes(df_raw=df_raw, df_punches=df_punches)
    assert len(records) == 31, f"Expected 31 records for July, got {len(records)}"

    present_count = sum(1 for r in records if "Present" in r["status"])
    absent_count = sum(1 for r in records if r["status"] == "Absent")

    # High match rate check (> 93.5%)
    valid_sessions = present_count + absent_count
    match_rate = valid_sessions / 31.0
    assert match_rate >= 0.935, f"Match rate {match_rate:.2%} is below 93.5% threshold"


if __name__ == "__main__":
    p = AttendanceProcessor()
    test_dual_sheet_ingestion(p)
    test_intermediate_noise_filtering(p)
    test_missing_punch_out_threshold(p)
    test_auto_swap_reverse_inputs(p)
    test_employee_A0003_full_month(p)
    print("All Round 7 tests passed successfully!")
