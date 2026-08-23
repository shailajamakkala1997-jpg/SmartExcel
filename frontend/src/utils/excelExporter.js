import * as XLSX from 'xlsx';

const getVal = (rec, key, defaultVal = '') => {
  if (!rec) return defaultVal;
  if (rec[key] !== undefined && rec[key] !== null && rec[key] !== '') return rec[key];

  const keyLower = String(key).toLowerCase().replace(/_/g, '').replace(/\./g, '').replace(/\s+/g, '');
  const mappings = {
    'no': ['NO.', 'No.', 'NO', 'No', 'S.No', 'Sl.No', 'raw_idx', '_rownum'],
    'empid': ['employee_id', 'EMPLOYEE ID', 'Emp ID', 'EMP ID', 'EMP CODE', 'Emp Code', 'Staff ID', 'User ID'],
    'employeename': ['employee_name', 'EMPLOYEE NAME', 'First Name', 'FIRST NAME', 'Name', 'NAME', 'Staff Name'],
    'gender': ['gender', 'GENDER', 'Gender', 'Sex'],
    'department': ['department', 'DEPARTMENT', 'Dept', 'DEPT'],
    'date': ['attendance_date', 'DATE', 'Date', 'Attendance Date'],
    'logoutdate': ['logout_date_str', 'logout_date', 'LOGOUT DATE', 'Logout Date', 'Check-Out Date'],
    'weekday': ['weekday', 'WEEKDAY', 'Day', 'DAY'],
    'shift': ['shift', 'Shift', 'SHIFT'],
    'firstcheckin': ['first_check_in', 'FIRST CHECK IN', 'First Check In', 'Check In', 'In Time'],
    'lastcheckout': ['last_check_out', 'LAST CHECK OUT', 'Last Check Out', 'Check Out', 'Out Time'],
    'singlepunch': ['SINGLE PUNCH', 'Single Punch', 'single_punch'],
    'workinghours': ['working_hours', 'WORKING HOURS', 'Working Hours', 'Total Time', 'TOTAL TIME'],
    'overtimehours': ['overtime_hours', 'OVERTIME HOURS', 'Overtime Hours', 'OT Hours', 'OT HOURS', 'Overtime'],
    'status': ['status', 'Status', 'STATUS'],
    'remarks': ['remarks', 'Remarks', 'REMARKS'],
  };

  if (mappings[keyLower]) {
    for (const candidate of mappings[keyLower]) {
      if (rec[candidate] !== undefined && rec[candidate] !== null && rec[candidate] !== '') {
        return rec[candidate];
      }
    }
  }

  for (const [k, v] of Object.entries(rec)) {
    const kClean = String(k).toLowerCase().replace(/_/g, '').replace(/\./g, '').replace(/\s+/g, '');
    if (kClean === keyLower && v !== undefined && v !== null && v !== '') {
      return v;
    }
  }

  return defaultVal;
};

const mapToDailyDetailRow = (rec, idx) => ({
  'NO.': idx + 1,
  'Emp ID': getVal(rec, 'employee_id', '--'),
  'Employee Name': getVal(rec, 'employee_name', '--'),
  'Department': getVal(rec, 'department', '--'),
  'Gender': getVal(rec, 'gender', '--'),
  'Day': getVal(rec, 'weekday', '--'),
  'Date': getVal(rec, 'attendance_date', '--'),
  'Shift': getVal(rec, 'shift', '--'),
  'Login': getVal(rec, 'first_check_in', '--'),
  'Logout Date': getVal(rec, 'logout_date', getVal(rec, 'attendance_date', '--')),
  'Logout': getVal(rec, 'last_check_out', '--'),
  'Working Hours': getVal(rec, 'working_hours', '00:00'),
  'Overtime Hours': getVal(rec, 'overtime_hours', '00:00'),
  'Status': getVal(rec, 'status', '--'),
  'Remarks': getVal(rec, 'remarks', ''),
});

