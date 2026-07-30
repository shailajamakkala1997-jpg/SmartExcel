import pandas as pd
from services.attendance_processor import AttendanceProcessor

proc = AttendanceProcessor()

print('=== Test: Unsorted Raw Excel Rows & Night Shift Pairing ===')

df_unsorted = pd.DataFrame([
    {'NO.': 102, 'EMPLOYEE ID': 'EMP001', 'FIRST NAME': 'Rahul Verma', 'DATE': '2026-06-14', 'FIRST CHECK IN': '06:15', 'LAST CHECK OUT': None},
    {'NO.': 101, 'EMPLOYEE ID': 'EMP001', 'FIRST NAME': 'Rahul Verma', 'DATE': '2026-06-13', 'FIRST CHECK IN': '21:55', 'LAST CHECK OUT': None},
])

results, columns = proc.process_dataframe(df_unsorted)

print('Total Output Rows after processing:', len(results))
for idx, r in enumerate(results, 1):
    print('Row', idx)
    print('  Emp ID      :', r.get('employee_id'))
    print('  Name        :', r.get('employee_name'))
    print('  Date        :', r.get('attendance_date'))
    print('  Check In    :', r.get('first_check_in'))
    print('  Logout Date :', r.get('Logout Date'))
    print('  Check Out   :', r.get('last_check_out'))
    print('  Shift       :', r.get('shift'))
    print('  Working Hrs :', r.get('working_hours'))
    print('  Status      :', r.get('status'))

assert len(results) == 1, f'Expected 1 paired row, got {len(results)}'
assert results[0]['shift'] == 'C', f'Expected Shift C, got {results[0][shift]}'
print('\nPASSED! Unsorted rows successfully sorted by sort_dt and paired cleanly!')