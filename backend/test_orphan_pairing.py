# -*- coding: utf-8 -*-
# test_orphan_pairing.py - Unit tests for attendance_processor.py v2
# Run: venv\Scripts\python.exe -m pytest test_orphan_pairing.py -v

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services"))

import pytest
import pandas as pd
from datetime import date
from attendance_processor import AttendanceProcessor

@pytest.fixture
def p():
    return AttendanceProcessor()

# --- helpers ------------------------------------------------------------------
def make_df(emp_ids, names, dates, check_ins, check_outs):
    return pd.DataFrame({
        "Employee ID":    emp_ids,
        "First Name":     names,
        "Gender":         ["Female"] * len(emp_ids),
        "Date":           dates,
        "Weekday":        ["Wednesday"] * len(emp_ids),
        "First Check In": check_ins,
        "Last Check Out": check_outs,
        "Total Time":     [None] * len(emp_ids),
    })


# --- TEST 1: Shift classification ---------------------------------------------
class TestShiftClassification:
    def test_A_band_low(self, p):       assert p.determine_shift("06:00") == ("A", False, "A")
    def test_A_band_high(self, p):      assert p.determine_shift("08:59") == ("A", False, "A")
    def test_A_Gen_low(self, p):        assert p.determine_shift("09:00") == ("General", False, "General")
    def test_A_Gen_high(self, p):       assert p.determine_shift("13:59") == ("General", False, "General")
    def test_B_Gen_low(self, p):        assert p.determine_shift("14:00") == ("B", False, "B")
    def test_B_Gen_high(self, p):       assert p.determine_shift("17:29") == ("B", False, "B")
    # Same-day 17:30-20:59 = B (not B1 — B1 is only cross-midnight)
    def test_B_sameday_1730(self, p):   assert p.determine_shift("17:30") == ("B", False, "B")
    def test_B_sameday_2059(self, p):   assert p.determine_shift("20:59") == ("B", False, "B")
    # Overnight 17:30-20:59 = B1
    def test_B1_overnight(self, p):     assert p.determine_shift("18:00", logout_date=date(2026, 7, 2), login_date=date(2026, 7, 1)) == ("B1", False, "B1")
    def test_C_B1_2100(self, p):        assert p.determine_shift("21:00") == ("C", False, "C")
    def test_C_B1_2159(self, p):        assert p.determine_shift("21:59") == ("C", False, "C")
    def test_C_B1_2200(self, p):        assert p.determine_shift("22:00") == ("C", False, "C")
    def test_C_B1_night(self, p):       assert p.determine_shift("22:02") == ("C", False, "C")
    def test_C_B1_am(self, p):          assert p.determine_shift("05:29") == ("C", False, "C")
    def test_Unknown_none(self, p):     assert p.determine_shift(None)    == ("Unknown", False, "Unknown")


# --- TEST 2: Working hours -----------------------------------------------------
class TestWorkingHours:
    def test_same_day(self, p):
        s = p._compute_session("08:00", "17:00", date(2026, 7, 1))
        assert s["working_hours_str"]     == "09:00"
        assert s["working_hours_decimal"] == 9.0
        assert s["is_overnight"]          == False
        assert s["logout_date"]           == date(2026, 7, 1)

    def test_overnight_same_row(self, p):
        s = p._compute_session("22:02", "06:16", date(2026, 7, 8))
        assert s["working_hours_str"]     == "08:14"
        assert s["working_hours_decimal"] == 8.23
        assert s["is_overnight"]          == True
        assert s["logout_date"]           == date(2026, 7, 9)

    def test_missing_login(self, p):
        s = p._compute_session(None, "06:00", date(2026, 7, 1))
        assert s["working_hours_str"]     == "--"
        assert s["working_hours_decimal"] is None

    def test_missing_logout(self, p):
        s = p._compute_session("22:00", None, date(2026, 7, 1))
        assert s["working_hours_str"]     == "--"

    def test_explicit_logout_date(self, p):
        s = p._compute_session("22:00", "06:00", date(2026, 7, 1),
                                explicit_logout_date=date(2026, 7, 2))
        assert s["is_overnight"]          == True
        assert s["logout_date"]           == date(2026, 7, 2)
        assert s["working_hours_decimal"] == 8.0


