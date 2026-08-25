import ExcelJS from 'exceljs';

// ── Value helper (unchanged logic) ────────────────────────────────────────
const getVal = (rec, key, defaultVal = '') => {
  if (!rec) return defaultVal;
  if (rec[key] !== undefined && rec[key] !== null && rec[key] !== '') return rec[key];

  const keyLower = String(key).toLowerCase().replace(/_/g, '').replace(/\./g, '').replace(/\s+/g, '');
  const mappings = {
    'no':            ['NO.', 'No.', 'NO', 'No', 'S.No', 'Sl.No', 'raw_idx', '_rownum'],
    'empid':         ['employee_id', 'EMPLOYEE ID', 'Emp ID', 'EMP ID', 'EMP CODE', 'Emp Code', 'Staff ID', 'User ID'],
    'employeename':  ['employee_name', 'EMPLOYEE NAME', 'First Name', 'FIRST NAME', 'Name', 'NAME', 'Staff Name'],
    'gender':        ['gender', 'GENDER', 'Gender', 'Sex'],
    'department':    ['department', 'DEPARTMENT', 'Dept', 'DEPT'],
    'date':          ['attendance_date', 'DATE', 'Date', 'Attendance Date'],
    'logoutdate':    ['logout_date_str', 'logout_date', 'LOGOUT DATE', 'Logout Date', 'Check-Out Date'],
    'weekday':       ['weekday', 'WEEKDAY', 'Day', 'DAY'],
    'shift':         ['shift', 'Shift', 'SHIFT'],
    'firstcheckin':  ['first_check_in', 'FIRST CHECK IN', 'First Check In', 'Check In', 'In Time'],
    'lastcheckout':  ['last_check_out', 'LAST CHECK OUT', 'Last Check Out', 'Check Out', 'Out Time'],
    'singlepunch':   ['SINGLE PUNCH', 'Single Punch', 'single_punch'],
    'workinghours':  ['working_hours', 'WORKING HOURS', 'Working Hours', 'Total Time', 'TOTAL TIME'],
    'overtimehours': ['overtime_hours', 'OVERTIME HOURS', 'Overtime Hours', 'OT Hours', 'OT HOURS', 'Overtime'],
    'status':        ['status', 'Status', 'STATUS'],
    'remarks':       ['remarks', 'Remarks', 'REMARKS'],
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
    if (kClean === keyLower && v !== undefined && v !== null && v !== '') return v;
  }

  return defaultVal;
};

// ── Style constants ────────────────────────────────────────────────────────
const THIN_BORDER = {
  top:    { style: 'thin', color: { argb: 'FFC0C8D4' } },
  left:   { style: 'thin', color: { argb: 'FFC0C8D4' } },
  bottom: { style: 'thin', color: { argb: 'FFC0C8D4' } },
  right:  { style: 'thin', color: { argb: 'FFC0C8D4' } },
};

const NRM_FONT = { name: 'Calibri', size: 10, color: { argb: 'FF1E293B' } };

// Status → ARGB font color (for Status + Remarks columns)
const getStatusColor = (status) => {
  const st = String(status || '').toLowerCase();
  if (st.includes('absent'))                                   return 'FFB91C1C'; // red
  if (st.includes('single punch'))                             return 'FFC2410C'; // orange
  if (st.includes('manual review') || st.includes('manual'))  return 'FFB45309'; // amber
  if (st.includes('half day'))                                 return 'FF1D4ED8'; // blue
  if (st.includes('overnight') || st.includes('c shift'))     return 'FF6D28D9'; // violet
  if (st.includes('present'))                                  return 'FF15803D'; // green
  return 'FF1E293B'; // default dark
};

