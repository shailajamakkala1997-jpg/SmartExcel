import pandas as pd
from services.attendance_processor import AttendanceProcessor

proc = AttendanceProcessor()

print('=== Test: Multi-Date Chronological Output Sorting ===')

df_mixed = pd.DataFrame([
    {'EMPLOYEE ID': 'EMP001', 'FIRST NAME': 'Rahul', 'DATE': '2026-06-05', 'FIRST CHECK IN': '09:00', 'LAST CHECK OUT': '17:30'},
    {'EMPLOYEE ID': 'EMP001', 'FIRST NAME': 'Rahul', 'DATE': '2026-06-01', 'FIRST CHECK IN': '09:00', 'LAST CHECK OUT': '17:30'},
    {'EMPLOYEE ID': 'EMP001', 'FIRST NAME': 'Rahul', 'DATE': '2026-06-03', 'FIRST CHECK IN': '09:00', 'LAST CHECK OUT': '17:30'},
    {'EMPLOYEE ID': 'EMP001', 'FIRST NAME': 'Rahul', 'DATE': '2026-06-02', 'FIRST CHECK IN': '09:00', 'LAST CHECK OUT': '17:30'},
])

results, columns = proc.process_dataframe(df_mixed)

output_dates = [str(r.get('attendance_date')) for r in results]
print('Output Date Sequence:', output_dates)

expected = ['2026-06-01', '2026-06-02', '2026-06-03', '2026-06-05']
assert output_dates == expected, f'Expected {expected}, got {output_dates}'
print('PASSED! Multi-date output is sorted chronologically 100%!')