# --- TEST 3: Status ------------------------------------------------------------
class TestStatus:
    def test_absent(self, p):
        st, _ = p._determine_status(None, None, None, "A", False)
        assert st == "Absent"

    def test_missing_punch_out(self, p):
        st, _ = p._determine_status("22:00", None, None, "C", False)
        assert st == "Needs Manual Review"

    def test_missing_punch_in(self, p):
        st, _ = p._determine_status(None, "06:00", None, "C", False)
        assert st == "Needs Manual Review"

    def test_full_day(self, p):
        st, _ = p._determine_status("08:00", "17:00", 9.0, "A", False)
        assert st == "Present (Full Day)"

    def test_half_day(self, p):
        st, _ = p._determine_status("08:00", "12:30", 4.5, "A", False)
        assert st == "Present (Half Day)"

    def test_short_hours(self, p):
        st, _ = p._determine_status("08:00", "10:00", 2.0, "A", False)
        assert st == "Short Hours"

    def test_ambiguous_shift_remark(self, p):
        _, rem = p._determine_status("09:30", "18:00", 8.5, "General", True)
        assert "auto-detected" in rem


# --- TEST 4: Orphan pairing ----------------------------------------------------
class TestOrphanPairing:
    def test_orphan_pair_creates_one_session(self, p):
        df = make_df(["A001","A001"], ["Alice","Alice"],
                     ["08-07-2026","09-07-2026"],
                     ["21:59", None], [None, "06:17"])
        recs, _ = p.process_dataframe(df)
        assert len(recs) == 2, f"Expected 2 records (1 Present + 1 Absent skeleton), got {len(recs)}"
        assert recs[0]["first_check_in"] == "21:59"
        assert recs[0]["last_check_out"] == "06:17"
        assert recs[0]["logout_date"]    == "2026-07-09"
        assert recs[0]["shift"]          == "C"
        assert recs[0]["shift"] not in ("B", "General")
        assert recs[0]["status"]         == "Present (Full Day)"

    def test_bug_case_self_paired_next_row_not_stolen(self, p):
        """Under shift-carry state machine, row 0 pairs with next day logout, row 1 login becomes pending single punch."""
        df = make_df(["A0003","A0003"], ["Sumithra","Sumithra"],
                     ["08-07-2026","09-07-2026"],
                     ["21:59", "21:58"], [None, "06:17"])
        recs, _ = p.process_dataframe(df)
        assert len(recs) == 2, f"Expected 2 rows, got {len(recs)}"
        recs.sort(key=lambda r: str(r["attendance_date"]))
        r0, r1 = recs[0], recs[1]
        assert r0["first_check_in"]  == "21:59"
        assert r0["last_check_out"]  == "06:17"
        assert r0["logout_date"]     == "2026-07-09"
        assert r0["status"]          == "Present (Full Day)"
        assert r1["first_check_in"]  is None
        assert r1["last_check_out"]  is None
        assert r1["single_punch"]    == "21:58"
        assert r1["SINGLE PUNCH"]    == "21:58"
        assert r1["status"]          == "Needs Manual Review"

    def test_employee_a0003_multi_day_overnight_chain(self, p):
        """Dedicated test for Employee A0003 pattern (multi-day overnight chain 22:03 -> 06:16, 22:02 -> 06:19)."""
        df = make_df(
            ["A0003", "A0003", "A0003"],
            ["Sumithra", "Sumithra", "Sumithra"],
            ["08-07-2026", "09-07-2026", "10-07-2026"],
            ["22:03", "22:02", None],
            [None, "06:16", "06:19"]
        )
        recs, _ = p.process_dataframe(df)
        assert len(recs) == 3, f"Expected 3 records (2 overnight + 1 skeleton), got {len(recs)}"
        recs.sort(key=lambda r: str(r["attendance_date"]))
        r0, r1 = recs[0], recs[1]
        assert r0["first_check_in"]  == "22:03"
        assert r0["last_check_out"]  == "06:16"
        assert r0["attendance_date"] == date(2026, 7, 8)
        assert r0["logout_date"]     == "2026-07-09"
        assert r0["status"]          == "Present (Full Day)"

        assert r1["first_check_in"]  == "22:02"
        assert r1["last_check_out"]  == "06:19"
        assert r1["attendance_date"] == date(2026, 7, 9)
        assert r1["logout_date"]     == "2026-07-10"
        assert r1["status"]          == "Present (Full Day)"

    def test_cascading_date_shift_daytime_orphan_guard(self, p):
        """
        Round 7 Fix: Punch-stream pairing is continuous across dates for Employee A0003.
        13:54 on 07-21 pairs across midnight with 06:15 on 07-22 (~16h21m double shift).
        21:56 on 07-22 pairs with 06:11 on 07-23 (~8h15m overnight).
        21:59 on 07-23 pairs with 06:18 on 07-24 (~8h19m overnight).
        """
        df = make_df(
            ["A0003", "A0003", "A0003", "A0003", "A0003"],
            ["Sumithra", "Sumithra", "Sumithra", "Sumithra", "Sumithra"],
            ["20-07-2026", "21-07-2026", "22-07-2026", "23-07-2026", "24-07-2026"],
            ["13:54", "13:54", "21:56", "21:59", None],
            ["22:15", None, "06:15", "06:11", "06:18"]
        )
        recs, _ = p.process_dataframe(df)
        assert len(recs) == 5, f"Expected 5 records, got {len(recs)}"
        recs.sort(key=lambda r: (str(r["attendance_date"]), r.get("first_check_in") or ""))

        # 2026-07-20: Self-paired B-shift (13:54 - 22:15)
        assert recs[0]["attendance_date"] == date(2026, 7, 20)
        assert recs[0]["first_check_in"] == "13:54"
        assert recs[0]["last_check_out"] == "22:15"
        assert recs[0]["status"] == "Present (Full Day)"

        # 2026-07-21: Daytime shift login (13:54) — single punch -> Needs Manual Review
        assert recs[1]["attendance_date"] == date(2026, 7, 21)
        assert recs[1]["first_check_in"] is None
        assert recs[1]["last_check_out"] is None
        assert recs[1]["single_punch"] == "13:54"
        assert recs[1]["SINGLE PUNCH"] == "13:54"
        assert recs[1]["status"] == "Needs Manual Review"

        # 2026-07-22: Self-paired C-shift overnight (21:56 - 06:15 next day)
        assert recs[2]["attendance_date"] == date(2026, 7, 22)
        assert recs[2]["first_check_in"] == "21:56"
        assert recs[2]["last_check_out"] == "06:15"
        assert recs[2]["logout_date"] == "2026-07-23"
        assert recs[2]["status"] == "Present (Full Day)"

        # 2026-07-23: Self-paired C-shift overnight (21:59 - 06:11 next day)
        assert recs[3]["attendance_date"] == date(2026, 7, 23)
        assert recs[3]["first_check_in"] == "21:59"
        assert recs[3]["last_check_out"] == "06:11"
        assert recs[3]["logout_date"] == "2026-07-24"
        assert recs[3]["status"] == "Present (Full Day)"

        # 2026-07-24: Single punch (06:18) -> Needs Manual Review
        assert recs[4]["attendance_date"] == date(2026, 7, 24)
        assert recs[4]["first_check_in"] is None
        assert recs[4]["last_check_out"] is None
        assert recs[4]["single_punch"] == "06:18"
        assert recs[4]["SINGLE PUNCH"] == "06:18"
        assert recs[4]["status"] in ("Needs Manual Review", "Missing Punch-Out")

    def test_bug1_overnight_shift_classification(self, p):
        """Assert all output rows where logout_date != login_date have shift not in ('B', 'General')."""
        df = make_df(
            ["S001", "S001", "S002", "S002"],
            ["Sam", "Sam", "Sally", "Sally"],
            ["08-07-2026", "09-07-2026", "08-07-2026", "09-07-2026"],
            ["21:59", None, "22:00", None],
            [None, "06:17", None, "06:00"]
        )
        recs, _ = p.process_dataframe(df)
        assert len(recs) == 4
        for r in recs:
            if r.get("is_overnight"):
                assert r["shift"] not in ("B", "General"), f"Overnight shift should not be B or General, got {r['shift']}"

    def test_bug2_multi_session_guard(self, p):
        """Synthetic 3-row scenario: Day D 22:00 login, Day D+1 06:00 login and 22:00 logout."""
        df = make_df(
            ["M001", "M001"],
            ["Multi", "Multi"],
            ["08-07-2026", "09-07-2026"],
            ["22:00", "06:00"],
            [None, "22:00"]
        )
        recs, _ = p.process_dataframe(df)
        assert len(recs) == 2, f"Expected 2 records, got {len(recs)}"
        recs.sort(key=lambda r: str(r["attendance_date"]))
        r_day_d, r_day_d_plus_1 = recs[0], recs[1]
        assert r_day_d["status"] == "Possible Multiple Sessions - Manual Review"
        assert r_day_d_plus_1["status"] in ("Needs Manual Review", "Missing Punch-Out")

    def test_self_paired_row(self, p):
        df = make_df(["B001"], ["Bob"], ["01-07-2026"], ["08:00"], ["17:00"])
        recs, _ = p.process_dataframe(df)
        assert len(recs) == 1
        assert recs[0]["working_hours"] == "09:00"
        assert recs[0]["status"]        == "Present (Full Day)"

    def test_absent_row(self, p):
        df = make_df(["C001"], ["Carol"], ["01-07-2026"], [None], [None])
        recs, _ = p.process_dataframe(df)
        assert len(recs) == 1
        assert recs[0]["status"] == "Absent"

    def test_orphan_checkout_no_prior_login(self, p):
        df = make_df(["F001"], ["Frank"], ["01-07-2026"], [None], ["06:00"])
        recs, _ = p.process_dataframe(df)
        assert len(recs) == 1
        assert recs[0]["status"] == "Needs Manual Review"

    def test_multi_employee_no_cross_contamination(self, p):
        df = make_df(
            ["E001","E001","E002","E002"],
            ["Eve","Eve","Dan","Dan"],
            ["01-07-2026","02-07-2026","01-07-2026","02-07-2026"],
            ["22:00", None,    "08:00", "08:00"],
            [None,    "06:00", "17:00", "17:00"],
        )
        recs, _ = p.process_dataframe(df)
        assert len(recs) == 4, f"Expected 4 rows, got {len(recs)}"
        e1 = [r for r in recs if r["employee_id"] == "E001"]
        e2 = [r for r in recs if r["employee_id"] == "E002"]
        assert len(e1) == 2 and len(e2) == 2
        assert e1[0]["first_check_in"] == "22:00"
        assert e1[0]["last_check_out"] == "06:00"
        assert e1[0]["logout_date"]    == "2026-07-02"
        assert e1[0]["shift"]          == "C"

    def test_no_orphan_checkout_emits_missing_punch_out(self, p):
        df = make_df(
            ["G001","G001"], ["Grace","Grace"],
            ["08-07-2026","09-07-2026"],
            ["21:59", "08:00"], [None, None]
        )
        recs, _ = p.process_dataframe(df)
        assert len(recs) == 2
        recs.sort(key=lambda r: str(r["attendance_date"]))
        assert recs[0]["status"] == "Needs Manual Review"
        assert recs[1]["status"] == "Needs Manual Review"