// ── Daily Detail sheet writer ─────────────────────────────────────────────
const DETAIL_COLS = [
  { header: 'NO.',            key: '_rownum',         width: 6,  align: 'center' },
  { header: 'Emp ID',         key: 'employee_id',     width: 14, align: 'center' },
  { header: 'Employee Name',  key: 'employee_name',   width: 25, align: 'left'   },
  { header: 'Department',     key: 'department',      width: 18, align: 'left'   },
  { header: 'Gender',         key: 'gender',          width: 10, align: 'center' },
  { header: 'Day',            key: 'weekday',         width: 12, align: 'center' },
  { header: 'Date',           key: 'attendance_date', width: 14, align: 'center' },
  { header: 'Shift',          key: 'shift',           width: 10, align: 'center' },
  { header: 'Login',          key: 'first_check_in',  width: 12, align: 'center' },
  { header: 'Logout Date',    key: 'logout_date',     width: 14, align: 'center' },
  { header: 'Logout',         key: 'last_check_out',  width: 12, align: 'center' },
  { header: 'Working Hours',  key: 'working_hours',   width: 14, align: 'center' },
  { header: 'Overtime Hours', key: 'overtime_hours',  width: 14, align: 'center' },
  { header: 'Status',         key: 'status',          width: 26, align: 'left'   },
  { header: 'Remarks',        key: 'remarks',         width: 45, align: 'left'   },
];

const STATUS_COL_IDX  = DETAIL_COLS.findIndex(c => c.key === 'status')  + 1; // 14
const REMARKS_COL_IDX = DETAIL_COLS.findIndex(c => c.key === 'remarks') + 1; // 15

const writeDailyDetailSheet = (ws, records, hdrArgb = 'FF1E3A5F') => {
  // Column widths
  ws.columns = DETAIL_COLS.map(c => ({ header: c.header, key: c.key, width: c.width }));

  // Header row styling
  const hdrRow = ws.getRow(1);
  hdrRow.height = 22;
  hdrRow.eachCell((cell) => {
    cell.fill      = { type: 'pattern', pattern: 'solid', fgColor: { argb: hdrArgb } };
    cell.font      = { name: 'Calibri', size: 11, bold: true, color: { argb: 'FFFFFFFF' } };
    cell.alignment = { horizontal: 'center', vertical: 'middle' };
    cell.border    = THIN_BORDER;
  });

  // Freeze header
  ws.views = [{ state: 'frozen', ySplit: 1 }];

  records.forEach((rec, i) => {
    const rowNum    = i + 2;
    const isOdd     = rowNum % 2 === 0;
    const bgArgb    = isOdd ? 'FFF8FAFC' : 'FFFFFFFF';
    const status    = String(getVal(rec, 'status', ''));
    const statusArgb = getStatusColor(status);

    // Build row data
    const rowData = {};
    DETAIL_COLS.forEach((col) => {
      if (col.key === '_rownum') {
        rowData[col.key] = i + 1;
      } else {
        const v = getVal(rec, col.key, '--');
        rowData[col.key] = (v !== null && v !== undefined && v !== '') ? String(v) : '--';
      }
    });

    const row = ws.addRow(rowData);
    row.height = 19;

    row.eachCell({ includeEmpty: true }, (cell, colNumber) => {
      const colDef = DETAIL_COLS[colNumber - 1];

      // Background — always plain zebra
      cell.fill   = { type: 'pattern', pattern: 'solid', fgColor: { argb: bgArgb } };
      cell.border = THIN_BORDER;
      cell.alignment = {
        horizontal: colDef ? colDef.align : 'center',
        vertical: 'middle',
        wrapText: colNumber === REMARKS_COL_IDX,
      };

      // Font — colored only for Status + Remarks
      if (colNumber === STATUS_COL_IDX || colNumber === REMARKS_COL_IDX) {
        cell.font = { name: 'Calibri', size: 10, bold: true, color: { argb: statusArgb } };
      } else {
        cell.font = NRM_FONT;
      }
    });
  });
};