const buildMonthlySummary = (records) => {
  const empMap = new Map();

  records.forEach(rec => {
    const empId = String(getVal(rec, 'employee_id', 'UNKNOWN')).trim();
    if (!empMap.has(empId)) {
      empMap.set(empId, {
        empId,
        name: getVal(rec, 'employee_name', '--'),
        dept: getVal(rec, 'department', '--'),
        gender: getVal(rec, 'gender', '--'),
        totalDays: 0,
        presentDays: 0,
        absentDays: 0,
        halfDays: 0,
        shiftA: 0,
        shiftGeneral: 0,
        shiftB: 0,
        shiftB1: 0,
        shiftC: 0,
        nmr: 0,
        totalWhMins: 0,
        totalOtMins: 0,
      });
    }

    const d = empMap.get(empId);
    d.totalDays += 1;

    const st = String(getVal(rec, 'status', '')).toLowerCase();
    const rem = String(getVal(rec, 'remarks', '')).toLowerCase();
    const sft = String(getVal(rec, 'shift', '')).toUpperCase();

    const isPresent = st.includes('present') || st.includes('short hours') || st.includes('full day') || st.includes('late') || st.includes('overtime');

    if (st.includes('absent')) {
      d.absentDays += 1;
    } else if (st.includes('half day')) {
      d.presentDays += 1;
      d.halfDays += 1;
    } else if (isPresent) {
      d.presentDays += 1;
    } else {
      d.absentDays += 1;
    }

    if (isPresent) {
      if (sft.includes('A') || sft === '1') d.shiftA += 1;
      else if (sft.includes('GEN') || sft === '4') d.shiftGeneral += 1;
      else if (sft.includes('B1') || sft === '5') d.shiftB1 += 1;
      else if (sft.includes('B') || sft === '2') d.shiftB += 1;
      else if (sft.includes('C') || sft.includes('NIGHT') || sft === '3') d.shiftC += 1;
    }

    if (st.includes('manual review') || rem.includes('manual review')) {
      d.nmr += 1;
    }

    // Working Hours Mins
    const whDec = Number(rec.working_hours_decimal || 0);
    if (whDec > 0) {
      d.totalWhMins += Math.round(whDec * 60);
    } else {
      const whStr = String(getVal(rec, 'working_hours', '00:00'));
      if (whStr.includes(':')) {
        const parts = whStr.split(':');
        d.totalWhMins += (parseInt(parts[0], 10) || 0) * 60 + (parseInt(parts[1], 10) || 0);
      }
    }

    // Overtime Mins
    const otDec = Number(rec.overtime_hours_decimal || 0);
    if (otDec > 0) {
      d.totalOtMins += Math.round(otDec * 60);
    } else {
      const otStr = String(getVal(rec, 'overtime_hours', '00:00'));
      if (otStr.includes(':')) {
        const parts = otStr.split(':');
        d.totalOtMins += (parseInt(parts[0], 10) || 0) * 60 + (parseInt(parts[1], 10) || 0);
      }
    }
  });

  const minsToHhmm = (mins) => {
    if (!mins || mins <= 0) return '00:00';
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  };

  return Array.from(empMap.values()).map(d => ({
    'Employee ID': d.empId,
    'First Name': d.name,
    'Gender': d.gender,
    'Total Days': d.totalDays,
    'Present Days': d.presentDays,
    'Absent Days': d.absentDays,
    'Half Days': d.halfDays,
    'Shift A Count': d.shiftA,
    'General Count': d.shiftGeneral,
    'Shift B Count': d.shiftB,
    'Shift B1 Count': d.shiftB1,
    'Shift C Count': d.shiftC,
    'Needs Manual Review Count': d.nmr,
    'Total Working Hours': minsToHhmm(d.totalWhMins),
    'Total Overtime Hours': minsToHhmm(d.totalOtMins),
  }));
};

export const exportToExcelClient = (records, scope = 'filtered', fileName = 'Attendance_Report.xlsx') => {
  const wb = XLSX.utils.book_new();

  // Sheet 1: Daily Detail
  const dailyDetailRows = records.map((rec, idx) => mapToDailyDetailRow(rec, idx));
  const ws1 = XLSX.utils.json_to_sheet(dailyDetailRows);

  ws1['!cols'] = [
    { wch: 6 },  // NO.
    { wch: 14 }, // Emp ID
    { wch: 25 }, // Employee Name
    { wch: 18 }, // Department
    { wch: 10 }, // Gender
    { wch: 12 }, // Day
    { wch: 14 }, // Date
    { wch: 10 }, // Shift
    { wch: 12 }, // Login
    { wch: 14 }, // Logout Date
    { wch: 12 }, // Logout
    { wch: 14 }, // Working Hours
    { wch: 14 }, // Overtime Hours
    { wch: 24 }, // Status
    { wch: 45 }, // Remarks
  ];

  XLSX.utils.book_append_sheet(wb, ws1, 'Daily Detail');

  // Sheet 2: Monthly Summary
  const summaryRows = buildMonthlySummary(records);
  const ws2 = XLSX.utils.json_to_sheet(summaryRows);
  ws2['!cols'] = [
    { wch: 14 }, { wch: 25 }, { wch: 10 }, { wch: 12 }, { wch: 12 },
    { wch: 12 }, { wch: 10 }, { wch: 12 }, { wch: 12 }, { wch: 12 },
    { wch: 12 }, { wch: 12 }, { wch: 22 }, { wch: 18 }, { wch: 18 }
  ];
  XLSX.utils.book_append_sheet(wb, ws2, 'Monthly Summary');

  // If full export, append Sheet 3: Manual Review
  if (scope === 'full') {
    const nmrRecords = records.filter(r => {
      const st = String(getVal(r, 'status', '')).toLowerCase();
      const rem = String(getVal(r, 'remarks', '')).toLowerCase();
      return st.includes('manual review') || rem.includes('manual review');
    });
    const nmrRows = nmrRecords.map((rec, idx) => mapToDailyDetailRow(rec, idx));
    const ws3 = XLSX.utils.json_to_sheet(nmrRows);
    ws3['!cols'] = ws1['!cols'];
    XLSX.utils.book_append_sheet(wb, ws3, 'Manual Review');
  }

  // Trigger instant client-side file download
  XLSX.writeFile(wb, fileName);
};
