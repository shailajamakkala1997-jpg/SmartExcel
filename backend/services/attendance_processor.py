import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta, time
import re

class AttendanceProcessor:
    def __init__(self):
        self.last_diagnostics = {}

    def _normalize_time_str(self, val):
        """Converts various time representations into standard HH:MM format."""
        if pd.isna(val) or val is None or str(val).strip() in ["", "nan", "NaN", "NaT", "--", "None", "-"]:
            return None
        
        val_str = str(val).strip()
        
        # Handle datetime/timestamp object or pandas Timestamp
        if isinstance(val, (datetime, pd.Timestamp)):
            return val.strftime("%H:%M")
        if isinstance(val, time):
            return val.strftime("%H:%M")

        # Handle Excel float time representation (fraction of 24h, e.g. 0.9111 = 21:52)
        if isinstance(val, (float, int)) and 0 <= val < 1:
            try:
                total_seconds = int(round(val * 86400))
                hours = (total_seconds // 3600) % 24
                minutes = (total_seconds % 3600) // 60
                return f"{hours:02d}:{minutes:02d}"
            except Exception:
                pass

        # Try parsing standard time formats (HH:MM, HH:MM:SS, 12-hour AM/PM, dot time, etc.)
        for fmt in ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p", "%I:%M%p", "%I:%M %P", "%H.%M", "%H.%M.%S", "%H%M"]:
            try:
                dt = datetime.strptime(val_str, fmt)
                return dt.strftime("%H:%M")
            except ValueError:
                pass
        
        # If timestamp string like "2026-06-03 21:52:00"
        if " " in val_str and ":" in val_str:
            parts = val_str.split()
            for part in parts:
                if ":" in part:
                    res = self._normalize_time_str(part)
                    if res: return res

        # Regex extraction fallback (e.g., "21:52:00" or "9:52pm")
        match = re.search(r'(\d{1,2}):(\d{2})', val_str)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            if 0 <= h < 24 and 0 <= m < 60:
                return f"{h:02d}:{m:02d}"
                
        return None

    def _normalize_date(self, val):
        """Converts date values into standard datetime.date objects."""
        if pd.isna(val) or val is None or str(val).strip() in ["", "nan", "NaN", "NaT", "--", "None"]:
            return None
            
        if isinstance(val, (datetime, pd.Timestamp)):
            return val.date()
        if isinstance(val, date):
            return val
            
        # Handle Excel serial numbers (e.g. 45446 -> 2026-06-03)
        if isinstance(val, (int, float)) and not pd.isna(val):
            try:
                if 30000 < float(val) < 70000:
                    return (datetime(1899, 12, 30) + timedelta(days=float(val))).date()
            except Exception:
                pass

        val_str = str(val).strip()
        
        # String serial float
        try:
            val_float = float(val_str)
            if 30000 < val_float < 70000:
                return (datetime(1899, 12, 30) + timedelta(days=val_float)).date()
        except ValueError:
            pass

        # If date string has time component, extract date part
        if " " in val_str and ("-" in val_str or "/" in val_str or "." in val_str):
            val_str = val_str.split()[0]

        for fmt in [
            "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", 
            "%d.%m.%Y", "%Y.%m.%d", "%d-%b-%Y", "%d-%B-%Y", "%Y%m%d", 
            "%d%m%Y", "%d-%m-%y", "%d/%m/%y", "%d.%m.%y", "%b %d, %Y", "%B %d, %Y",
            "%m-%d", "%d-%m", "%m/%d", "%d/%m"
        ]:
            try:
                dt = datetime.strptime(val_str, fmt)
                if fmt in ["%m-%d", "%d-%m", "%m/%d", "%d/%m"]:
                    dt = dt.replace(year=datetime.now().year)
                return dt.date()
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
        """Safely extract (hour, minute) from a time value that may be str, float, or None."""
        if val is None:
            return None, None
        # If float (Excel decimal time), convert first
        if isinstance(val, (float, int)) and not isinstance(val, bool):
            normalized = self._normalize_time_str(val)
            if normalized:
                val = normalized
            else:
                return None, None
        val = str(val).strip()
        if ":" not in val:
            normalized = self._normalize_time_str(val)
            if normalized and ":" in normalized:
                val = normalized
            else:
                return None, None
        try:
            parts = val.split(":")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return None, None

    def determine_shift(self, login_time_str):
        """
        Determines shift based on login check-in time:
        Shift A (Day): 05:30 - 13:29 (Scheduled 06:00 - 14:00)
        Shift B (Eve): 13:30 - 21:29 (Scheduled 14:00 - 22:00)
        Shift C (Night): 21:30 - 05:29 (Scheduled 22:00 - 06:00)
        """
        if not login_time_str:
            return "Unknown"
        
        h, m = self._safe_parse_hm(login_time_str)
        if h is None:
            return "Unknown"

        total_mins = h * 60 + m
        
        if 330 <= total_mins < 810:      # 05:30 AM to 13:29 PM
            return "A"
        elif 810 <= total_mins < 1290:   # 13:30 PM to 21:29 PM
            return "B"
        else:                            # 21:30 PM to 05:29 AM
            return "C"

    def calculate_working_hours(self, login_str, logout_str):
        """
        Calculates working hours and returns (formatted_str, decimal_hours, is_overnight).
        Handles cross-midnight (e.g. 21:52 -> 06:12 = 8h 20m = 8.33h).
        """
        if not login_str or not logout_str:
            return "00:00", 0.0, False
            
        lh, lm = self._safe_parse_hm(login_str)
        oh, om = self._safe_parse_hm(logout_str)
        if lh is None or oh is None:
            return "00:00", 0.0, False
        
        login_mins = lh * 60 + lm
        logout_mins = oh * 60 + om
        
        is_overnight = False
        if logout_mins < login_mins:
            logout_mins += 24 * 60
            is_overnight = True
        elif lh >= 21 and oh <= 7:
            is_overnight = True
            
        diff_mins = logout_mins - login_mins
        
        hours = diff_mins // 60
        mins = diff_mins % 60
        decimal_hours = round(diff_mins / 60.0, 2)
        
        return f"{hours:02d}:{mins:02d}", decimal_hours, is_overnight

    def detect_exceptions_and_status(self, shift, login_str, logout_str, decimal_hours, is_overnight):
        """Detects anomalies and determines attendance status & detailed remarks."""
        remarks = []
        
        if not login_str and not logout_str:
            return "Absent", "No punch recorded"
        if not login_str:
            return "Missing Login", "Missing Check-in punch"
        if not logout_str:
            return "Missing Logout", "Missing Check-out punch"
            
        if decimal_hours == 0.0:
            return "Invalid Hours", "Duration is 0 hours (Possible double punch)"
        if decimal_hours > 15.0:
            return "Invalid Hours", f"Exceeds max threshold: {decimal_hours} hours recorded"
            
        lh, lm = self._safe_parse_hm(login_str)
        if lh is None:
            return "Present", "Normal Attendance"
        login_mins = lh * 60 + lm
        
        is_late = False
        if shift == "A" and login_mins > (6 * 60 + 15):
            is_late = True
            remarks.append("Late Check-in (Shift A)")
        elif shift == "B" and login_mins > (14 * 60 + 15):
            is_late = True
            remarks.append("Late Check-in (Shift B)")
        elif shift == "C" and (login_mins > (22 * 60 + 15) or login_mins < (5 * 60)):
            is_late = True
            remarks.append("Late Check-in (Shift C)")

        is_overtime = False
        if decimal_hours > 8.5:
            is_overtime = True
            remarks.append(f"Overtime recorded ({decimal_hours} hrs)")

        if is_late:
            status = "Late Login"
        elif is_overtime:
            status = "Overtime"
        else:
            status = "Present"
            
        if is_overnight:
            remarks.append("Night shift overnight record")

        remark_str = "; ".join(remarks) if remarks else "Normal Attendance"
        return status, remark_str

    def _auto_detect_header_and_map(self, df: pd.DataFrame):
        """Finds header row if not row 0 and maps column aliases to canonical keys."""
        working_df = df.copy()

        # Keywords ranked by specificity
        id_kw = ["emp code", "employee code", "emp id", "employee id", "emp_id", "emp_code", "staff id", "user id", "card no", "badge no", "badge", "enroll id", "bio id", "staff_id", "user_id"]
        id_fallback_kw = ["id", "code", "pin"]
        
        name_kw = ["employee name", "emp name", "staff name", "user name", "full name", "emp_name", "staff_name", "user_name"]
        first_name_kw = ["first name", "firstname", "first_name", "fname"]
        last_name_kw = ["last name", "lastname", "last_name", "surname", "lname"]
        name_fallback_kw = ["name", "employee", "staff", "user", "person"]

        date_kw = ["attendance date", "punch date", "log date", "shift date", "work date", "atten date", "att date", "date", "dt", "day"]

        login_kw = ["first check in", "first check-in", "first checkin", "check in", "check-in", "checkin", "first in", "firstin", "first_in", "1st in", "in time", "intime", "time in", "timein", "punch in", "clock in", "start time", "login", "log in", "in_time", "time_in"]
        login_fallback_kw = ["in"]

        logout_kw = ["last check out", "last check-out", "last checkout", "check out", "check-out", "checkout", "last out", "lastout", "last_out", "out time", "outtime", "time out", "timeout", "punch out", "clock out", "end time", "logout", "log out", "out_time", "time_out"]
        logout_fallback_kw = ["out"]

        gender_kw = ["gender", "sex"]
        dept_kw = ["department", "dept", "section", "division", "unit", "branch"]

        def score_row(col_list):
            cols_str = [str(c).strip().lower().replace("_", " ").replace("-", " ") for c in col_list]
            score = 0
            has_name = any(any(k in c for k in (name_kw + first_name_kw + name_fallback_kw)) for c in cols_str)
            has_id = any(any(k in c for k in id_kw) for c in cols_str)
            has_date = any(any(k in c for k in date_kw) for c in cols_str)
            has_login = any(any(k in c for k in (login_kw + ["in"])) for c in cols_str)
            has_logout = any(any(k in c for k in (logout_kw + ["out"])) for c in cols_str)
            
            if has_name or has_id: score += 2
            if has_date: score += 2
            if has_login or has_logout: score += 2
            return score

        # Always check top 15 rows for the maximum scoring header row
        best_score = score_row(working_df.columns)
        header_row_idx = -1

        if len(working_df) > 0:
            for r in range(min(15, len(working_df))):
                row_vals = working_df.iloc[r].tolist()
                s = score_row(row_vals)
                if s > best_score:
                    best_score = s
                    header_row_idx = r

        if header_row_idx >= 0:
            new_cols = [str(c).strip() if not pd.isna(c) else f"Unnamed_{i}" for i, c in enumerate(working_df.iloc[header_row_idx])]
            working_df = working_df.iloc[header_row_idx + 1:].reset_index(drop=True)
            working_df.columns = new_cols

        # Now build canonical col_map safely
        col_map = {}
        columns = list(working_df.columns)

        def match_col(category_kws, exclude_used=True):
            for kw in category_kws:
                for col in columns:
                    if exclude_used and col in col_map.values():
                        continue
                    col_lower = str(col).strip().lower().replace("_", " ").replace("-", " ")
                    words = set(re.findall(r'\w+', col_lower))
                    
                    if " " in kw:
                        if kw in col_lower:
                            return col
                    else:
                        if kw in words or col_lower == kw:
                            return col
            return None

        # Match specific ID & Name columns first
        col_map["id"] = match_col(id_kw) or match_col(id_fallback_kw)
        col_map["name"] = match_col(name_kw)
        col_map["first_name"] = match_col(first_name_kw)
        col_map["last_name"] = match_col(last_name_kw)

        if not col_map.get("name"):
            if col_map.get("first_name"):
                col_map["name"] = col_map["first_name"]
            else:
                col_map["name"] = match_col(name_fallback_kw)

        col_map["date"] = match_col(date_kw)
        col_map["login"] = match_col(login_kw) or match_col(login_fallback_kw)
        col_map["logout"] = match_col(logout_kw) or match_col(logout_fallback_kw)
        col_map["gender"] = match_col(gender_kw)
        col_map["dept"] = match_col(dept_kw)

        # Fallback positional inferencing based on cell content if login/logout/date missing
        if len(working_df) > 0:
            sample = working_df.head(10)
            for col in columns:
                if col in col_map.values() or str(col).startswith("Unnamed"):
                    continue
                vals = [str(v).strip() for v in sample[col].dropna() if str(v).strip() not in ["", "nan", "None", "NaT"]]
                if not vals:
                    continue
                
                # Check if values look like time (HH:MM or HH:MM:SS)
                time_matches = sum(1 for v in vals if self._normalize_time_str(v) is not None)
                if time_matches >= max(1, len(vals) * 0.4):
                    if "login" not in col_map:
                        col_map["login"] = col
                    elif "logout" not in col_map:
                        col_map["logout"] = col
                    continue

                # Check if values look like date
                date_matches = sum(1 for v in vals if self._normalize_date(v) is not None)
                if date_matches >= max(1, len(vals) * 0.4):
                    if "date" not in col_map:
                        col_map["date"] = col
                    continue

        # Remove None entries
        col_map = {k: v for k, v in col_map.items() if v is not None}

        return working_df, col_map

    def process_dataframe(self, df: pd.DataFrame):
        """
        Intelligent processing of Pandas dataframe:
        - Auto detects header row
        - Normalizes column names
        - Pairs overnight night-shift punches across dates if split across rows
        - Assigns shifts, calculates working hours, detects exceptions
        - Preserves user's original Excel column names dynamically
        """
        if df is None or df.empty:
            self.last_diagnostics = {"reason": "Uploaded Excel sheet is empty"}
            return [], []

        df, col_map = self._auto_detect_header_and_map(df)
        
        # Capture clean original columns from Excel
        raw_headers = [str(c).strip() for c in df.columns if not str(c).startswith("Unnamed")]

        self.last_diagnostics = {
            "columns_found": list(df.columns),
            "mapped_columns": col_map,
            "total_rows_read": len(df)
        }

        processed_rows = []
        for idx, row in df.iterrows():
            # Extract raw ID value without substituting dummy string unless empty
            raw_id_val = row.get(col_map.get("id")) if col_map.get("id") else None
            if pd.notna(raw_id_val) and str(raw_id_val).strip() not in ["", "nan", "None", "NaT"]:
                if isinstance(raw_id_val, float) and raw_id_val == int(raw_id_val):
                    emp_id = str(int(raw_id_val))
                else:
                    emp_id = str(raw_id_val).strip()
            else:
                emp_id = f"EMP_{idx+1:03d}"

            # Extract raw Name value without substituting dummy string unless empty
            raw_name_val = row.get(col_map.get("name")) if col_map.get("name") else None
            first_val = row.get(col_map.get("first_name")) if col_map.get("first_name") else None
            last_val = row.get(col_map.get("last_name")) if col_map.get("last_name") else None

            if pd.notna(raw_name_val) and str(raw_name_val).strip() not in ["", "nan", "None", "NaT"]:
                emp_name = str(raw_name_val).strip()
                if col_map.get("first_name") and col_map.get("last_name") and col_map.get("name") == col_map.get("first_name"):
                    if pd.notna(last_val) and str(last_val).strip() not in ["", "nan", "None"]:
                        emp_name = f"{emp_name} {str(last_val).strip()}"
            elif pd.notna(first_val) or pd.notna(last_val):
                f_s = str(first_val).strip() if (pd.notna(first_val) and str(first_val).strip() not in ["nan", "None"]) else ""
                l_s = str(last_val).strip() if (pd.notna(last_val) and str(last_val).strip() not in ["nan", "None"]) else ""
                emp_name = f"{f_s} {l_s}".strip()
            else:
                emp_name = f"Employee_{idx+1}"

            raw_date = self._normalize_date(row.get(col_map.get("date"))) if col_map.get("date") else None
            login_time = self._normalize_time_str(row.get(col_map.get("login"))) if col_map.get("login") else None
            logout_time = self._normalize_time_str(row.get(col_map.get("logout"))) if col_map.get("logout") else None
            
            # Fallback 1: Extract date from check-in or check-out if date column missing/unparseable
            if raw_date is None:
                if col_map.get("login"):
                    raw_date = self._normalize_date(row.get(col_map.get("login")))
                if raw_date is None and col_map.get("logout"):
                    raw_date = self._normalize_date(row.get(col_map.get("logout")))

            # Fallback 2: Default to today's date if employee or checkin/checkout exists
            if raw_date is None and (login_time is not None or logout_time is not None or col_map.get("name")):
                raw_date = date.today()

            if raw_date is None:
                continue

            gender = str(row.get(col_map.get("gender"), "Unspecified")).strip() if col_map.get("gender") else "Unspecified"
            dept = str(row.get(col_map.get("dept"), "General")).strip() if col_map.get("dept") else "General"
            if gender.lower() in ["nan", "none", ""]: gender = "Unspecified"
            if dept.lower() in ["nan", "none", ""]: dept = "General"

            weekday_str = raw_date.strftime("%A")

            # Identify which raw columns are time or date columns
            time_cols = set()
            date_cols = set()
            for role, mapped_col in col_map.items():
                if role in ("login", "logout"):
                    time_cols.add(mapped_col)
                elif role == "date":
                    date_cols.add(mapped_col)

            # Capture all raw column values for this row, properly normalized
            raw_row_data = {}
            for col in raw_headers:
                val = row.get(col)
                if pd.isna(val) or val is None or str(val).strip() in ["nan", "None", "NaT"]:
                    raw_row_data[col] = ""
                elif col in time_cols:
                    normalized = self._normalize_time_str(val)
                    raw_row_data[col] = normalized if normalized else str(val).strip()
                elif col in date_cols:
                    normalized = self._normalize_date(val)
                    raw_row_data[col] = normalized.strftime("%Y-%m-%d") if normalized else str(val).strip()
                elif isinstance(val, (datetime, pd.Timestamp)):
                    raw_row_data[col] = val.strftime("%Y-%m-%d %H:%M")
                elif isinstance(val, date):
                    raw_row_data[col] = val.strftime("%Y-%m-%d")
                elif isinstance(val, float):
                    if 0 <= val < 1:
                        normalized = self._normalize_time_str(val)
                        if normalized:
                            raw_row_data[col] = normalized
                        else:
                            raw_row_data[col] = str(val).strip()
                    else:
                        raw_row_data[col] = str(int(val)) if val == int(val) else str(val).strip()
                else:
                    raw_row_data[col] = str(val).strip()
            
            # Calculate exact datetime sort key for chronological ordering
            time_str = login_time or logout_time or "00:00"
            sh, sm = 0, 0
            if time_str:
                res_parsed = self._safe_parse_hm(time_str)
                if res_parsed[0] is not None:
                    sh, sm = res_parsed[0], res_parsed[1]
            
            sort_dt = datetime.combine(raw_date, time(sh, sm)) if isinstance(raw_date, date) else datetime(1970, 1, 1, sh, sm)

            processed_rows.append({
                "raw_idx": int(idx),
                "emp_id": emp_id,
                "emp_name": emp_name,
                "gender": gender,
                "department": dept,
                "date": raw_date,
                "sort_dt": sort_dt,
                "weekday": weekday_str,
                "login": login_time,
                "logout": logout_time,
                "raw_row_data": raw_row_data
            })

        if not processed_rows:
            return [], []

        pdf = pd.DataFrame(processed_rows)
        # CRITICAL PROJECT GOAL: Sort chronologically by employee ID (numeric-safe), employee name, and exact datetime!
        # Numeric-safe emp_id key: numeric IDs sort as numbers (1,2,10), non-numeric sort alphabetically after
        def _emp_sort_key_val(eid):
            try:
                return (0, int(str(eid).strip()))
            except (ValueError, TypeError):
                return (1, str(eid).strip().lower())
        pdf["_emp_sort_key"] = pdf["emp_id"].apply(_emp_sort_key_val)
        pdf = pdf.sort_values(by=["_emp_sort_key", "emp_name", "sort_dt"]).reset_index(drop=True)
        pdf.drop(columns=["_emp_sort_key"], inplace=True)

        results = []
        skip_indices = set()

        for i in range(len(pdf)):
            if i in skip_indices:
                continue
                
            curr = pdf.iloc[i]
            curr_emp_id = curr["emp_id"]
            curr_emp_name = curr["emp_name"]
            curr_date = curr["date"]
            login = curr["login"] if pd.notna(curr["login"]) else None
            logout = curr["logout"] if pd.notna(curr["logout"]) else None
            raw_row_data = dict(curr["raw_row_data"])
            checkout_date = curr_date  # Default checkout date = same day
            
            shift = self.determine_shift(login)
            
            # Check if login is genuinely a night shift check-in (19:00 PM to 04:30 AM)
            is_night_login = False
            if login:
                lh, lm = self._safe_parse_hm(login)
                if lh is not None:
                    login_m = lh * 60 + lm
                    if login_m >= 1140 or login_m < 270:
                        is_night_login = True

            # If night login and missing logout, search next rows chronologically for morning logout punch
            if is_night_login and (not logout or logout in ["00:00", "00:00:00"]):
                for j in range(i + 1, min(i + 10, len(pdf))):
                    if j in skip_indices:
                        continue
                    next_row = pdf.iloc[j]
                    next_emp_id = next_row["emp_id"]
                    next_emp_name = next_row["emp_name"]
                    
                    # Match employee ID or Employee Name
                    if (next_emp_id and curr_emp_id and next_emp_id != curr_emp_id) and \
                       (next_emp_name and curr_emp_name and next_emp_name != curr_emp_name):
                        continue

                    next_date = next_row["date"]
                    day_diff = (next_date - curr_date).days if next_date and curr_date else -1
                    
                    # Must be same day or next consecutive day
                    if day_diff not in [0, 1]:
                        if day_diff > 1:
                            break
                        continue

                    # Candidate morning punch: try logout first, then login
                    next_logout = next_row["logout"] if pd.notna(next_row["logout"]) else None
                    next_login = next_row["login"] if pd.notna(next_row["login"]) else None
                    candidate_out = next_logout if (next_logout and next_logout not in ["00:00", "00:00:00"]) else next_login

                    if candidate_out and candidate_out not in ["00:00", "00:00:00"]:
                        n_h, _ = self._safe_parse_hm(candidate_out)
                        if n_h is not None and n_h < 14:  # Morning logout before 2 PM
                            logout = candidate_out
                            shift = self.determine_shift(login)
                            checkout_date = next_date  # Checkout is on the NEXT day
                            skip_indices.add(j)
                            break

            working_hours_str, decimal_hours, is_overnight = self.calculate_working_hours(login, logout)
            
            if is_overnight and checkout_date == curr_date and logout:
                checkout_date = curr_date + timedelta(days=1)

            if is_overnight and shift != "C" and login:
                lh_check, _ = self._safe_parse_hm(login)
                if lh_check is not None and lh_check >= 21:
                    shift = "C"

            status, remarks = self.detect_exceptions_and_status(shift, login, logout, decimal_hours, is_overnight)

            # Compute explicit logout date & checkout datetime string for EVERY shift
            if logout:
                logout_date = checkout_date
                logout_date_str = checkout_date.strftime('%Y-%m-%d')
                last_check_out_datetime = f"{logout_date_str} {logout}"
                if col_map.get("logout"):
                    raw_row_data[col_map["logout"]] = logout
                raw_row_data["Logout Date"] = logout_date_str
            else:
                logout_date = None
                logout_date_str = None
                last_check_out_datetime = None
                raw_row_data["Logout Date"] = "--"

            # Update login in raw_row_data if mapped
            if col_map.get("login") and login:
                raw_row_data[col_map["login"]] = login

            # Build row object combining original Excel fields with calculated fields
            rec_dict = dict(raw_row_data)
            # Update any raw Total Time / Working Hours key with dynamically calculated working hours
            for k in list(rec_dict.keys()):
                if str(k).lower().strip() in ("total time", "total_time", "total hrs", "total hours", "working hours", "working_hours"):
                    rec_dict[k] = working_hours_str

            rec_dict.update({
                "raw_idx": curr["raw_idx"],
                "employee_id": curr["emp_id"],
                "employee_name": emp_name,
                "gender": curr["gender"],
                "department": curr["department"],
                "attendance_date": curr_date,
                "logout_date": logout_date_str if logout_date_str else "",
                "logout_date_str": logout_date_str if logout_date_str else "--",
                "Logout Date": logout_date_str if logout_date_str else "--",
                "weekday": curr["weekday"],
                "shift": shift,
                "first_check_in": login,
                "last_check_out": logout,
                "last_check_out_datetime": last_check_out_datetime,
                "working_hours": working_hours_str,
                "working_hours_decimal": decimal_hours,
                "status": status,
                "remarks": remarks,
                "is_overnight": is_overnight
            })

            results.append(rec_dict)

        # Sort final output: Employee first (numeric-safe), then Date ascending, then Check-in time
        def get_sort_key(r):
            emp_val = r.get("employee_id") or r.get("EMPLOYEE ID") or r.get("employee_name") or ""
            emp_str = str(emp_val or "").strip()
            # Numeric-safe: parse as int when possible so "1","2","10" sort as 1,2,10 not 1,10,2
            try:
                emp_key = (0, int(emp_str))
            except (ValueError, TypeError):
                emp_key = (1, emp_str.lower())

            raw_d = r.get("attendance_date") or r.get("DATE") or r.get("Date") or r.get("date") or ""
            date_obj = None
            if isinstance(raw_d, datetime):
                date_obj = raw_d.date()
            elif isinstance(raw_d, date):
                date_obj = raw_d
            elif isinstance(raw_d, str) and raw_d.strip() and raw_d.strip() != "--":
                date_obj = self._normalize_date(raw_d.strip())

            y_val, m_val, d_val = 9999, 0, 0
            if date_obj is not None:
                y_val, m_val, d_val = date_obj.year, date_obj.month, date_obj.day

            t_val = r.get("first_check_in") or r.get("FIRST CHECK IN") or r.get("login") or "00:00"
            sh, sm = 0, 0
            if t_val and t_val != "--":
                res_parsed = self._safe_parse_hm(t_val)
                if res_parsed[0] is not None:
                    sh, sm = res_parsed[0], res_parsed[1]

            return (*emp_key, y_val, m_val, d_val, sh, sm)

        results.sort(key=get_sort_key)

        # Build dynamic column list respecting the user's requested order:
        # Info Cols -> WEEKDAY -> DATE -> FIRST CHECK IN -> LOGOUT DATE -> LAST CHECK OUT -> Trailing Cols -> Shift -> Working Hours -> Status
        dt_roles = {"weekday", "date", "login", "logout"}
        dt_cols_in_raw = set()
        for role in dt_roles:
            if col_map.get(role) and col_map[role] in raw_headers:
                dt_cols_in_raw.add(col_map[role])

        weekday_col = col_map.get("weekday") or next((c for c in raw_headers if c.lower() == "weekday"), "WEEKDAY")
        date_col = col_map.get("date") or next((c for c in raw_headers if "date" in c.lower() and "logout" not in c.lower()), "DATE")
        login_col = col_map.get("login") or next((c for c in raw_headers if "in" in c.lower() or "login" in c.lower()), "FIRST CHECK IN")
        logout_date_col = "LOGOUT DATE"
        logout_time_col = col_map.get("logout") or next((c for c in raw_headers if "out" in c.lower() or "logout" in c.lower()), "LAST CHECK OUT")

        info_cols = []
        trailing_cols = []
        seen_date_area = False

        for c in raw_headers:
            c_clean = str(c).lower().replace("_", "").replace(".", "").replace(" ", "").strip()
            if c in dt_cols_in_raw or c.lower() in ("logout date", "check-out date", "checkout date", "weekday"):
                seen_date_area = True
                continue
            # Exclude raw Total Time / Working Hours column so we don't display duplicate time columns
            if c_clean in ("totaltime", "totalhours", "totalhrs", "workinghours"):
                continue
            if not seen_date_area:
                info_cols.append(c)
            else:
                trailing_cols.append(c)

        final_cols = list(info_cols)
        
        # Insert Date/Time columns in exact requested order
        ordered_dt = [weekday_col, date_col, login_col, logout_date_col, logout_time_col]
        for c in ordered_dt:
            if c not in final_cols:
                final_cols.append(c)

        for c in trailing_cols:
            if c not in final_cols:
                final_cols.append(c)

        for extra in ["Shift", "Working Hours", "Status"]:
            if extra not in final_cols:
                final_cols.append(extra)

        return results, final_cols