// ── Monthly Summary builder (unchanged logic) ─────────────────────────────
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
        totalDays: 0, presentDays: 0, absentDays: 0, halfDays: 0,
        shiftA: 0, shiftGeneral: 0, shiftB: 0, shiftB1: 0, shiftC: 0,
        nmr: 0, totalWhMins: 0, totalOtMins: 0,
      });
    }

    const d = empMap.get(empId);
    d.totalDays += 1;

    const st  = String(getVal(rec, 'status', '')).toLowerCase();
    const rem = String(getVal(rec, 'remarks', '')).toLowerCase();
    const sft = String(getVal(rec, 'shift', '')).toUpperCase();

    const isPresent = st.includes('present') || st.includes('short hours') ||
                      st.includes('full day') || st.includes('late') || st.includes('overtime');

    if (st.includes('absent'))       { d.absentDays  += 1; }
    else if (st.includes('half day')) { d.presentDays += 1; d.halfDays += 1; }
    else if (isPresent)               { d.presentDays += 1; }
    else                              { d.absentDays  += 1; }

    if (isPresent) {
      if      (sft.includes('A')   || sft === '1') d.shiftA       += 1;
      else if (sft.includes('GEN') || sft === '4') d.shiftGeneral += 1;
      else if (sft.includes('B1')  || sft === '5') d.shiftB1      += 1;
      else if (sft.includes('B')   || sft === '2') d.shiftB       += 1;
      else if (sft.includes('C')   || sft.includes('NIGHT') || sft === '3') d.shiftC += 1;
    }

    if (st.includes('manual review') || rem.includes('manual review')) d.nmr += 1;

    const whDec = Number(rec.working_hours_decimal || 0);
    if (whDec > 0) {
      d.totalWhMins += Math.round(whDec * 60);
    } else {
      const wh = String(getVal(rec, 'working_hours', '00:00'));
      if (wh.includes(':')) {
        const p = wh.split(':');
        d.totalWhMins += (parseInt(p[0], 10) || 0) * 60 + (parseInt(p[1], 10) || 0);
      }
    }

    const otDec = Number(rec.overtime_hours_decimal || 0);
    if (otDec > 0) {
      d.totalOtMins += Math.round(otDec * 60);
    } else {
      const ot = String(getVal(rec, 'overtime_hours', '00:00'));
      if (ot.includes(':')) {
        const p = ot.split(':');
        d.totalOtMins += (parseInt(p[0], 10) || 0) * 60 + (parseInt(p[1], 10) || 0);
      }
    }
  });

  const toHhmm = (mins) => {
    if (!mins || mins <= 0) return '00:00';
    return `${String(Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`;
  };

  return Array.from(empMap.values()).map(d => ({
    'Employee ID':               d.empId,
    'First Name':                d.name,
    'Gender':                    d.gender,
    'Total Days':                d.totalDays,
    'Present Days':              d.presentDays,
    'Absent Days':               d.absentDays,
    'Half Days':                 d.halfDays,
    'Shift A Count':             d.shiftA,
    'General Count':             d.shiftGeneral,
    'Shift B Count':             d.shiftB,
    'Shift B1 Count':            d.shiftB1,
    'Shift C Count':             d.shiftC,
    'Needs Manual Review Count': d.nmr,
    'Total Working Hours':       toHhmm(d.totalWhMins),
    'Total Overtime Hours':      toHhmm(d.totalOtMins),
  }));
};

// ── Monthly Summary sheet writer ───────────────────────────────────────────
const SUMMARY_COLS = [
  { header: 'Employee ID',               key: 'Employee ID',               width: 14, align: 'center' },
  { header: 'First Name',                key: 'First Name',                width: 25, align: 'left'   },
  { header: 'Gender',                    key: 'Gender',                    width: 10, align: 'center' },
  { header: 'Total Days',               key: 'Total Days',               width: 12, align: 'center' },
  { header: 'Present Days',             key: 'Present Days',             width: 12, align: 'center' },
  { header: 'Absent Days',              key: 'Absent Days',              width: 12, align: 'center' },
  { header: 'Half Days',                key: 'Half Days',                width: 10, align: 'center' },
  { header: 'Shift A Count',            key: 'Shift A Count',            width: 12, align: 'center' },
  { header: 'General Count',            key: 'General Count',            width: 12, align: 'center' },
  { header: 'Shift B Count',            key: 'Shift B Count',            width: 12, align: 'center' },
  { header: 'Shift B1 Count',           key: 'Shift B1 Count',           width: 12, align: 'center' },
  { header: 'Shift C Count',            key: 'Shift C Count',            width: 12, align: 'center' },
  { header: 'Needs Manual Review Count',key: 'Needs Manual Review Count',width: 22, align: 'center' },
  { header: 'Total Working Hours',      key: 'Total Working Hours',      width: 18, align: 'center' },
  { header: 'Total Overtime Hours',     key: 'Total Overtime Hours',     width: 18, align: 'center' },
];