# --- TEST 5: Round 8 Date Skeleton, Shift Accuracy & Identity Integrity -----------
class TestRound8Fixes:
    def test_full_date_skeleton_coverage(self, p):
        """Bug A: Every employee is output for full global date range, zero-punch dates emitted as Absent."""
        df = pd.DataFrame({
            "Employee ID": ["E101", "E101", "E102"],
            "First Name":  ["Alice", "Alice", "Bob"],
            "Date":        ["2026-07-20", "2026-07-22", "2026-07-21"],
            "First Check In": ["09:00", "09:00", "09:00"],
            "Last Check Out": ["17:30", "17:30", "17:30"],
        })
        recs, _ = p.process_dataframe(df)
        # Global date range is 2026-07-20 to 2026-07-22 (3 days).
        # 2 employees * 3 days = 6 total records emitted.
        assert len(recs) == 6
        e101_recs = [r for r in recs if r["employee_id"] == "E101"]
        e102_recs = [r for r in recs if r["employee_id"] == "E102"]
        assert len(e101_recs) == 3
        assert len(e102_recs) == 3

        # E101 missing July 21 -> explicit Absent
        e101_july21 = [r for r in e101_recs if str(r.get("Date")) == "2026-07-21"][0]
        assert e101_july21["status"] == "Absent"

        # E102 missing July 20 and July 22 -> explicit Absent
        e102_july20 = [r for r in e102_recs if str(r.get("Date")) == "2026-07-20"][0]
        assert e102_july20["status"] == "Absent"

    def test_same_day_shift_b_disambiguation(self, p):
        """Bug C: Same-day session starting 13:55 and ending 22:14 classified as Shift B."""
        df = pd.DataFrame({
            "Employee ID": ["E201"],
            "First Name":  ["Charlie"],
            "Date":        ["2026-07-20"],
            "First Check In": ["13:55"],
            "Last Check Out": ["22:14"],
        })
        recs, _ = p.process_dataframe(df)
        assert len(recs) == 1
        assert recs[0]["shift"] == "B"

    def test_column_key_mapping_and_identity_integrity(self, p):
        """Bug B & C: Raw headers like EMPLOYEE ID, FIRST NAME, SHIFT forced onto all records, including Absent rows."""
        df = pd.DataFrame({
            "EMPLOYEE ID": ["E301", "E301"],
            "FIRST NAME":  ["David", "David"],
            "SHIFT":       ["A", "A"],
            "DATE":        ["2026-07-20", "2026-07-22"],
            "FIRST CHECK IN": ["09:00", None],
            "LAST CHECK OUT": ["17:30", None],
        })
        recs, cols = p.process_dataframe(df)
        assert len(recs) == 3  # 2026-07-20, 2026-07-21 (Absent), 2026-07-22 (Absent)
        for r in recs:
            assert r.get("EMPLOYEE ID") == "E301"
            assert r.get("FIRST NAME") == "David"
            assert r.get("SHIFT") in ("A", "General", "Unknown")
            assert r.get("SHIFT") != "" and r.get("SHIFT") != "--"


