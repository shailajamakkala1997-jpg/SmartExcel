import pandas as pd
from services.attendance_processor import AttendanceProcessor

proc = AttendanceProcessor()

if __name__ == "__main__":
    print('=== Test: User Screenshots Fixes Verification ===')

    df_shifts = pd.DataFrame([
        {'EMPLOYEE ID': 'EMP1', 'FIRST NAME': 'Anil', 'DATE': '2026-06-07', 'FIRST CHECK IN': '05:55', 'LAST CHECK OUT': '14:16'},
        {'EMPLOYEE ID': 'EMP1', 'FIRST NAME': 'Anil', 'DATE': '2026-06-15', 'FIRST CHECK IN': '21:53', 'LAST CHECK OUT': '06:12'},
    ])

    results_shifts, _ = proc.process_dataframe(df_shifts)
    print('Shift Results:')
    for r in results_shifts:
        print(r.get('attendance_date'), r.get('first_check_in'), r.get('shift'))

    shift_0555 = next(r.get('shift') for r in results_shifts if '05:55' in str(r.get('first_check_in')))
    shift_2153 = next(r.get('shift') for r in results_shifts if '21:53' in str(r.get('first_check_in')))

    assert shift_0555 == 'A', f'Expected 05:55 AM check-in to be Shift A, got {shift_0555}'
    assert shift_2153 in ('C', 'B1'), f'Expected 21:53 PM check-in to be overnight shift, got {shift_2153}'
    print('PASSED: Shift A (05:55 AM) & Shift B1/C (21:53 PM) classified 100% correctly!')

df_short_dates = pd.DataFrame([
    {'EMPLOYEE ID': 'E1', 'FIRST NAME': 'User', 'DATE': '06-03', 'FIRST CHECK IN': '09:00', 'LAST CHECK OUT': '17:00'},
    {'EMPLOYEE ID': 'E1', 'FIRST NAME': 'User', 'DATE': '06-19', 'FIRST CHECK IN': '09:00', 'LAST CHECK OUT': '17:00'},
    {'EMPLOYEE ID': 'E1', 'FIRST NAME': 'User', 'DATE': '06-11', 'FIRST CHECK IN': '09:00', 'LAST CHECK OUT': '17:00'},
    {'EMPLOYEE ID': 'E1', 'FIRST NAME': 'User', 'DATE': '06-01', 'FIRST CHECK IN': '09:00', 'LAST CHECK OUT': '17:00'},
    {'EMPLOYEE ID': 'E1', 'FIRST NAME': 'User', 'DATE': '06-23', 'FIRST CHECK IN': '09:00', 'LAST CHECK OUT': '17:00'},
    {'EMPLOYEE ID': 'E1', 'FIRST NAME': 'User', 'DATE': '06-07', 'FIRST CHECK IN': '09:00', 'LAST CHECK OUT': '17:00'},
    {'EMPLOYEE ID': 'E1', 'FIRST NAME': 'User', 'DATE': '06-15', 'FIRST CHECK IN': '09:00', 'LAST CHECK OUT': '17:00'},
    {'EMPLOYEE ID': 'E1', 'FIRST NAME': 'User', 'DATE': '06-06', 'FIRST CHECK IN': '09:00', 'LAST CHECK OUT': '17:00'},
    {'EMPLOYEE ID': 'E1', 'FIRST NAME': 'User', 'DATE': '06-25', 'FIRST CHECK IN': '09:00', 'LAST CHECK OUT': '17:00'},
])

results_dates, _ = proc.process_dataframe(df_short_dates)
output_short_dates = [str(r.get('attendance_date')) for r in results_dates]
print('Short Dates Sorted Output:', output_short_dates)

day_numbers = [int(str(d).split('-')[-1]) for d in output_short_dates]
print('Extracted Day Numbers:', day_numbers)
assert day_numbers == sorted(day_numbers), f'Expected sorted day numbers, got {day_numbers}'
print('PASSED: Short date strings sorted in strict numerical order!')