const writeSummarySheet = (ws, records) => {
  ws.columns = SUMMARY_COLS.map(c => ({ header: c.header, key: c.key, width: c.width }));

  // Header — dark emerald
  const hdrRow = ws.getRow(1);
  hdrRow.height = 22;
  hdrRow.eachCell((cell) => {
    cell.fill      = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF14532D' } };
    cell.font      = { name: 'Calibri', size: 11, bold: true, color: { argb: 'FFFFFFFF' } };
    cell.alignment = { horizontal: 'center', vertical: 'middle' };
    cell.border    = THIN_BORDER;
  });
  ws.views = [{ state: 'frozen', ySplit: 1 }];

  const summaryRows = buildMonthlySummary(records);

  summaryRows.forEach((rowData, i) => {
    const rowNum = i + 2;
    const bgArgb = rowNum % 2 === 0 ? 'FFF8FAFC' : 'FFFFFFFF';
    const absentVal = Number(rowData['Absent Days'] || 0);
    const nmrVal    = Number(rowData['Needs Manual Review Count'] || 0);

    const row = ws.addRow(rowData);
    row.height = 19;

    SUMMARY_COLS.forEach((col, ci) => {
      const cell      = row.getCell(ci + 1);
      const colKey    = col.key;
      const isAbsent  = colKey === 'Absent Days';
      const isNmr     = colKey === 'Needs Manual Review Count';

      cell.fill      = { type: 'pattern', pattern: 'solid', fgColor: { argb: bgArgb } };
      cell.border    = THIN_BORDER;
      cell.alignment = { horizontal: col.align, vertical: 'middle' };

      if (isAbsent && absentVal > 0) {
        cell.font = { name: 'Calibri', size: 10, bold: true, color: { argb: 'FFB91C1C' } };
      } else if (isNmr && nmrVal > 0) {
        cell.font = { name: 'Calibri', size: 10, bold: true, color: { argb: 'FFB45309' } };
      } else {
        cell.font = NRM_FONT;
      }
    });
  });
};

// ── Main export function ───────────────────────────────────────────────────
export const exportToExcelClient = async (records, scope = 'filtered', fileName = 'Attendance_Report.xlsx') => {
  try {
    const workbook = new ExcelJS.Workbook();
    workbook.creator  = 'SmartExcel Attendance';
    workbook.created  = new Date();

    // Sheet 1 — Daily Detail
    const ws1 = workbook.addWorksheet('Daily Detail');
    writeDailyDetailSheet(ws1, records, 'FF1E3A5F');

    // Sheet 2 — Monthly Summary
    const ws2 = workbook.addWorksheet('Monthly Summary');
    writeSummarySheet(ws2, records);

    // Sheet 3 — Manual Review (full export only)
    if (scope === 'full') {
      const nmrRecords = records.filter(r => {
        const st  = String(getVal(r, 'status',  '')).toLowerCase();
        const rem = String(getVal(r, 'remarks', '')).toLowerCase();
        return st.includes('manual review') || rem.includes('manual review') || st.includes('single punch');
      });
      const ws3 = workbook.addWorksheet('Manual Review');
      writeDailyDetailSheet(ws3, nmrRecords, 'FF1E3A5F');
    }

    // Write buffer → Blob → download
    const buffer = await workbook.xlsx.writeBuffer();
    const blob   = new Blob([buffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    const url = URL.createObjectURL(blob);
    const a   = document.createElement('a');
    a.href     = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 2000);

  } catch (err) {
    console.error('[ExcelExporter] Export failed:', err);
    throw err;
  }
};
