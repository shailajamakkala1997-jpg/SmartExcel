import pandas as pd
from datetime import datetime
from services.attendance_processor import AttendanceProcessor

proc = AttendanceProcessor()

# Test 1: Normal day shift - checkout should show same-day date
print("=== Test 1: Normal Shift A ===")
df1 = pd.DataFrame([
    {'No.': 1, 'Employee ID': 'A0201', 'First Name': 'A Harisha', 'Gender': 'Female', 'Date': '2026-06-12', 'First Check In': '13:53', 'Last Check Out': '22:03'},
])
res1, cols1 = proc.process_dataframe(df1)
r = res1[0]
print(f"  Columns: {cols1}")
print(f"  No.     raw: {r.get('No.')}")
print(f"  Emp ID  raw: {r.get('Employee ID')}")
print(f"  Name    raw: {r.get('First Name')}")
print(f"  Date       : {r.get('attendance_date')}")
print(f"  Logout Date: {r.get('Logout Date')}")
print(f"  Checkout   : {r.get('last_check_out')}")
print(f"  Checkout dt: {r.get('last_check_out_datetime')}")

# Test 2: Night shift spanning two rows - checkout should show next-day date
print("\n=== Test 2: Night Shift C (2 rows) ===")
df2 = pd.DataFrame([
    {'No.': 2, 'Employee ID': 'A0201', 'First Name': 'A Harisha', 'Gender': 'Female', 'Date': '2026-06-13', 'First Check In': '21:57', 'Last Check Out': None},
    {'No.': 3, 'Employee ID': 'A0201', 'First Name': 'A Harisha', 'Gender': 'Female', 'Date': '2026-06-14', 'First Check In': '06:03', 'Last Check Out': None},
])
res2, cols2 = proc.process_dataframe(df2)
print(f"  Rows after pairing: {len(res2)}")
for r in res2:
    print(f"  No.     raw: {r.get('No.')}")
    print(f"  Emp ID  raw: {r.get('Employee ID')}")
    print(f"  Name    raw: {r.get('First Name')}")
    print(f"  Date       : {r.get('attendance_date')}")
    print(f"  Logout Date: {r.get('Logout Date')}")
    print(f"  Shift      : {r.get('shift')}")
    print(f"  Checkout   : {r.get('last_check_out')}")
    print(f"  Checkout dt: {r.get('last_check_out_datetime')}")

print("\n=== Test 3: User Uploaded Excel Structure ===")
df3 = pd.DataFrame([
    {'NO.': 13879, 'EMPLOYEE ID': 'SGD1160', 'FIRST NAME': 'A Harisha', 'GENDER': 'Female', 'DATE': '2026-06-01', 'WEEKDAY': 'Monday', 'FIRST CHECK IN': '13:54', 'LAST CHECK OUT': '22:11', 'TOTAL TIME': '08:17'},
    {'NO.': 13881, 'EMPLOYEE ID': 'SGD1161', 'FIRST NAME': 'B Rajesh', 'GENDER': 'Male', 'DATE': '2026-06-02', 'WEEKDAY': 'Tuesday', 'FIRST CHECK IN': '05:57', 'LAST CHECK OUT': '14:13', 'TOTAL TIME': '08:16'}
])
res3, cols3 = proc.process_dataframe(df3)
print(f"  Final Columns: {cols3}")
for r in res3:
    print(f"  NO. raw: {r.get('NO.')} | EMP ID raw: {r.get('EMPLOYEE ID')} | NAME raw: {r.get('FIRST NAME')} | Logout Date: {r.get('Logout Date')}")

print("\nAll tests done!")