# --- TEST 6: Round 9 Break-Punch Detection (odd punch-count same-day merging) ----
class TestRound9BreakPunches:
    def test_employee_a0004_break_punch_merging(self, p):
        """
        Employee A0004 scenario:
        2026-07-26 has 3 punches: 05:53, 12:11 (break), 14:05.
        2026-07-27 has 2 punches: 05:51, 14:05.
        Should merge 07-26 to 05:53 -> 14:05 (Shift A, ~8h12m), ignoring 12:11 as break.
        07-27 should remain uncorrupted as 05:51 -> 14:05 (Shift A, ~8h14m).
        """
        df_raw = pd.DataFrame({
            "Employee ID": ["A0004", "A0004"],
            "Employee Name": ["Staff A0004", "Staff A0004"],
            "Date": ["2026-07-26", "2026-07-27"],
            "First Check In": ["05:53", "05:51"],
            "Last Check Out": ["14:05", "14:05"]
        })
        df_punches = pd.DataFrame({
            "Emp ID": ["A0004", "A0004"],
            "Date": ["2026-07-26", "2026-07-27"],
            "Time": ["05:53, 12:11, 14:05", "05:51, 14:05"]
        })

        recs, _ = p.process_dataframes(df_raw=df_raw, df_punches=df_punches)
        assert len(recs) == 2, f"Expected 2 output records, got {len(recs)}"
        recs.sort(key=lambda r: str(r["attendance_date"]))

        r26, r27 = recs[0], recs[1]

        # July 26 assertion
        assert str(r26["attendance_date"]) == "2026-07-26"
        assert r26["first_check_in"] == "05:53"
        assert r26["last_check_out"] == "14:05"
        assert r26["shift"] == "A"
        assert r26["working_hours"] in ("08:12", "08:13")
        assert "Break punch ignored: 12:11" in r26["remarks"]

        # July 27 assertion (uncorrupted!)
        assert str(r27["attendance_date"]) == "2026-07-27"
        assert r27["first_check_in"] == "05:51"
        assert r27["last_check_out"] == "14:05"
        assert r27["shift"] == "A"
        assert r27["working_hours"] in ("08:14", "08:15")

    def test_odd_punches_over_11h_falls_back(self, p):
        """Odd punches spanning > 11h (e.g. 16h) do not merge into single shift, falling back to sequential pairing."""
        df_punches = pd.DataFrame({
            "Emp ID": ["E401", "E401"],
            "Date": ["2026-07-25", "2026-07-26"],
            "Time": ["22:00", "06:15, 14:05, 22:15"]
        })
        # 22:00 on 07-25 pairs with 06:15 on 07-26 (C-shift overnight).
        # 07-26 has 14:05 and 22:15 remaining -> pairs as Shift B (14:05 -> 22:15).
        recs, _ = p.process_dataframes(df_punches=df_punches)
        b_shifts = [r for r in recs if r.get("shift") == "B" and r.get("first_check_in") == "14:05"]
        assert len(b_shifts) == 1
        assert b_shifts[0]["last_check_out"] == "22:15"


