# -*- coding: utf-8 -*-
import pytest
import pandas as pd
from services.attendance_processor import AttendanceProcessor


def test_round15_summary_counts():
    """
    Test Round 15 summary stats card logic:
    - PRESENT counts all 'Present (Full Day)', 'Present (Half Day)', and 'Short Hours' rows.
    - OVERTIME counts all rows where overtime_hours > 0 or overtime_hours_decimal > 0.
    """
    processor = AttendanceProcessor()

    df_raw = pd.DataFrame({
        "Employee ID": ["A0001", "A0002", "A0003", "A0004"],
        "Employee Name": ["Alice", "Bob", "Charlie", "David"],
        "Attendance Date": ["2026-07-01", "2026-07-01", "2026-07-01", "2026-07-01"],
        "First Check In": ["09:00", "09:00", "13:54", None],
        "Last Check Out": ["17:30", "17:00", None, None]
    })

    records, _ = processor.process_dataframes(df_raw=df_raw)

    present_count = sum(1 for r in records if any(t in str(r.get("status")) for t in ["Present", "Full Day", "Half Day", "Short Hours"]))
    absent_count = sum(1 for r in records if r.get("status") == "Absent")
    manual_review_count = sum(1 for r in records if r.get("status") == "Needs Manual Review")

    assert present_count == 2, f"Expected 2 present records, got {present_count}"
    assert absent_count == 1, f"Expected 1 absent record, got {absent_count}"
    assert manual_review_count == 1, f"Expected 1 manual review record, got {manual_review_count}"
