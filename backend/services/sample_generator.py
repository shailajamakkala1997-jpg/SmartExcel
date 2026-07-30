import pandas as pd
from io import BytesIO

def generate_sample_attendance_excel():
    """Generates sample raw attendance Excel file for testing."""
    sample_data = [
        {
            "First Name": "Kavitha",
            "Gender": "Female",
            "Date": "03-06-2026",
            "Weekday": "Wednesday",
            "First Check In": "21:52",
            "Last Check Out": "06:12",
            "Total Time": "--"
        },
        {
            "First Name": "Rajesh Kumar",
            "Gender": "Male",
            "Date": "03-06-2026",
            "Weekday": "Wednesday",
            "First Check In": "06:05",
            "Last Check Out": "14:10",
            "Total Time": "--"
        },
        {
            "First Name": "Priya Sharma",
            "Gender": "Female",
            "Date": "03-06-2026",
            "Weekday": "Wednesday",
            "First Check In": "14:15",
            "Last Check Out": "23:45",
            "Total Time": "--"
        },
        {
            "First Name": "Suresh Patel",
            "Gender": "Male",
            "Date": "03-06-2026",
            "Weekday": "Wednesday",
            "First Check In": "06:45",
            "Last Check Out": "14:00",
            "Total Time": "--"
        },
        {
            "First Name": "Anita Roy",
            "Gender": "Female",
            "Date": "03-06-2026",
            "Weekday": "Wednesday",
            "First Check In": "22:10",
            "Last Check Out": "",
            "Total Time": "--"
        },
        {
            "First Name": "Vikram Singh",
            "Gender": "Male",
            "Date": "03-06-2026",
            "Weekday": "Wednesday",
            "First Check In": "",
            "Last Check Out": "14:00",
            "Total Time": "--"
        },
        {
            "First Name": "Ananya Das",
            "Gender": "Female",
            "Date": "04-06-2026",
            "Weekday": "Thursday",
            "First Check In": "21:45",
            "Last Check Out": "06:00",
            "Total Time": "--"
        },
        {
            "First Name": "Arjun Nair",
            "Gender": "Male",
            "Date": "04-06-2026",
            "Weekday": "Thursday",
            "First Check In": "14:00",
            "Last Check Out": "22:15",
            "Total Time": "--"
        }
    ]

    df = pd.DataFrame(sample_data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Raw Attendance')
    output.seek(0)
    return output