class TestRound11BoundaryOrphan:
    def test_employee_a0008_boundary_orphan_checkout(self, p):
        """Round 11: Employee A0008 starts data range on 2026-07-01 with punches 06:18 and 22:10."""
        df_raw = pd.DataFrame([
            {'EMPLOYEE ID': 'A0008', 'FIRST NAME': 'John', 'DATE': '2026-07-01', 'FIRST CHECK IN': '22:10', 'LAST CHECK OUT': '06:18'},
            {'EMPLOYEE ID': 'A0008', 'FIRST NAME': 'John', 'DATE': '2026-07-02', 'FIRST CHECK IN': '22:05', 'LAST CHECK OUT': '06:19'},
        ])
        df_punches = pd.DataFrame([
            {'Emp ID': 'A0008', 'Date': '2026-07-01', 'Time': '06:18, 22:10'},
            {'Emp ID': 'A0008', 'Date': '2026-07-02', 'Time': '06:19, 22:05'},
        ])
        recs, _ = p.process_dataframes(df_raw=df_raw, df_punches=df_punches)
        recs.sort(key=lambda r: str(r["attendance_date"]))
        r0 = recs[0]
        assert r0["attendance_date"] == date(2026, 7, 1)
        assert r0["first_check_in"] == "22:10"
        assert r0["logout_date"] == "2026-07-02"
        assert r0["c_shift_exit"] == "06:19"
        assert r0["working_hours"] == "08:09"
        assert r0["status"] == "Present (Full Day)"
        assert r0["status"] != "Possible Multiple Sessions - Manual Review"


if __name__ == "__main__":
    import traceback
    p_inst = AttendanceProcessor()
    classes = [TestShiftClassification, TestWorkingHours, TestStatus, TestOrphanPairing, TestRound8Fixes, TestRound9BreakPunches, TestRound11BoundaryOrphan]
    total = passed = 0
    for cls in classes:
        obj = cls()
        for name in sorted(dir(cls)):
            if not name.startswith("test"):
                continue
            total += 1
            try:
                getattr(obj, name)(p_inst)
                print(f"  PASS  {cls.__name__}.{name}")
                passed += 1
            except AssertionError as e:
                print(f"  FAIL  {cls.__name__}.{name}: {e}")
            except Exception:
                print(f"  ERROR {cls.__name__}.{name}:")
                traceback.print_exc()
    print(f"\n{passed}/{total} tests passed")
    sys.exit(0 if passed == total else 1)



