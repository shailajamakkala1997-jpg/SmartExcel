"""
attendance_processor.py  —  v2 (complete rewrite)

Root cause fixed
────────────────
Old code used a global skip_indices set and scanned up to 10 rows forward
for any row that had a checkout value, even self-paired rows.  This silently
deleted the next day's session by stealing its checkout.

New algorithm
─────────────
• Group rows by Employee ID, sort within each group by Date.
• Walk each employee's rows with a per-employee consumed[] boolean list
  (never shared across employees).
• An orphan login (login=value, logout=None) may ONLY be paired with a
  genuine orphan checkout row (logout=value AND login=None) that falls on
  exactly the next calendar day.  Self-paired rows (both fields present)
  are NEVER consumed by a prior row's search.
• If no genuine orphan checkout is found, the orphan login is emitted as-is
  with status "Missing Punch-Out" — it is never silently dropped.

Shift bands (5-band, no roster)
────────────────────────────────
A       : login 05:30 – 08:59
General : login 09:00 – 13:59  (auto-detected, flagged)
B       : login 14:00 – 17:29
B1      : login 17:30 – 21:59  (auto-detected, flagged)
C       : login 22:00 – 05:29 (crosses midnight)
Unknown : login is None

Configurable thresholds (edit here)
────────────────────────────────────
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta, time
import re

# ── Configurable business-rule constants ──────────────────────────────────────
FULL_DAY_HOURS  = 8.0   # >= this -> Present (Full Day)
HALF_DAY_HOURS  = 4.0   # >= this (and < FULL_DAY_HOURS) -> Present (Half Day)
ORPHAN_SEARCH_WINDOW = 3  # How many subsequent rows to scan for orphan checkout
# ─────────────────────────────────────────────────────────────────────────────


class AttendanceProcessor:
    """
    Stateless processor.  Call process_dataframe(df) -> (list[dict], list[str]).
    The returned tuple is API-compatible with the old implementation.
    """

    def __init__(self):
        self.last_diagnostics: dict = {}

    # =========================================================================
    # SECTION 1 — Low-level parsers
    # =========================================================================

    def _normalize_time_str(self, val):
        """Return 'HH:MM' string or None."""
        if val is None:
            return None
        if isinstance(val, str) and val.strip() in (
            "", "nan", "NaN", "NaT", "--", "None", "-", "N/A", "n/a"
        ):
            return None
        try:
            if pd.isna(val):
                return None
        except (TypeError, ValueError):
            pass

        if isinstance(val, (datetime, pd.Timestamp)):
            return val.strftime("%H:%M")
        if isinstance(val, time):
            return val.strftime("%H:%M")

        # Excel fraction-of-day float (0.0 ... <1.0)
        if isinstance(val, (float, int)) and not isinstance(val, bool):
            fv = float(val)
            if 0.0 <= fv < 1.0:
                total_seconds = int(round(fv * 86400))
                h = (total_seconds // 3600) % 24
                m = (total_seconds % 3600) // 60
                return f"{h:02d}:{m:02d}"

        val_str = str(val).strip()

        for fmt in (
            "%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p",
            "%I:%M%p", "%I:%M %P", "%H.%M", "%H.%M.%S", "%H%M"
        ):
            try:
                dt = datetime.strptime(val_str, fmt)
                return dt.strftime("%H:%M")
            except ValueError:
                pass

        # Embedded in a full datetime string like "2026-06-03 21:52:00"
        if " " in val_str and ":" in val_str:
            for part in val_str.split():
                if ":" in part:
                    result = self._normalize_time_str(part)
                    if result:
                        return result

        # Regex fallback
        match = re.search(r'(\d{1,2}):(\d{2})', val_str)
        if match:
            h, mn = int(match.group(1)), int(match.group(2))
            if 0 <= h < 24 and 0 <= mn < 60:
                return f"{h:02d}:{mn:02d}"

        return None

    def _normalize_date(self, val):
        """Return datetime.date or None."""
        if val is None:
            return None
        try:
            if pd.isna(val):
                return None
        except (TypeError, ValueError):
            pass

        if isinstance(val, (datetime, pd.Timestamp)):
            return val.date()
        if isinstance(val, date):
            return val

        # Excel serial number
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            fv = float(val)
            if 30000 < fv < 70000:
                return (datetime(1899, 12, 30) + timedelta(days=fv)).date()

        val_str = str(val).strip()

        # String serial float
        try:
            fv = float(val_str)
            if 30000 < fv < 70000:
                return (datetime(1899, 12, 30) + timedelta(days=fv)).date()
        except ValueError:
            pass

        # Strip time component if present
        if " " in val_str and ("-" in val_str or "/" in val_str or "." in val_str):
            val_str = val_str.split()[0]

        for fmt in (
            "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d",
            "%d.%m.%Y", "%Y.%m.%d", "%d-%b-%Y", "%d-%B-%Y", "%Y%m%d",
            "%d%m%Y", "%d-%m-%y", "%d/%m/%y", "%d.%m.%y",
            "%b %d, %Y", "%B %d, %Y",
        ):
            try:
                return datetime.strptime(val_str, fmt).date()
            except ValueError:
                pass

        try:
            dt = pd.to_datetime(val_str)
            if not pd.isna(dt):
                return dt.date()
        except Exception:
            pass

        return None

    def _safe_parse_hm(self, val):
        """Return (hour, minute) ints or (None, None)."""
        if val is None:
            return None, None
        val_str = str(val).strip()
        norm = self._normalize_time_str(val_str)
        if norm and ":" in norm:
            try:
                parts = norm.split(":")
                return int(parts[0]), int(parts[1])
            except (ValueError, IndexError):
                pass
        return None, None

    def _parse_wh_to_mins(self, val):
        """Parse any working hours value (string/float/time) into total minutes integer or None."""
        if val is None or val == '' or str(val).strip() in ('--', 'None', 'nan', 'N/A', 'n/a'):
            return None
        val_s = str(val).strip()
        if ':' in val_s:
            parts = val_s.split(':')
            try:
                return int(parts[0]) * 60 + int(parts[1])
            except Exception:
                return None
        try:
            f = float(val_s)
            if f <= 0:
                return 0
            h = int(f)
            dec_part = round((f - h) * 100)
            if 1 <= dec_part <= 59 and '.' in val_s:
                # e.g., 8.13 -> 8 hours 13 minutes
                return h * 60 + dec_part
            # e.g., 8.5 -> 8.5 hours = 510 mins
            return int(round(f * 60))
        except Exception:
            return None

    # =========================================================================
    # SECTION 2 — Column mapping
    # =========================================================================

    _ID_KW       = ["emp code", "employee code", "emp id", "employee id",
                    "emp_id", "emp_code", "staff id", "user id", "card no",
                    "badge no", "badge", "enroll id", "bio id", "staff_id", "user_id"]
    _ID_FALL_KW  = ["id", "code", "pin"]

    _NAME_KW     = ["employee name", "emp name", "staff name", "user name",
                    "full name", "emp_name", "staff_name", "user_name"]
    _FNAME_KW    = ["first name", "firstname", "first_name", "fname"]
    _LNAME_KW    = ["last name", "lastname", "last_name", "surname", "lname"]
    _NAME_FALL   = ["name", "employee", "staff", "user", "person"]

    _DATE_KW     = ["attendance date", "punch date", "log date", "shift date",
                    "work date", "atten date", "att date", "date", "dt"]

    _LOGIN_KW    = ["first check in", "first check-in", "first checkin",
                    "check in", "check-in", "checkin", "first in", "firstin",
                    "first_in", "1st in", "in time", "intime", "time in",
                    "timein", "punch in", "clock in", "start time",
                    "login", "log in", "in_time", "time_in"]
    _LOGIN_FALL  = ["in"]

    _LOGOUT_KW   = ["last check out", "last check-out", "last checkout",
                    "check out", "check-out", "checkout", "last out", "lastout",
                    "last_out", "out time", "outtime", "time out", "timeout",
                    "punch out", "clock out", "end time", "logout", "log out",
                    "out_time", "time_out"]
    _LOGOUT_FALL = ["out"]

    _GENDER_KW   = ["gender", "sex"]
    _DEPT_KW     = ["department", "dept", "section", "division", "unit", "branch"]
    _WDAY_KW     = ["weekday", "week day", "day of week", "day"]
    _SHIFT_KW    = ["shift", "shifts", "shift code", "shift name", "shift_code", "shift_name", "shift type", "shift_type", "SHIFTS", "Shifts"]

    def _col_lower(self, col):
        return str(col).strip().lower().replace("_", " ").replace("-", " ")

    def _score_header_row(self, cols):
        lowered = [self._col_lower(c) for c in cols]
        score = 0
        if any(any(k in c for k in self._ID_KW + self._ID_FALL_KW) for c in lowered):
            score += 2
        if any(any(k in c for k in self._NAME_KW + self._FNAME_KW + self._NAME_FALL) for c in lowered):
            score += 2
        if any(any(k in c for k in self._DATE_KW) for c in lowered):
            score += 2
        if any(any(k in c for k in self._LOGIN_KW + self._LOGIN_FALL) for c in lowered):
            score += 2
        if any(any(k in c for k in self._LOGOUT_KW + self._LOGOUT_FALL) for c in lowered):
            score += 2
        return score

    def _auto_detect_header_and_map(self, df):
        """
        Locate the real header row within the first 15 rows and build a
        canonical col_map: role -> actual column name in df.
        """
        working = df.copy()
        best_score = self._score_header_row(list(working.columns))
        header_row_idx = -1

        for r in range(min(15, len(working))):
            s = self._score_header_row(working.iloc[r].tolist())
            if s > best_score:
                best_score = s
                header_row_idx = r

        if header_row_idx >= 0:
            new_cols = [
                str(c).strip() if not (isinstance(c, float) and pd.isna(c)) else f"Unnamed_{i}"
                for i, c in enumerate(working.iloc[header_row_idx])
            ]
            working = working.iloc[header_row_idx + 1:].reset_index(drop=True)
            working.columns = new_cols

        columns = list(working.columns)
        used = set()

        def match(primary_kws, fallback_kws=None):
            all_kw_lists = [primary_kws]
            if fallback_kws:
                all_kw_lists.append(fallback_kws)
            for kw_list in all_kw_lists:
                for kw in kw_list:
                    for col in columns:
                        if col in used:
                            continue
                        cl = self._col_lower(col)
                        words = set(re.findall(r'\w+', cl))
                        if " " in kw:
                            if kw in cl:
                                used.add(col)
                                return col
                        else:
                            if kw in words or cl == kw:
                                used.add(col)
                                return col
            return None

        col_map = {}
        col_map["id"]         = match(self._ID_KW, self._ID_FALL_KW)
        col_map["name"]       = match(self._NAME_KW)
        col_map["first_name"] = match(self._FNAME_KW)
        col_map["last_name"]  = match(self._LNAME_KW)
        if not col_map.get("name"):
            col_map["name"] = col_map.get("first_name") or match(self._NAME_FALL)
        col_map["date"]    = match(self._DATE_KW)
        col_map["login"]   = match(self._LOGIN_KW, self._LOGIN_FALL)
        col_map["logout"]  = match(self._LOGOUT_KW, self._LOGOUT_FALL)
        col_map["gender"]  = match(self._GENDER_KW)
        col_map["dept"]    = match(self._DEPT_KW)
        col_map["weekday"] = match(self._WDAY_KW)
        col_map["shift"]   = match(self._SHIFT_KW)

        # Positional fallback: detect unmapped time-like / date-like columns
        if len(working) > 0:
            sample = working.head(10)
            for col in columns:
                if col in used or str(col).startswith("Unnamed"):
                    continue
                vals = [
                    str(v).strip() for v in sample[col].dropna()
                    if str(v).strip() not in ("", "nan", "None", "NaT")
                ]
                if not vals:
                    continue
                time_hits = sum(1 for v in vals if self._normalize_time_str(v) is not None)
                if time_hits >= max(1, len(vals) * 0.4):
                    if not col_map.get("login"):
                        col_map["login"] = col
                        used.add(col)
                    elif not col_map.get("logout"):
                        col_map["logout"] = col
                        used.add(col)
                    continue
                date_hits = sum(1 for v in vals if self._normalize_date(v) is not None)
                if date_hits >= max(1, len(vals) * 0.4):
                    if not col_map.get("date"):
                        col_map["date"] = col
                        used.add(col)

        col_map = {k: v for k, v in col_map.items() if v is not None}
        return working, col_map

    # =========================================================================
    # SECTION 3 — Shift classification (5-band with 4 overlap zones)
    # =========================================================================

    def determine_shift(self, login_time_str, logout_date=None, login_date=None, logout_time_str=None, emp_id=None, raw_shift=None):
        """
        Returns (primary_shift: str, is_ambiguous: bool, overlap_label: str).

        Confirmed shift definitions (user-facing timings):
          - A       : Login 06:00 – 08:59 (day shift, ends ~14:00)
          - General : Login 09:00 – 13:59 (office shift, ends ~17:30)
          - B       : Login 14:00 – 20:59 same-day (evening shift, ends ~22:00)
          - B1      : Login 17:30 – 20:59 ONLY when session crosses midnight (overnight, ends ~06:00)
          - C       : Login >= 21:00 or overnight-crossing with login < 17:30 (night shift)
        """
        if raw_shift is not None and str(raw_shift).strip() not in ("", "nan", "None", "NaT"):
            rs = str(raw_shift).strip().upper()
            if rs.endswith(".0"):
                rs = rs[:-2]
            if rs in ("1", "A"):
                return ("A", False, "A")
            elif rs in ("2", "B"):
                return ("B", False, "B")
            elif rs in ("3", "C", "NIGHT"):
                return ("C", False, "C")
            elif rs in ("4", "GENERAL", "GEN", "G"):
                return ("General", False, "General")
            elif rs in ("5", "B1"):
                return ("B1", False, "B1")

        if not login_time_str:
            return ("Unknown", False, "Unknown")

        h, m = self._safe_parse_hm(login_time_str)
        if h is None:
            return ("Unknown", False, "Unknown")

        total = h * 60 + m
        is_overnight = (logout_date is not None and login_date is not None and logout_date != login_date)

        # Midnight-crossing session signal
        if is_overnight:
            if 1050 <= total < 1260:  # 17:30 – 20:59 crossing midnight → B1
                return ("B1", False, "B1")
            else:                     # < 17:30 or >= 21:00 crossing midnight → C
                return ("C", False, "C")

        # Same-day session classification based on login time:
        if 330 <= total < 540:          # 05:30 – 08:59 (Shift A day shift)
            return ("A", False, "A")
        elif 540 <= total < 840:        # 09:00 – 13:59 (General shift)
            # Round 8 checkout cross-check: if same-day logout is well past 20:00 (1200 mins), reclassify as B
            if logout_time_str:
                oh, om = self._safe_parse_hm(logout_time_str)
                if oh is not None and (oh * 60 + om) >= 1200:
                    return ("B", True, "General/B")
            return ("General", False, "General")
        elif 840 <= total < 1260:       # 14:00 – 20:59 same-day → Shift B
            # B1 only applies when crossing midnight; same-day late evening stays as B
            return ("B", False, "B")
        else:                           # >= 21:00 or < 05:30 (Shift C night shift)
            return ("C", False, "C")

    def is_night_shift_start(self, login_time_str) -> bool:
        """
        Returns True if login_time_str represents a login that may produce an overnight-crossing session.
        Login >= 17:30 (B1 territory) or early AM < 05:30 could cross midnight.
        Daytime shifts (A, General, B starting < 17:30) return False.
        """
        if not login_time_str:
            return False
        h, m = self._safe_parse_hm(login_time_str)
        if h is None:
            return False
        mins = h * 60 + m
        return mins >= 1050 or mins < 330

    # =========================================================================
    # SECTION 4 — Working hours & logout date computation
    # =========================================================================

    def _compute_session(self, login_str, logout_str, login_date, explicit_logout_date=None):
        """
        Returns dict with keys:
          working_hours_str, working_hours_decimal, is_overnight, logout_date
        """
        empty = {
            "working_hours_str":     "--",
            "working_hours_decimal": None,
            "overtime_hours_str":    "00:00",
            "overtime_hours_decimal": 0.0,
            "is_overnight":          False,
            "logout_date":           None,
        }

        if not login_str or not logout_str:
            return empty

        lh, lm = self._safe_parse_hm(login_str)
        oh, om = self._safe_parse_hm(logout_str)

        if lh is None or oh is None:
            return empty

        login_mins  = lh * 60 + lm
        logout_mins = oh * 60 + om
        is_overnight = False

        if explicit_logout_date is not None:
            # Cross-row pairing: logout date is already known exactly
            logout_date = explicit_logout_date
            if logout_date > login_date:
                logout_mins += 24 * 60
                is_overnight = True
        else:
            if logout_mins < login_mins:
                # Same-row overnight (device already paired login + next-morning logout)
                logout_mins += 24 * 60
                is_overnight = True
                logout_date = login_date + timedelta(days=1)
            else:
                logout_date = login_date

        diff_mins = logout_mins - login_mins
        hours = diff_mins // 60
        mins  = diff_mins % 60
        decimal = round(diff_mins / 60.0, 2)

        # Overtime computation: 8.0 hours = 480 minutes
        if diff_mins > 480:
            ot_mins = diff_mins - 480
            ot_h = ot_mins // 60
            ot_m = ot_mins % 60
            ot_str = f"{ot_h:02d}:{ot_m:02d}"
            ot_decimal = round(ot_mins / 60.0, 2)
        else:
            ot_str = "00:00"
            ot_decimal = 0.0

        return {
            "working_hours_str":     f"{hours:02d}:{mins:02d}",
            "working_hours_decimal": decimal,
            "overtime_hours_str":    ot_str,
            "overtime_hours_decimal": ot_decimal,
            "is_overnight":          is_overnight,
            "logout_date":           logout_date,
        }

    def calculate_working_hours(self, login_str, logout_str):
        """Helper to calculate working hours & overtime hours for punch updates."""
        session = self._compute_session(login_str, logout_str, date.today())
        return (
            session["working_hours_str"],
            session["working_hours_decimal"],
            session["is_overnight"],
            session["overtime_hours_str"],
            session["overtime_hours_decimal"]
        )

    # =========================================================================
    # SECTION 5 — Status determination
    # =========================================================================

    def _determine_status(self, login_str, logout_str, hours, shift, is_ambiguous_shift, overlap_label="", has_prior_orphan=False):
        """Returns (status: str, remarks: str)."""
        remarks_parts = []

        if login_str is None and logout_str is None:
            return "Absent", "No punch recorded"

        if (login_str is not None and logout_str is None) or (login_str is None and logout_str is not None):
            status = "Needs Manual Review"
            remarks_parts.append("Single punch recorded — manual review required")
            return status, "; ".join(remarks_parts)
        elif hours is None:
            status = "Invalid Hours"
            remarks_parts.append("Could not compute working hours")
            return status, "; ".join(remarks_parts)

        # Check for multi-session collapse / implausible duration
        lh, lm = self._safe_parse_hm(login_str)
        login_m = (lh * 60 + lm) if lh is not None else None
        oh, om = self._safe_parse_hm(logout_str)
        logout_m = (oh * 60 + om) if oh is not None else None
        is_morning_window = ((login_m is not None and 300 <= login_m <= 480) or (logout_m is not None and 300 <= logout_m <= 480))

        if hours > 12.0 or (is_morning_window and has_prior_orphan):
            status = "Possible Multiple Sessions - Manual Review"
            remarks_parts.append(f"Multi-session overlap/implausible duration ({hours:.2f}h) — manual review required")
            if is_ambiguous_shift and shift not in ("Unknown",):
                remarks_parts.append(f"Shift {shift} auto-detected ({overlap_label} overlap) — verify with roster")
            return status, "; ".join(remarks_parts)

        if hours >= FULL_DAY_HOURS:
            status = "Present (Full Day)"
        elif hours >= HALF_DAY_HOURS:
            status = "Present (Half Day)"
        else:
            status = "Short Hours"
            remarks_parts.append(f"Only {hours:.2f}h recorded")

        if is_ambiguous_shift and shift not in ("Unknown",):
            remarks_parts.append(f"Shift {shift} auto-detected ({overlap_label} overlap) — verify with roster")

        # Late check-in detection
        if login_str is not None and lh is not None:
            late = False
            if shift == "A"         and login_m > (6  * 60 + 15):
                late = True
            elif shift == "General" and login_m > (9  * 60 + 15):
                late = True
            elif shift == "B"       and login_m > (14 * 60 + 15):
                late = True
            elif shift == "B1"      and login_m > (17 * 60 + 45):
                late = True
            elif shift == "C"       and (login_m > (22 * 60 + 15)):
                late = True
            if late:
                remarks_parts.append(f"Late Check-in (Shift {shift})")

        remarks = "; ".join(remarks_parts) if remarks_parts else "Normal Attendance"
        return status, remarks

    # =========================================================================
    # SECTION 6 — Main entry point
    # =========================================================================

    def _emp_sort_key(self, eid):
        try:
            return (0, int(eid))
        except (ValueError, TypeError):
            return (1, str(eid).lower())

    def _extract_raw_rows(self, df, col_map, raw_headers):
        time_cols = {col_map[r] for r in ("login", "logout") if r in col_map}
        date_cols = {col_map["date"]} if "date" in col_map else set()

        def _raw_cell(col, val):
            if val is None:
                return ""
            try:
                if pd.isna(val):
                    return ""
            except (TypeError, ValueError):
                pass
            if str(val).strip() in ("nan", "None", "NaT", ""):
                return ""
            if col in time_cols:
                t = self._normalize_time_str(val)
                return t if t else str(val).strip()
            if col in date_cols:
                d = self._normalize_date(val)
                return d.strftime("%Y-%m-%d") if d else str(val).strip()
            if isinstance(val, (datetime, pd.Timestamp)):
                return val.strftime("%Y-%m-%d %H:%M")
            if isinstance(val, date):
                return val.strftime("%Y-%m-%d")
            if isinstance(val, float):
                if 0.0 <= val < 1.0:
                    t = self._normalize_time_str(val)
                    return t if t else str(val)
                return str(int(val)) if val == int(val) else str(val)
            return str(val).strip()

        raw_rows = []
        for idx, row in df.iterrows():
            raw_id = row.get(col_map["id"]) if "id" in col_map else None
            if raw_id is not None:
                try:
                    is_na = pd.isna(raw_id)
                except (TypeError, ValueError):
                    is_na = False
                if not is_na and str(raw_id).strip() not in ("", "nan", "None", "NaT"):
                    if isinstance(raw_id, float) and raw_id == int(raw_id):
                        emp_id = str(int(raw_id))
                    else:
                        emp_id = str(raw_id).strip()
                else:
                    emp_id = f"EMP_{idx+1:03d}"
            else:
                emp_id = f"EMP_{idx+1:03d}"

            if emp_id.startswith("EMP_"):
                has_any = any(
                    str(row.get(col_map.get(k, ""), "")).strip() not in ("", "nan", "None", "NaT")
                    for k in ("name", "login", "logout", "date")
                    if k in col_map
                )
                if not has_any:
                    continue

            raw_name = row.get(col_map["name"]) if "name" in col_map else None
            first_v  = row.get(col_map["first_name"]) if "first_name" in col_map else None
            last_v   = row.get(col_map["last_name"])  if "last_name"  in col_map else None

            def _str_clean(v):
                if v is None:
                    return ""
                try:
                    if pd.isna(v):
                        return ""
                except (TypeError, ValueError):
                    pass
                s = str(v).strip()
                return "" if s in ("nan", "None", "NaT") else s

            raw_name_s = _str_clean(raw_name)
            first_s    = _str_clean(first_v)
            last_s     = _str_clean(last_v)

            if raw_name_s:
                emp_name = raw_name_s
                if (col_map.get("first_name") == col_map.get("name")) and last_s:
                    emp_name = f"{emp_name} {last_s}"
            elif first_s or last_s:
                emp_name = f"{first_s} {last_s}".strip() or f"Employee_{idx+1}"
            else:
                emp_name = f"Employee_{idx+1}"

            raw_date = self._normalize_date(row.get(col_map["date"])) if "date" in col_map else None
            if raw_date is None:
                for role in ("login", "logout"):
                    if role in col_map:
                        raw_date = self._normalize_date(row.get(col_map[role]))
                        if raw_date:
                            break
            if raw_date is None:
                raw_date = date.today()

            login_time  = self._normalize_time_str(row.get(col_map["login"]))  if "login"  in col_map else None
            logout_time = self._normalize_time_str(row.get(col_map["logout"])) if "logout" in col_map else None

            gender_raw  = row.get(col_map["gender"])  if "gender"  in col_map else None
            dept_raw    = row.get(col_map["dept"])    if "dept"    in col_map else None
            wday_raw    = row.get(col_map["weekday"]) if "weekday" in col_map else None

            gender  = _str_clean(gender_raw) or "Unspecified"
            dept    = _str_clean(dept_raw)   or "General"
            weekday = _str_clean(wday_raw)   or raw_date.strftime("%A")

            raw_cell_data = {col: _raw_cell(col, row.get(col)) for col in raw_headers}

            raw_rows.append({
                "emp_id":        emp_id,
                "emp_name":      emp_name,
                "gender":        gender,
                "dept":          dept,
                "date":          raw_date,
                "weekday":       weekday,
                "login":         login_time,
                "logout":        logout_time,
                "raw_cell_data": raw_cell_data,
                "raw_idx":       int(idx),
            })
        return raw_rows

    def _extract_total_punches(self, df_tp, col_map, source_name="total_punches sheet"):
        punches_by_emp = {}
        for idx, row in df_tp.iterrows():
            raw_id = row.get(col_map.get("id")) if "id" in col_map else None
            if raw_id is None or pd.isna(raw_id) or str(raw_id).strip() in ("", "nan", "None"):
                continue
            if isinstance(raw_id, float) and raw_id == int(raw_id):
                emp_id = str(int(raw_id))
            else:
                emp_id = str(raw_id).strip()

            raw_date = self._normalize_date(row.get(col_map.get("date"))) if "date" in col_map else None
            if raw_date is None:
                continue

            candidate_cols = []
            for col_name in df_tp.columns:
                c_clean = str(col_name).lower().strip()
                if ("time" in c_clean or "punch" in c_clean or "log" in c_clean) and not ("no." in c_clean or "count" in c_clean or "num" in c_clean or "total" == c_clean):
                    candidate_cols.append(col_name)

            if not candidate_cols:
                candidate_cols = [c for c in df_tp.columns if c not in (col_map.get("id"), col_map.get("date"))]

            for col_name in candidate_cols:
                time_val = row.get(col_name)
                if time_val is None or pd.isna(time_val):
                    continue
                time_str = str(time_val).strip()
                if not time_str or time_str.lower() in ("nan", "none", "nat", "--"):
                    continue

                if str(emp_id).upper() == "A0004":
                    print(f"[PARSE PUNCHES DEBUG] Reading from {source_name} | emp_id={emp_id} | date={raw_date} | raw_cell_value='{time_str}'")

                parts = time_str.split(",") if "," in time_str else [time_str]
                row_punches = []
                curr_date = raw_date
                last_mins = None
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    t_norm = self._normalize_time_str(part)
                    if t_norm and ":" in t_norm:
                        h, m = self._safe_parse_hm(t_norm)
                        if h is not None:
                            curr_mins = h * 60 + m
                            if last_mins is not None and curr_mins < last_mins:
                                curr_date = curr_date + timedelta(days=1)
                            last_mins = curr_mins
                            dt = datetime(curr_date.year, curr_date.month, curr_date.day, h, m)
                            row_punches.append(dt)
                if row_punches:
                    for dt in row_punches:
                        punches_by_emp.setdefault(emp_id, []).append({
                            "dt": dt, "kind": "stream", "base_row": None
                        })
                    break

        return punches_by_emp

    def _extract_punches_from_raw_rows(self, raw_rows):
        punches_by_emp = {}
        for r in raw_rows:
            emp_id = r["emp_id"]
            r_date = r["date"]
            lin = r["login"]
            lout = r["logout"]

            if str(emp_id).upper() == "A0004":
                print(f"[PARSE PUNCHES DEBUG] Reading from RAW_DATA login/logout columns | emp_id={emp_id} | date={r_date} | raw_login='{lin}' | raw_logout='{lout}'")

            if lin:
                lh, lm = self._safe_parse_hm(lin)
                if lh is not None:
                    dtin = datetime(r_date.year, r_date.month, r_date.day, lh, lm)
                    punches_by_emp.setdefault(emp_id, []).append({
                        "dt": dtin, "kind": "in", "base_row": r
                    })

            if lout:
                oh, om = self._safe_parse_hm(lout)
                if oh is not None:
                    dtout = datetime(r_date.year, r_date.month, r_date.day, oh, om)
                    punches_by_emp.setdefault(emp_id, []).append({
                        "dt": dtout, "kind": "out", "base_row": r
                    })
        return punches_by_emp

    def _build_record_from_session(
        self, emp_id, emp_name, gender, dept, r_date,
        login_val, logout_val, is_overnight, logout_date_obj,
        base_row, global_stats, raw_headers, col_map_raw,
        has_prior_orphan=False, session_obj=None
    ):
        raw_shift = None
        if base_row:
            raw_shift = base_row.get("shift")
            if not raw_shift and "raw_cell_data" in base_row:
                rcd = base_row["raw_cell_data"]
                raw_shift = rcd.get("SHIFTS") or rcd.get("Shift") or rcd.get("shifts") or rcd.get("SHIFT")

        explicit_logout_date = logout_date_obj if is_overnight and logout_date_obj else None

        session = self._compute_session(login_val, logout_val, r_date, explicit_logout_date)
        shift, is_amb, label = self.determine_shift(
            login_val, logout_date=session["logout_date"], login_date=r_date, logout_time_str=logout_val, raw_shift=raw_shift
        )
        st, rem = self._determine_status(login_val, logout_val, session["working_hours_decimal"], shift, is_amb, label, has_prior_orphan=has_prior_orphan)

        if st == "Needs Manual Review":
            shift = "Unknown"
            single_punch_val = login_val or logout_val
            login_val = None
            logout_val = None
        else:
            single_punch_val = None

        if session_obj and session_obj.get("ignored_breaks"):
            break_str = f"Break punch ignored: {', '.join(session_obj['ignored_breaks'])}"
            if rem in ("Normal Attendance", ""):
                rem = break_str
            else:
                rem = f"{rem}; {break_str}"

        kind = "same_day" if (login_val and logout_val and not is_overnight) else (
            "overnight_chained" if is_overnight else (
                "missing_out" if (login_val or single_punch_val) else "absent"
            )
        )
        if kind in global_stats:
            global_stats[kind] += 1

        return self._build_record_dict(
            base_row, emp_id, emp_name, gender, dept, r_date,
            login_val, logout_val, session["logout_date"],
            session["working_hours_str"] if st != "Needs Manual Review" else "--",
            session["working_hours_decimal"] if st != "Needs Manual Review" else None,
            session["is_overnight"], shift, st, rem, raw_headers, col_map_raw,
            overtime_hours_str=session.get("overtime_hours_str", "00:00") if st != "Needs Manual Review" else "00:00",
            overtime_hours_decimal=session.get("overtime_hours_decimal", 0.0) if st != "Needs Manual Review" else 0.0,
            session_obj=session_obj,
            single_punch_val=single_punch_val
        )

    def _build_record_dict(
        self, base_row, emp_id, emp_name, gender, dept, r_date,
        login_val, logout_val, logout_date_obj,
        working_hours_str, working_hours_decimal,
        is_overnight, shift, status, remarks,
        raw_headers, col_map_raw,
        overtime_hours_str="00:00", overtime_hours_decimal=0.0,
        session_obj=None, single_punch_val=None
    ):
        import logging
        if not emp_id or str(emp_id).strip() in ("", "--", "None", "nan"):
            logging.error(f"[DATA INTEGRITY ERROR] Record emitted with blank employee_id for date {r_date}!")
            emp_id = str(emp_id).strip() if emp_id else "EMP_UNKNOWN"
        if not emp_name or str(emp_name).strip() in ("", "--", "None", "nan"):
            emp_name = f"Employee_{emp_id}"

        if status == "Needs Manual Review":
            if not single_punch_val:
                single_punch_val = login_val or logout_val
            login_val = None
            logout_val = None
            shift = "Unknown"
            single_punch_display = single_punch_val or "--"
        else:
            single_punch_display = "--"

        if base_row and "raw_cell_data" in base_row:
            rec = dict(base_row["raw_cell_data"])
        else:
            rec = {}

        for h in (raw_headers or []):
            if h not in rec:
                rec[h] = ""

        date_str = r_date.strftime("%Y-%m-%d") if isinstance(r_date, (date, datetime)) else str(r_date)
        logout_date_str = logout_date_obj.strftime("%Y-%m-%d") if logout_date_obj else "--"

        # Overtime Fallback: only for records that DO have valid working hours
        # Single punch (Needs Manual Review) records have no valid pair so skip entirely
        if status != "Needs Manual Review" and overtime_hours_str in ("00:00", "", "--", None):
            wh_cand = working_hours_str or rec.get("working_hours") or rec.get("Working Hours") or rec.get("WORKING HOURS") or rec.get("totaltime") or rec.get("TOTAL TIME") or rec.get("Total Hours")
            mins = self._parse_wh_to_mins(wh_cand)
            if mins is not None and mins > 480:
                ot_m = mins - 480
                ot_h = ot_m // 60
                ot_mn = ot_m % 60
                overtime_hours_str = f"{ot_h:02d}:{ot_mn:02d}"
                overtime_hours_decimal = round(ot_m / 60.0, 2)

        # Dynamically sync any raw cell keys that match core metadata roles
        for col_name in list(rec.keys()):
            col_clean = str(col_name).lower().strip().replace("_", "").replace(".", "").replace(" ", "").replace("-", "")
            if col_clean in ("empid", "employeeid", "empcode", "staffid", "userid", "id", "code", "badgeno", "badge", "cardno", "enrollid"):
                rec[col_name] = emp_id
            elif col_clean in ("employeename", "empname", "firstname", "first_name", "fname", "lastname", "last_name", "lname", "name", "staffname", "username", "fullname"):
                rec[col_name] = emp_name
            elif col_clean in ("gender", "sex"):
                rec[col_name] = gender
            elif col_clean in ("department", "dept", "section", "division", "unit"):
                rec[col_name] = dept
            elif col_clean in ("shift", "shifts", "shiftcode", "shiftname", "shifttype"):
                rec[col_name] = shift
            elif col_clean in ("logoutdate", "checkoutdate", "lastcheckoutdate"):
                rec[col_name] = logout_date_str
            elif col_clean in ("totaltime", "totalhours", "totalhrs", "workinghours"):
                # Always push the computed working_hours_str outward.
                # For NMR/single-punch records, working_hours_str is "--" and we must NOT
                # read back the raw Excel pre-filled value — that would produce bogus hours.
                if status == "Needs Manual Review":
                    rec[col_name] = "--"  # hard guard: never show raw Excel WH for single punch
                elif working_hours_str not in ("--", None, ""):
                    rec[col_name] = working_hours_str
                else:
                    # No computed value yet: attempt to read from raw cell (valid pair records only)
                    raw_wh = rec.get(col_name)
                    if raw_wh not in ("--", None, ""):
                        working_hours_str = str(raw_wh).strip()
                        mins_cand = self._parse_wh_to_mins(working_hours_str)
                        if mins_cand is not None:
                            working_hours_decimal = round(mins_cand / 60.0, 2)
            elif col_clean in ("overtimehours", "overtime", "othours", "ot"):
                rec[col_name] = overtime_hours_str
            elif col_clean in ("firstcheckin", "checkin", "intime", "login", "firstin", "timein", "clockin", "starttime"):
                rec[col_name] = login_val or "--"
            elif col_clean in ("lastcheckout", "checkout", "outtime", "logout", "lastout", "timeout", "clockout", "endtime"):
                rec[col_name] = logout_val or "--"
            elif col_clean in ("singlepunch", "singlepunchtime", "singlecheckin", "singlecheckout", "unpairedpunch"):
                rec[col_name] = single_punch_display
            elif col_clean in ("date", "attendancedate", "punchdate", "logdate", "shiftdate", "workdate", "attendate", "attdate", "dt"):
                rec[col_name] = date_str
            elif col_clean in ("status", "attenstatus"):
                rec[col_name] = status
            elif col_clean in ("remarks", "remark"):
                rec[col_name] = remarks
            elif col_clean in ("missingshiftdetails", "shiftdetails", "breakpunch", "breakpunches"):
                if session_obj and session_obj.get("ignored_breaks"):
                    rec[col_name] = f"Break punch ignored: {', '.join(session_obj['ignored_breaks'])}"

        # Synchronize mapped column header roles if detected
        if col_map_raw.get("id"):         rec[col_map_raw["id"]] = emp_id
        if col_map_raw.get("name"):       rec[col_map_raw["name"]] = emp_name
        if col_map_raw.get("first_name"): rec[col_map_raw["first_name"]] = emp_name
        if col_map_raw.get("last_name"):  rec[col_map_raw["last_name"]] = emp_name
        if col_map_raw.get("login"):      rec[col_map_raw["login"]] = login_val or "--"
        if col_map_raw.get("logout"):     rec[col_map_raw["logout"]] = logout_val or "--"
        if col_map_raw.get("shift"):      rec[col_map_raw["shift"]] = shift
        if col_map_raw.get("gender"):     rec[col_map_raw["gender"]] = gender
        if col_map_raw.get("dept"):       rec[col_map_raw["dept"]] = dept
        if col_map_raw.get("date"):       rec[col_map_raw["date"]] = date_str

        weekday_val = base_row["weekday"] if (base_row and "weekday" in base_row) else r_date.strftime("%A")

        if status == "Needs Manual Review":
            punch_status = "Single punch — manual review needed"
        elif status == "Absent":
            punch_status = "No Punch"
        elif is_overnight:
            punch_status = "Overnight Chained"
        elif session_obj and session_obj.get("ignored_breaks"):
            punch_status = f"Break punch ignored ({', '.join(session_obj['ignored_breaks'])})"
        else:
            punch_status = "Normal"

        rec.update({
            "raw_idx":                base_row["raw_idx"] if base_row else 0,
            "employee_id":            emp_id,
            "Employee ID":            emp_id,
            "Emp ID":                 emp_id,
            "EMP ID":                 emp_id,
            "employee_name":          emp_name,
            "Employee Name":          emp_name,
            "FIRST NAME":             emp_name,
            "First Name":             emp_name,
            "gender":                 gender,
            "Gender":                 gender,
            "GENDER":                 gender,
            "department":             dept,
            "Department":             dept,
            "DEPARTMENT":             dept,
            "attendance_date":        r_date,
            "Date":                   date_str,
            "DATE":                   date_str,
            "weekday":                weekday_val,
            "WEEKDAY":                weekday_val,
            "shift":                  shift,
            "Shift":                  shift,
            "SHIFT":                  shift,
            "shifts":                 shift,
            "Shifts":                 shift,
            "SHIFTS":                 shift,
            "first_check_in":         login_val,
            "FIRST CHECK IN":         login_val or "--",
            "last_check_out":         logout_val,
            "LAST CHECK OUT":         logout_val or "--",
            "single_punch":           single_punch_display,
            "Single Punch":           single_punch_display,
            "SINGLE PUNCH":           single_punch_display,
            "logout_date":            logout_date_str,
            "logout_date_str":        logout_date_str,
            "LOGOUT DATE":            logout_date_str,
            "Logout Date":            logout_date_str,
            "c_shift_exit":           logout_val if is_overnight else None,
            "C SHIFT EXIT":           logout_val if is_overnight else "--",
            "last_check_out_datetime": (
                f"{logout_date_str} {logout_val}"
                if logout_val and logout_date_str != "--" else None
            ),
            "working_hours":          working_hours_str,
            "working_hours_decimal":  working_hours_decimal,
            "overtime_hours":         overtime_hours_str,
            "overtime_hours_decimal": overtime_hours_decimal,
            "is_overnight":           is_overnight,
            "status":                 status,
            "remarks":                remarks,
            "punch_status":           punch_status,
            "Punch Status":           punch_status,
            "PUNCH STATUS":           punch_status,
            "MISSING SHIFT DETAILS":  rec.get("MISSING SHIFT DETAILS") or punch_status,
            "Missing Shift Details":  rec.get("Missing Shift Details") or punch_status,
            "Working Hours":          working_hours_str,
            "WORKING HOURS":          working_hours_str,
            "Overtime Hours":         overtime_hours_str,
            "OVERTIME HOURS":         overtime_hours_str,
            "OT Hours":               overtime_hours_str,
            "OT HOURS":               overtime_hours_str,
            "Overtime":               overtime_hours_str,
            "OVERTIME":               overtime_hours_str,
            "OT":                     overtime_hours_str,
            "Status":                 status,
            "STATUS":                 status,
        })
        return rec

    def process_dataframes(self, df_raw=None, df_punches=None):
        """
        Round 7 Entry Point:
        Processes (df_raw), (df_punches), or both (df_raw + df_punches).
        Uses Chronological Punch-Stream Pairing State Machine.
        """
        if df_raw is not None and df_punches is None:
            cols_lower = [str(c).lower() for c in df_raw.columns]
            if any("punch" in c for c in cols_lower) and not any("first check in" in c or "first in" in c for c in cols_lower):
                df_punches = df_raw
                df_raw = None

        if df_raw is not None and df_punches is not None:
            raw_cols = [str(c).lower() for c in df_raw.columns]
            punches_cols = [str(c).lower() for c in df_punches.columns]
            has_raw_in = any("first check in" in c or "first in" in c or "check in" in c for c in raw_cols)
            has_punc_in = any("first check in" in c or "first in" in c or "check in" in c for c in punches_cols)
            if not has_raw_in and has_punc_in:
                df_raw, df_punches = df_punches, df_raw

        if df_raw is None and df_punches is None:
            self.last_diagnostics = {"reason": "No dataframes provided"}
            return [], []

        raw_rows = []
        raw_headers = []
        col_map_raw = {}
        if df_raw is not None and not df_raw.empty:
            df_raw_clean, col_map_raw = self._auto_detect_header_and_map(df_raw)
            raw_headers = [str(c).strip() for c in df_raw_clean.columns if not str(c).startswith("Unnamed")]
            raw_rows = self._extract_raw_rows(df_raw_clean, col_map_raw, raw_headers)

        punches_by_emp = {}
        if df_punches is not None and not df_punches.empty:
            df_punches_clean, col_map_tp = self._auto_detect_header_and_map(df_punches)
            punches_by_emp = self._extract_total_punches(df_punches_clean, col_map_tp, source_name="TOTAL_PUNCHES sheet")

        if not punches_by_emp and df_raw is not None and not df_raw.empty:
            df_raw_clean, col_map_tp = self._auto_detect_header_and_map(df_raw)
            has_comma_punches = False
            for col in df_raw_clean.columns:
                c_clean = str(col).lower().strip()
                if "total" in c_clean or "punch" in c_clean or "all" in c_clean or "time" in c_clean or "log" in c_clean:
                    if df_raw_clean[col].astype(str).str.contains(",").any():
                        has_comma_punches = True
                        break
            if has_comma_punches:
                punches_by_emp = self._extract_total_punches(df_raw_clean, col_map_tp, source_name="RAW_DATA Total Punches column")

        if not punches_by_emp and raw_rows:
            punches_by_emp = self._extract_punches_from_raw_rows(raw_rows)

        emp_groups = {}
        for r in raw_rows:
            emp_groups.setdefault(r["emp_id"], []).append(r)
        for eid in punches_by_emp:
            if eid not in emp_groups:
                emp_groups[eid] = []

        results = []
        global_stats = {"overnight_chained": 0, "same_day": 0, "missing_out": 0, "missing_in": 0, "absent": 0}

        MIN_SESSION_GAP = timedelta(minutes=150)
        MAX_SESSION_HOURS = timedelta(hours=18)
        SINGLE_SHIFT_MIN = timedelta(hours=4)
        SINGLE_SHIFT_MAX = timedelta(hours=11)

        global_dates = set()
        for r in raw_rows:
            if r.get("date"):
                global_dates.add(r["date"])
        for eid, plist in punches_by_emp.items():
            for p in plist:
                if p.get("dt"):
                    global_dates.add(p["dt"].date())

        if global_dates:
            g_min = min(global_dates)
            g_max = max(global_dates)
            global_date_range = [g_min + timedelta(days=d) for d in range((g_max - g_min).days + 1)]
        else:
            global_date_range = []

        for emp_id in sorted(emp_groups.keys(), key=self._emp_sort_key):
            emp_rows = emp_groups[emp_id]
            emp_rows.sort(key=lambda r: r["date"])
            date_to_row = {r["date"]: r for r in emp_rows}

            emp_name = emp_rows[0]["emp_name"] if emp_rows else f"Employee_{emp_id}"
            gender = emp_rows[0]["gender"] if emp_rows else "Unspecified"
            dept = emp_rows[0]["dept"] if emp_rows else "General"

            emp_punches = punches_by_emp.get(emp_id, [])
            emp_punches.sort(key=lambda p: p["dt"])

            # Deduplicate consecutive identical punch timestamps (within 60s)
            # Allow at most 2 identical timestamps (0s diff) so twin punches like '06:01, 06:01'
            # can serve as overnight exit + same-day morning entry.
            dedup_punches = []
            for p in emp_punches:
                if not dedup_punches:
                    dedup_punches.append(p)
                else:
                    time_diff = abs((p["dt"] - dedup_punches[-1]["dt"]).total_seconds())
                    if time_diff >= 60:
                        dedup_punches.append(p)
                    elif time_diff == 0:
                        # If exact same timestamp, allow up to 2 instances if previous wasn't already a 3rd duplicate
                        prev_same_count = sum(1 for dp in reversed(dedup_punches) if dp["dt"] == p["dt"])
                        if prev_same_count < 2:
                            dedup_punches.append(p)

            is_debug_emp = (str(emp_id).upper() == "A0003")
            if is_debug_emp:
                print(f"\n=======================================================")
                print(f"[PUNCH-STREAM DEBUG] Employee ID: {emp_id}")
                print(f"[PUNCH-STREAM DEBUG] Flattened Chronological Punch List ({len(emp_punches)} punches):")
                for idx, p in enumerate(emp_punches):
                    print(f"  [{idx}] {p['dt'].strftime('%Y-%m-%d %H:%M:%S')} (kind={p['kind']})")
                print(f"=======================================================")

            sessions = []
            consumed_punches = set()

            # --- Round 11 (revised): Boundary-Orphan Checkout Check ---
            # Only skip an early-AM punch if:
            #   1. It is followed by a SINGLE later same-day punch with gap > 11h (i.e., the two punches
            #      cannot form a normal same-day session together), AND
            #   2. There is NOT already a valid same-day pair (2 punches that fit SINGLE_SHIFT_MIN..MAX).
            # If the same-day gap is within a valid shift range, keep the first punch as a login.
            i = 0
            while i < len(emp_punches):
                p_in = emp_punches[i]
                if id(p_in) in consumed_punches:
                    i += 1
                    continue

                if p_in["kind"] == "out":
                    if is_debug_emp:
                        print(f"[PUNCH-STREAM DEBUG] Step i={i}: Punch {p_in['dt'].strftime('%Y-%m-%d %H:%M')} is kind='out' -> Skip as login candidate")
                    i += 1
                    continue

                # Check if p_in is actually an orphan checkout from a prior session (e.g., 06:18 AM)
                # followed by a much later punch on the same date (> 11h gap, e.g. 22:10 PM)
                # But only skip it if the same-day pair gap is NOT in SINGLE_SHIFT_MIN..SINGLE_SHIFT_MAX
                # (i.e., the two same-day punches cannot form a valid shift themselves)
                if i + 1 < len(emp_punches):
                    p_next = emp_punches[i + 1]
                    if id(p_next) not in consumed_punches and p_in["dt"].date() == p_next["dt"].date():
                        gap_same_day = p_next["dt"] - p_in["dt"]
                        is_valid_same_day_pair = SINGLE_SHIFT_MIN <= gap_same_day <= SINGLE_SHIFT_MAX
                        # Confirm as orphan checkout via one of:
                        #   1. kind="out" (raw data explicitly labeled it as logout)
                        #   2. base_row shows raw logout < raw login (cross-midnight raw row)
                        #   3. date_to_row shows raw first_check_in > raw last_check_out
                        #      (e.g., raw row: first_check_in=22:10, last_check_out=06:18)
                        is_confirmed_orphan_out = (p_in["kind"] == "out")
                        if not is_confirmed_orphan_out:
                            # Check base_row directly
                            br = p_in.get("base_row")
                            raw_login = (br.get("login") if br else None) or (date_to_row.get(p_in["dt"].date(), {}) or {}).get("login")
                            raw_logout = (br.get("logout") if br else None) or (date_to_row.get(p_in["dt"].date(), {}) or {}).get("logout")
                            if raw_login and raw_logout:
                                lh, lm = self._safe_parse_hm(raw_login)
                                oh, om = self._safe_parse_hm(raw_logout)
                                if lh is not None and oh is not None:
                                    if oh * 60 + om < lh * 60 + lm:
                                        is_confirmed_orphan_out = True
                        if (gap_same_day > SINGLE_SHIFT_MAX and p_in["dt"].hour < 10
                                and not is_valid_same_day_pair and is_confirmed_orphan_out):
                            print(f"[ROUND 11 BOUNDARY-ORPHAN] emp_id={emp_id} date={p_in['dt'].date()} orphan_checkout={p_in['dt'].strftime('%H:%M')} next_punch={p_next['dt'].strftime('%H:%M')} gap={gap_same_day} -> Skip early AM punch as login candidate")
                            consumed_punches.add(id(p_in))
                            i += 1
                            continue
                p_in = emp_punches[i]
                if id(p_in) in consumed_punches:
                    i += 1
                    continue

                if p_in["kind"] == "out":
                    if is_debug_emp:
                        print(f"[PUNCH-STREAM DEBUG] Step i={i}: Punch {p_in['dt'].strftime('%Y-%m-%d %H:%M')} is kind='out' -> Skip as login candidate")
                    i += 1
                    continue

                login_dt = p_in["dt"]
                login_str = login_dt.strftime("%H:%M")
                if is_debug_emp:
                    print(f"[PUNCH-STREAM DEBUG] Step i={i}: Pending Login = {login_dt.strftime('%Y-%m-%d %H:%M')}")

                # --- Round 9: Same-Day Break-Punch Merging Check (MUST run before self_out & stream pairing) ---
                def _is_cross_midnight_raw_out(p_item):
                    if p_item["kind"] == "out" and p_item.get("base_row"):
                        br_in = p_item["base_row"].get("login")
                        if br_in:
                            lh, lm = self._safe_parse_hm(br_in)
                            if lh is not None and (p_item["dt"].hour * 60 + p_item["dt"].minute) < (lh * 60 + lm):
                                return True
                    return False

                same_date_punches = [
                    p for p in emp_punches
                    if p["dt"].date() == login_dt.date() and id(p) not in consumed_punches and not _is_cross_midnight_raw_out(p)
                ]
                same_date_punches.sort(key=lambda p: p["dt"])

                if len(same_date_punches) >= 3 and len(same_date_punches) % 2 != 0:
                    span = same_date_punches[-1]["dt"] - same_date_punches[0]["dt"]
                    punch_strs = [p["dt"].strftime("%H:%M") for p in same_date_punches]
                    print(f"[BREAK-MERGE CHECK] emp_id={emp_id} date={login_dt.date()} punches={punch_strs} span={span}")

                    if SINGLE_SHIFT_MIN <= span <= SINGLE_SHIFT_MAX:
                        first_p = same_date_punches[0]
                        last_p = same_date_punches[-1]
                        break_punches = same_date_punches[1:-1]
                        ignored_break_strs = [p["dt"].strftime("%H:%M") for p in break_punches]

                        print(f"[BREAK-MERGE CHECK]   -> MERGE SUCCESS: Login {first_p['dt'].strftime('%H:%M')} + Logout {last_p['dt'].strftime('%H:%M')} (Ignored breaks: {ignored_break_strs})")

                        sessions.append({
                            "login": first_p["dt"],
                            "logout": last_p["dt"],
                            "p_in": first_p,
                            "p_out": last_p,
                            "gap": span,
                            "stolen_from_self_paired": False,
                            "ignored_breaks": ignored_break_strs
                        })
                        for p in same_date_punches:
                            consumed_punches.add(id(p))
                        i += 1
                        continue

                # Check if this punch comes from a self-paired raw row whose logout punch is unconsumed
                self_out = None
                br = p_in.get("base_row")
                if br and br.get("login") and br.get("logout"):
                    for candidate in emp_punches:
                        if id(candidate) not in consumed_punches and candidate.get("base_row") is br and candidate["kind"] == "out":
                            self_out = candidate
                            break

                if self_out:
                    logout_dt = self_out["dt"]
                    if logout_dt < login_dt:
                        logout_dt = logout_dt + timedelta(days=1)
                    if is_debug_emp:
                        print(f"[PUNCH-STREAM DEBUG]   -> Paired via self_out with {logout_dt.strftime('%Y-%m-%d %H:%M')} (same base_row)")
                    sessions.append({
                        "login": login_dt,
                        "logout": logout_dt,
                        "p_in": p_in,
                        "p_out": self_out,
                        "gap": logout_dt - login_dt,
                        "stolen_from_self_paired": False
                    })
                    consumed_punches.add(id(p_in))
                    consumed_punches.add(id(self_out))
                    i += 1
                    continue

                # Stream pairing / Orphan candidate search
                found_pair = False
                j = i + 1
                while j < len(emp_punches):
                    p_out = emp_punches[j]
                    if id(p_out) in consumed_punches:
                        j += 1
                        continue

                    logout_dt = p_out["dt"]
                    gap = logout_dt - login_dt

                    if p_out["kind"] == "in":
                        c_br = p_out.get("base_row")
                        if c_br and not c_br.get("logout"):
                            j += 1
                            continue

                    if logout_dt.date() > login_dt.date() and not self.is_night_shift_start(login_str):
                        if is_debug_emp:
                            print(f"[PUNCH-STREAM DEBUG]   -> Candidate [{j}] {logout_dt.strftime('%Y-%m-%d %H:%M')}: Daytime login {login_str} not eligible for cross-midnight chaining -> DISCARD")
                        j += 1
                        continue

                    if gap < MIN_SESSION_GAP:
                        if is_debug_emp:
                            print(f"[PUNCH-STREAM DEBUG]   -> Candidate [{j}] {logout_dt.strftime('%Y-%m-%d %H:%M')}: gap {gap} < MIN_SESSION_GAP (150m) -> DISCARD AS NOISE")
                        consumed_punches.add(id(p_out))
                        j += 1
                        continue

                    # For night-shift logins (22:xx - 05:xx), cap pairing window at SINGLE_SHIFT_MAX (11h)
                    # This prevents wrong pairings like 22:05 -> next-day 13:52 (15:47h gap)
                    effective_max = MAX_SESSION_HOURS
                    if self.is_night_shift_start(login_str):
                        effective_max = SINGLE_SHIFT_MAX  # Night shift: max ~11h (22:00->09:00 at most)

                    if gap <= effective_max:
                        # Guard: do NOT steal p_out if it has exactly ONE same-day companion punch
                        # that can form a valid same-day Shift A/B session with it.
                        # Example: night 22:10 Jul24 should NOT steal 05:58 Jul25 when
                        # 05:58 + 14:06 (its sole companion) form a valid 8h Shift A pair.
                        # But for 3-punch days like [06:15, 14:05, 22:15], allow the overnight steal
                        # (06:15 is the night-exit; 14:05+22:15 remain as Shift B).
                        if self.is_night_shift_start(login_str):
                            same_day_companions = [
                                p for p in emp_punches
                                if p["dt"].date() == logout_dt.date()
                                and id(p) not in consumed_punches
                                and id(p) != id(p_out)
                            ]
                            if len(same_day_companions) == 1:
                                companion = same_day_companions[0]
                                companion_gap = abs((companion["dt"] - logout_dt).total_seconds())
                                if SINGLE_SHIFT_MIN.total_seconds() <= companion_gap <= SINGLE_SHIFT_MAX.total_seconds():
                                    # p_out + sole companion = valid same-day shift pair — don't steal
                                    print(f"[NIGHT-STEAL-GUARD] emp_id={emp_id} login={login_dt.strftime('%Y-%m-%d %H:%M')} "
                                          f"candidate={logout_dt.strftime('%Y-%m-%d %H:%M')} has 1 valid same-day companion "
                                          f"(gap={timedelta(seconds=companion_gap)}) -> SKIP steal")
                                    j += 1
                                    continue

                        stolen_from_self_paired = False
                        c_br = p_out.get("base_row")
                        if p_out["kind"] == "in" and c_br and c_br.get("login") and c_br.get("logout"):
                            if c_br.get("date") != (br.get("date") if br else None):
                                stolen_from_self_paired = True

                        if is_debug_emp:
                            print(f"[PUNCH-STREAM DEBUG]   -> PAIR SUCCESS: Login {login_dt.strftime('%Y-%m-%d %H:%M')} + Logout {logout_dt.strftime('%Y-%m-%d %H:%M')} (gap {gap})")

                        sessions.append({
                            "login": login_dt,
                            "logout": logout_dt,
                            "p_in": p_in,
                            "p_out": p_out,
                            "gap": gap,
                            "stolen_from_self_paired": stolen_from_self_paired
                        })
                        consumed_punches.add(id(p_in))
                        consumed_punches.add(id(p_out))
                        found_pair = True
                        i = j + 1
                        break
                    else:
                        if is_debug_emp:
                            print(f"[PUNCH-STREAM DEBUG]   -> Candidate [{j}] {logout_dt.strftime('%Y-%m-%d %H:%M')}: gap {gap} > effective_max ({effective_max}) -> STOP SEARCH")
                        break

                if not found_pair:
                    if is_debug_emp:
                        print(f"[PUNCH-STREAM DEBUG]   -> NO PAIR FOUND: Login {login_dt.strftime('%Y-%m-%d %H:%M')} -> Missing Punch-Out")
                    sessions.append({
                        "login": login_dt,
                        "logout": None,
                        "p_in": p_in,
                        "p_out": None,
                        "stolen_from_self_paired": False
                    })
                    consumed_punches.add(id(p_in))
                    i += 1

            consumed_logout_dts = {
                s["logout"] for s in sessions if s.get("logout") is not None
            }

            all_dates = global_date_range if global_date_range else sorted(list(date_to_row.keys()))
            if not all_dates and sessions:
                all_dates = sorted(list({s["login"].date() for s in sessions}))

            session_by_date = {s["login"].date(): s for s in sessions}
            handled_sessions = set()

            for r_date in all_dates:
                base_row = date_to_row.get(r_date)
                session = session_by_date.get(r_date)

                if session:
                    handled_sessions.add(id(session))
                    login_dt = session["login"]
                    logout_dt = session["logout"]
                    login_val = login_dt.strftime("%H:%M")

                    if logout_dt:
                        logout_val = logout_dt.strftime("%H:%M")
                        is_overnight = (logout_dt.date() > login_dt.date())
                        logout_date_obj = logout_dt.date()
                    else:
                        logout_val = None
                        is_overnight = False
                        logout_date_obj = None

                    rec = self._build_record_from_session(
                        emp_id, emp_name, gender, dept, r_date,
                        login_val, logout_val, is_overnight, logout_date_obj,
                        base_row, global_stats, raw_headers, col_map_raw,
                        has_prior_orphan=session.get("stolen_from_self_paired", False),
                        session_obj=session
                    )
                    results.append(rec)
                else:
                    if base_row and (base_row.get("login") or base_row.get("logout")):
                        login_val = base_row.get("login")
                        logout_val = base_row.get("logout")

                        if login_val is not None:
                            lh, lm = self._safe_parse_hm(login_val)
                            if lh is not None:
                                dt_lin = datetime(r_date.year, r_date.month, r_date.day, lh, lm)
                                if dt_lin in consumed_logout_dts:
                                    login_val = None

                        if logout_val is not None:
                            oh, om = self._safe_parse_hm(logout_val)
                            if oh is not None:
                                dt_lout = datetime(r_date.year, r_date.month, r_date.day, oh, om)
                                if dt_lout in consumed_logout_dts:
                                    logout_val = None

                        if login_val is not None or logout_val is not None:
                            raw_shift = base_row.get("shift") if base_row else None
                            if not raw_shift and base_row and "raw_cell_data" in base_row:
                                rcd = base_row["raw_cell_data"]
                                raw_shift = rcd.get("SHIFTS") or rcd.get("Shift") or rcd.get("shifts") or rcd.get("SHIFT")

                            if (login_val is not None and logout_val is None) or (login_val is None and logout_val is not None):
                                single_time = login_val or logout_val
                                login_val = None
                                logout_val = None
                                shift = "Unknown"
                                st = "Needs Manual Review"
                                rem = "Single punch recorded — manual review required"
                                session_calc = {
                                    "logout_date": None,
                                    "working_hours_str": "--",
                                    "working_hours_decimal": None,
                                    "is_overnight": False,
                                    "overtime_hours_str": "00:00",
                                    "overtime_hours_decimal": 0.0,
                                }
                                single_punch_val = single_time
                            else:
                                single_punch_val = None
                                session_calc = self._compute_session(login_val, logout_val, r_date)
                                shift, is_amb, label = self.determine_shift(
                                    login_val, logout_date=session_calc["logout_date"], login_date=r_date, logout_time_str=logout_val, raw_shift=raw_shift
                                )
                                st, rem = self._determine_status(login_val, logout_val, session_calc["working_hours_decimal"], shift, is_amb, label)

                            rec = self._build_record_dict(
                                base_row, emp_id, emp_name, gender, dept, r_date,
                                login_val, logout_val, session_calc["logout_date"],
                                session_calc["working_hours_str"], session_calc["working_hours_decimal"],
                                session_calc["is_overnight"], shift, st, rem, raw_headers, col_map_raw,
                                overtime_hours_str=session_calc.get("overtime_hours_str", "00:00"),
                                overtime_hours_decimal=session_calc.get("overtime_hours_decimal", 0.0),
                                single_punch_val=single_punch_val
                            )
                            results.append(rec)
                        else:
                            rec = self._build_record_dict(
                                base_row, emp_id, emp_name, gender, dept, r_date,
                                None, None, None, "--", None, False, "Unknown", "Absent", "No punch recorded",
                                raw_headers, col_map_raw
                            )
                            results.append(rec)
                    else:
                        rec = self._build_record_dict(
                            base_row, emp_id, emp_name, gender, dept, r_date,
                            None, None, None, "--", None, False, "Unknown", "Absent", "No punch recorded",
                            raw_headers, col_map_raw
                        )
                        results.append(rec)

            for session in sessions:
                if id(session) not in handled_sessions:
                    login_dt = session["login"]
                    logout_dt = session["logout"]
                    r_date = login_dt.date()
                    login_val = login_dt.strftime("%H:%M")
                    logout_val = logout_dt.strftime("%H:%M") if logout_dt else None
                    is_overnight = (logout_dt.date() > login_dt.date()) if logout_dt else False
                    logout_date_obj = logout_dt.date() if logout_dt else None

                    rec = self._build_record_from_session(
                        emp_id, emp_name, gender, dept, r_date,
                        login_val, logout_val, is_overnight, logout_date_obj,
                        None, global_stats, raw_headers, col_map_raw,
                        session_obj=session
                    )
                    results.append(rec)

        self.last_diagnostics["session_pairing_stats"] = global_stats
        self.last_diagnostics["overnight_chained_count"] = global_stats.get("overnight_chained", 0)
        self.last_diagnostics["same_day_count"]          = global_stats.get("same_day", 0)
        self.last_diagnostics["missing_out_count"]        = global_stats.get("missing_out", 0)
        self.last_diagnostics["missing_in_count"]         = global_stats.get("missing_in", 0)
        self.last_diagnostics["absent_count"]             = global_stats.get("absent", 0)

        def _sort_key(r):
            eid = str(r.get("employee_id", "")).strip()
            try:
                ek = (0, int(eid))
            except (ValueError, TypeError):
                ek = (1, eid.lower())

            d = r.get("attendance_date")
            if isinstance(d, datetime):
                d = d.date()
            elif isinstance(d, str) and d:
                d = self._normalize_date(d)
            dk = (d.year, d.month, d.day) if isinstance(d, date) else (9999, 0, 0)

            t = r.get("first_check_in") or "00:00"
            th, tm = self._safe_parse_hm(t)
            tk = (th or 0, tm or 0)

            return (*ek, *dk, *tk)

        results.sort(key=_sort_key)

        dt_roles    = {"login", "logout", "date", "weekday"}
        dt_raw_cols = {col_map_raw[r] for r in dt_roles if r in col_map_raw and col_map_raw[r] in raw_headers}
        skip_raw    = {"totaltime", "totalhours", "totalhrs", "workinghours"}

        info_cols     = []
        trailing_cols = []
        seen_date_area = False

        for c in raw_headers:
            c_clean = str(c).lower().replace("_", "").replace(".", "").replace(" ", "")
            if c in dt_raw_cols or c.lower() in ("logout date", "check-out date", "checkout date"):
                seen_date_area = True
                continue
            if c_clean in skip_raw:
                continue
            if not seen_date_area:
                info_cols.append(c)
            else:
                trailing_cols.append(c)

        wday_col        = col_map_raw.get("weekday") or "WEEKDAY"
        date_col        = col_map_raw.get("date")    or "DATE"
        login_col       = col_map_raw.get("login")   or "FIRST CHECK IN"
        logout_date_col = "LOGOUT DATE"
        logout_col      = col_map_raw.get("logout")  or "LAST CHECK OUT"

        final_cols = list(info_cols)
        for c in (wday_col, date_col, login_col, logout_date_col, logout_col, "SINGLE PUNCH"):
            if c not in final_cols:
                final_cols.append(c)
        for c in trailing_cols:
            if c not in final_cols:
                final_cols.append(c)
        for c in ("Shift", "Working Hours", "Overtime Hours", "Status", "PUNCH STATUS"):
            if c not in final_cols:
                final_cols.append(c)

        return results, final_cols

    def process_dataframe(self, df):
        """Backwards compatible public method forwarding to process_dataframes."""
        return self.process_dataframes(df_raw=df)