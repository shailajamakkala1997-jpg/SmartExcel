import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Search, ChevronLeft, ChevronRight, CheckCircle2, AlertTriangle, AlertCircle, TrendingUp, X, Download, RefreshCw, Moon, Edit2, Trash2, Save } from 'lucide-react';
import axios from 'axios';

export default function AttendanceTable({
  records, columns, loading, searchTerm, setSearchTerm,
  selectedShift, setSelectedShift, selectedStatus, setSelectedStatus,
  selectedDept, setSelectedDept, onExport, activeFilterLabel,
  onUpdateRecord, onDeleteRecord
}) {
  const [currentPage, setCurrentPage] = useState(1);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [editingRecord, setEditingRecord] = useState(null);
  const [savingEdit, setSavingEdit] = useState(false);
  const searchContainerRef = useRef(null);
  const itemsPerPage = 15;


  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, selectedShift, selectedStatus, selectedDept, records?.length]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const suggestions = useMemo(() => {
    if (!searchTerm || !searchTerm.trim() || !records || records.length === 0) return [];
    const term = searchTerm.toLowerCase().trim();
    const map = new Map();

    records.forEach(r => {
      const name = r.employee_name || r['EMPLOYEE NAME'] || r['First Name'] || r['FIRST NAME'] || '';
      const empId = r.employee_id || r['EMPLOYEE ID'] || r['Emp ID'] || r['EMP CODE'] || '';

      if (name && String(name).toLowerCase().includes(term) && !map.has('name:' + name)) {
        map.set('name:' + name, { label: String(name), sub: empId ? 'ID: ' + empId : 'Employee', type: 'Name' });
      }
      if (empId && String(empId).toLowerCase().includes(term) && !map.has('id:' + empId)) {
        map.set('id:' + empId, { label: String(empId), sub: name ? 'Name: ' + name : 'Employee ID', type: 'ID' });
      }
    });

    return Array.from(map.values()).slice(0, 6);
  }, [records, searchTerm]);

  const defaultHeaders = ['Emp ID', 'Employee Name', 'Date', 'Shift', 'Check In', 'Check Out', 'SINGLE PUNCH', 'Working Hours', 'Overtime Hours', 'Status'];
  const rawHeaders = (columns && columns.length > 0) ? columns : defaultHeaders;
  const displayHeaders = useMemo(() => {
    const list = [...rawHeaders];

    const hasOT = list.some(h => {
      const hl = String(h).toLowerCase().replace(/_/g, '').replace(/\s+/g, '');
      return ['overtimehours', 'othours', 'overtime', 'ot'].includes(hl);
    });
    if (!hasOT) {
      const whIdx = list.findIndex(h => {
        const hl = String(h).toLowerCase().replace(/_/g, '').replace(/\s+/g, '');
        return ['workinghours', 'totaltime', 'totalhours'].includes(hl);
      });
      if (whIdx !== -1) {
        list.splice(whIdx + 1, 0, 'Overtime Hours');
      } else {
        list.push('Overtime Hours');
      }
    }

    const hasSP = list.some(h => {
      const hl = String(h).toLowerCase().replace(/_/g, '').replace(/\s+/g, '');
      return ['singlepunch', 'singlepunchtime', 'unpairedpunch'].includes(hl);
    });
    if (!hasSP) {
      const coIdx = list.findIndex(h => {
        const hl = String(h).toLowerCase().replace(/_/g, '').replace(/\s+/g, '');
        return ['lastcheckout', 'checkout', 'outtime'].includes(hl);
      });
      if (coIdx !== -1) {
        list.splice(coIdx + 1, 0, 'SINGLE PUNCH');
      } else {
        const ciIdx = list.findIndex(h => {
          const hl = String(h).toLowerCase().replace(/_/g, '').replace(/\s+/g, '');
          return ['firstcheckin', 'checkin', 'intime'].includes(hl);
        });
        if (ciIdx !== -1) {
          list.splice(ciIdx + 1, 0, 'SINGLE PUNCH');
        } else {
          list.push('SINGLE PUNCH');
        }
      }
    }

    if (!list.includes('Actions')) {
      list.push('Actions');
    }

    return list;
  }, [rawHeaders]);

  const handleStartEdit = (rec) => {
    const recId = rec.id !== undefined ? rec.id : rec.raw_idx;
    setEditingRecord({
      recId,
      id: rec.id,
      employee_name: rec.employee_name || rec['Employee Name'] || '',
      employee_id: rec.employee_id || rec['Emp ID'] || '',
      attendance_date: rec.attendance_date || rec['Date'] || '',
      first_check_in: rec.first_check_in || rec['FIRST CHECK IN'] || rec['Check In'] || '',
      last_check_out: rec.last_check_out || rec['LAST CHECK OUT'] || rec['Check Out'] || '',
      shift: rec.shift || rec['Shift'] || 'A',
      status: rec.status || rec['Status'] || 'Present (Full Day)',
      remarks: rec.remarks || rec['Remarks'] || ''
    });
  };

  const handleSaveEdit = async () => {
    if (!editingRecord) return;
    setSavingEdit(true);

    const checkIn = editingRecord.first_check_in && editingRecord.first_check_in !== '--' ? editingRecord.first_check_in : null;
    const checkOut = editingRecord.last_check_out && editingRecord.last_check_out !== '--' ? editingRecord.last_check_out : null;

    let working_hours = '--';
    let working_hours_decimal = 0.0;
    let overtime_hours = '00:00';
    let overtime_hours_decimal = 0.0;
    let is_overnight = false;

    if (checkIn && checkOut) {
      try {
        const [cinH, cinM] = checkIn.split(':').map(Number);
        const [coutH, coutM] = checkOut.split(':').map(Number);
        if (!isNaN(cinH) && !isNaN(coutH)) {
          let totalMins = (coutH * 60 + coutM) - (cinH * 60 + cinM);
          if (totalMins < 0) {
            totalMins += 24 * 60;
            is_overnight = true;
          }
          const h = Math.floor(totalMins / 60);
          const m = totalMins % 60;
          working_hours = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
          working_hours_decimal = Number((totalMins / 60).toFixed(2));
          if (totalMins > 480) {
            const otMins = totalMins - 480;
            const otH = Math.floor(otMins / 60);
            const otM = otMins % 60;
            overtime_hours = `${String(otH).padStart(2, '0')}:${String(otM).padStart(2, '0')}`;
            overtime_hours_decimal = Number((otMins / 60).toFixed(2));
          }
        }
      } catch (err) {
        console.warn('Working hours calculation error:', err);
      }
    }

    const payload = {
      first_check_in: checkIn || '--',
      last_check_out: checkOut || '--',
      'FIRST CHECK IN': checkIn || '--',
      'LAST CHECK OUT': checkOut || '--',
      shift: editingRecord.shift,
      Shift: editingRecord.shift,
      status: editingRecord.status,
      Status: editingRecord.status,
      remarks: editingRecord.remarks,
      Remarks: editingRecord.remarks,
      working_hours,
      'Working Hours': working_hours,
      working_hours_decimal,
      overtime_hours,
      'Overtime Hours': overtime_hours,
      overtime_hours_decimal,
      is_overnight
    };

    if (editingRecord.id !== undefined && editingRecord.id !== null) {
      try {
        await axios.put(`/api/attendance/${editingRecord.id}`, {
          first_check_in: checkIn,
          last_check_out: checkOut,
          shift: editingRecord.shift,
          status: editingRecord.status,
          remarks: editingRecord.remarks
        });
      } catch (err) {
        console.error('API update failed:', err);
      }
    }

    if (onUpdateRecord) {
      onUpdateRecord(editingRecord.recId, payload);
    }

    setSavingEdit(false);
    setEditingRecord(null);
  };

  const getStatusBadge = (status) => {
    const st = String(status || '').toLowerCase();
    if (st.includes('needs manual review') || st.includes('manual review')) return <span className="badge badge-manual-review"><AlertTriangle style={{ width: 8, height: 8 }} /> Needs Manual Review</span>;
    if (st.includes('present')) return <span className="badge badge-present"><CheckCircle2 style={{ width: 8, height: 8 }} /> Present</span>;
    if (st.includes('overtime')) return <span className="badge badge-overtime"><TrendingUp style={{ width: 8, height: 8 }} /> Overtime</span>;
    if (st.includes('late')) return <span className="badge badge-late"><AlertTriangle style={{ width: 8, height: 8 }} /> Late Login</span>;
    if (st.includes('missing logout')) return <span className="badge badge-missing"><AlertTriangle style={{ width: 8, height: 8 }} /> Missing Logout</span>;
    if (st.includes('missing login')) return <span className="badge badge-missing"><AlertCircle style={{ width: 8, height: 8 }} /> Missing Login</span>;
    if (st.includes('absent')) return <span className="badge badge-absent">Absent</span>;
    return <span className="badge badge-absent">{status || '--'}</span>;
  };

  const getShiftBadge = (shift) => {
    const s = String(shift || '').trim().toUpperCase();
    if (s === 'A' || s === '1') return <span className="badge badge-shift-a">Shift A</span>;
    if (s === 'GENERAL' || s === 'GEN' || s === '4') return <span className="badge badge-shift-gen">General</span>;
    if (s === 'B' || s === '2') return <span className="badge badge-shift-b">Shift B</span>;
    if (s === 'B1' || s === '5') return <span className="badge badge-shift-b1">Shift B1</span>;
    if (s === 'B+C' || s === 'B + C' || s === 'BC') return <span className="badge badge-shift-b1" style={{ background: '#6D28D9', color: '#FFFFFF', border: '1px solid #5B21B6', fontWeight: 800 }}><Moon style={{ width: 8, height: 8 }} /> Shift B+C</span>;
    if (s === 'A+B' || s === 'A + B' || s === 'AB') return <span className="badge badge-shift-a" style={{ background: '#D97706', color: '#FFFFFF', border: '1px solid #B45309', fontWeight: 800 }}>Shift A+B</span>;
    if (s === 'C' || s === '3' || s === 'NIGHT') return <span className="badge badge-shift-c"><Moon style={{ width: 8, height: 8 }} /> Shift C</span>;
    return <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{shift && shift !== 'None' && shift !== 'Unknown' ? shift : '--'}</span>;
  };


  const renderCell = (rec, colName) => {
    const colLower = String(colName || '').toLowerCase().trim();
    if (colLower === 'actions') {
      const recordId = rec.id !== undefined ? rec.id : rec.raw_idx;
      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button
            onClick={() => handleStartEdit(rec)}
            style={{ padding: '4px 8px', background: '#F0F9F3', border: '1px solid #B3E6C4', borderRadius: 4, color: '#00873D', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 700 }}
            title="Edit Record"
            id={`edit-rec-${recordId}`}
          >
            <Edit2 style={{ width: 12, height: 12 }} /> Edit
          </button>
          {onDeleteRecord && (
            <button
              onClick={() => onDeleteRecord(recordId)}
              style={{ padding: '4px 6px', background: '#FEE2E2', border: '1px solid #FECACA', borderRadius: 4, color: '#991B1B', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}
              title="Delete Record"
              id={`del-rec-${recordId}`}
            >
              <Trash2 style={{ width: 12, height: 12 }} />
            </button>
          )}
        </div>
      );
    }
    if (colLower === 'status' || colLower === 'day status' || colLower === 'day_status') {
      const statusVal = rec.status || rec.Status || rec.STATUS || rec[colName];
      return getStatusBadge(statusVal);
    }
    if (colLower === 'shift' || colLower === 'shifts' || colLower === 'shift name' || colLower === 'shift_name') {
      const shiftVal = rec.shift || rec.Shift || rec.SHIFTS || rec.shifts || rec[colName];
      return getShiftBadge(shiftVal);
    }
    if (['punch status', 'punch_status', 'missing shift details', 'missing_shift_details'].includes(colLower)) {
      const ps = rec['PUNCH STATUS'] || rec.punch_status || rec['Punch Status'] || rec['MISSING SHIFT DETAILS'] || rec[colName];
      if (ps && String(ps).toLowerCase().includes('manual review')) {
        return <span className="badge badge-manual-review">{ps}</span>;
      }
      if (ps && ps !== 'Normal' && ps !== '--') {
        return <span className="badge badge-punch-status">{ps}</span>;
      }
      return <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{ps || 'Normal'}</span>;
    }
    if (colLower === 'working hours' || colLower === 'working_hours' || colLower === 'total working hours')
      return <span className="mono-cell" style={{ color: '#00873D', fontWeight: 700 }}>{rec.working_hours || rec['Working Hours'] || rec[colName] || '00:00'}</span>;
    if (['overtime hours', 'overtime_hours', 'overtime', 'ot hours', 'ot', 'overtimehours'].includes(colLower)) {
      const candidates = [
        rec.overtime_hours,
        rec['Overtime Hours'],
        rec['OVERTIME HOURS'],
        rec['OT Hours'],
        rec.overtime,
        rec[colName]
      ];
      const otVal = candidates.find(v => v && v !== '00:00' && v !== '--' && v !== '0') || candidates.find(v => v !== undefined && v !== null && v !== '') || '00:00';
      const isPositive = otVal && otVal !== '00:00' && otVal !== '--' && otVal !== '0';
      return (
        <span className="mono-cell" style={{ color: isPositive ? '#D97706' : 'var(--text-muted)', fontWeight: isPositive ? 700 : 400 }}>
          {otVal}
        </span>
      );
    }
    if (['check out', 'checkout', 'last check out', 'out time', 'c shift exit'].includes(colLower)) {
      const outVal = rec.c_shift_exit || rec.last_check_out || rec[colName] || '--';
      return <span className="mono-cell">{outVal && outVal !== 'None' ? outVal : '--'}</span>;
    }
    if (['single punch', 'single_punch', 'singlepunch', 'single punch time', 'unpaired punch'].includes(colLower)) {
      const spVal = rec['SINGLE PUNCH'] || rec.single_punch || rec['Single Punch'] || rec[colName] || '--';
      const isPresent = spVal && spVal !== '--' && spVal !== 'None' && spVal !== 'null';
      return (
        <span className="mono-cell" style={{ color: isPresent ? '#7C3AED' : 'var(--text-muted)', fontWeight: isPresent ? 700 : 400 }}>
          {isPresent ? spVal : '--'}
        </span>
      );
    }
    if (['logout date', 'logout_date', 'check-out date', 'checkout date'].includes(colLower)) {
      const dv = rec.logout_date_str || rec.logout_date || rec['Logout Date'] || rec[colName] || '--';
      return <span className="mono-cell">{dv && dv !== 'None' ? dv : '--'}</span>;
    }
    if (['check in', 'checkin', 'first check in', 'in time'].includes(colLower))
      return <span className="mono-cell">{rec.first_check_in || rec[colName] || '--'}</span>;
    if (['date', 'attendance_date'].includes(colLower))
      return <span className="mono-cell">{rec.attendance_date || rec[colName] || '--'}</span>;
    if (['no.', 'no', 'sl no', 'sl.no', 's.no', 'sr no'].includes(colLower)) {
      const v = rec['NO.'] ?? rec[colName] ?? rec['No.'] ?? '--';
      return <span className="mono-cell" style={{ color: 'var(--text-muted)' }}>{v}</span>;
    }
    let val = rec[colName];
    if (val === undefined || val === null || val === '') {
      const mk = Object.keys(rec).find(k => k.toLowerCase() === colLower);
      if (mk) val = rec[mk];
    }
    if (val === undefined || val === null || val === '') return <span style={{ color: 'var(--text-muted)' }}>--</span>;
    return String(val);
  };

  const totalPages = Math.ceil((records?.length || 0) / itemsPerPage) || 1;
  const paginatedRecords = (records || []).slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);
  const hasActiveFilters = searchTerm || selectedShift !== 'ALL' || selectedStatus !== 'ALL' || selectedDept !== 'ALL';

  const resetFilters = () => {
    setSearchTerm(''); setSelectedShift('ALL'); setSelectedStatus('ALL'); setSelectedDept('ALL');
  };

  return (
    <div className="panel-raised fade-up" style={{ borderRadius: 14 }}>
      {/* Ribbon / Toolbar */}
      <div style={{ padding: '14px 18px', background: '#F3F9F4', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <div ref={searchContainerRef} style={{ position: 'relative' }}>
            <Search style={{ width: 14, height: 14, color: '#009E49', position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }} />
            <input
              type="text"
              placeholder="Search employee, ID, date, status..."
              value={searchTerm}
              onChange={e => {
                setSearchTerm(e.target.value);
                setShowSuggestions(true);
              }}
              onFocus={() => setShowSuggestions(true)}
              className="input-enterprise"
              style={{ paddingLeft: 32, width: 290 }}
              id="search-input"
            />

            {/* Suggestions Popup */}
            {showSuggestions && suggestions.length > 0 && (
              <div style={{
                position: 'absolute', top: 'calc(100% + 4px)', left: 0, width: '100%',
                background: '#FFFFFF', border: '1px solid #009E49',
                borderRadius: 8, boxShadow: '0 8px 24px rgba(0,158,73,0.15)', zIndex: 50,
                overflow: 'hidden'
              }}>
                <div style={{ padding: '6px 10px', fontSize: 10, fontWeight: 700, color: '#00873D', textTransform: 'uppercase', borderBottom: '1px solid #E2EDE5', background: '#E2F5E8' }}>
                  Matching Suggestions ({suggestions.length})
                </div>
                {suggestions.map((s, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setSearchTerm(s.label);
                      setShowSuggestions(false);
                    }}
                    style={{
                      width: '100%', padding: '8px 12px', textAlign: 'left', background: 'none',
                      border: 'none', borderBottom: idx === suggestions.length - 1 ? 'none' : '1px solid #E2EDE5',
                      cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between'
                    }}
                    className="hover:bg-emerald-50 transition-colors"
                  >
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: '#0A2113' }}>{s.label}</div>
                      <div style={{ fontSize: 10, color: '#556C5D' }}>{s.sub}</div>
                    </div>
                    <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 4, background: '#E2F5E8', color: '#00873D', textTransform: 'uppercase' }}>
                      {s.type}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {hasActiveFilters && (
            <button onClick={resetFilters} className="btn-ghost" id="reset-filters" style={{ padding: '8px 14px' }}>
              <X style={{ width: 12, height: 12 }} /> Reset Filters
            </button>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 11, color: '#2C4234', fontWeight: 700 }}>
            {records?.length || 0} rows displayed
          </span>
          {onExport && records && records.length > 0 && (
            <button
              onClick={() => onExport('filtered')}
              className="btn-export"
              id="export-xlsx-btn"
              title={activeFilterLabel ? `Export only "${activeFilterLabel}" records (${records.length} rows)` : 'Download filtered records'}
              style={activeFilterLabel ? {
                background: '#005F2B',
                border: '2px solid #69F0AE',
                boxShadow: '0 0 0 3px rgba(105,240,174,0.2)'
              } : {}}
            >
              <Download style={{ width: 12, height: 12 }} />
              {activeFilterLabel ? `Export: ${activeFilterLabel}` : 'Export Filtered XLSX'}
              {activeFilterLabel && (
                <span style={{
                  marginLeft: 4, fontSize: 9, fontWeight: 800,
                  background: 'rgba(255,255,255,0.25)', borderRadius: 4,
                  padding: '1px 5px', letterSpacing: '0.04em'
                }}>
                  {records.length} rows
                </span>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Mini Excel Sheet Grid */}
      <div style={{ overflowX: 'auto' }}>
        <table className="enterprise-table">
          <thead>
            <tr>
              {displayHeaders.map((h, i) => <th key={i}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={displayHeaders.length} style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-muted)' }}>
                  <RefreshCw style={{ width: 18, height: 18, display: 'inline', marginRight: 8, color: '#009E49' }} className="spin" />
                  Processing attendance data...
                </td>
              </tr>
            ) : paginatedRecords.length === 0 ? (
              <tr>
                <td colSpan={displayHeaders.length} style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-muted)', fontSize: 12 }}>
                  No rows match the current filters.
                </td>
              </tr>
            ) : (
              paginatedRecords.map((rec, idx) => (
                <tr key={rec.id ?? (rec.employee_id + '-' + rec.attendance_date + '-' + idx)}>
                  {displayHeaders.map((col, ci) => (
                    <td key={ci}>{renderCell(rec, col)}</td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Sheet Pagination */}
      <div style={{ padding: '12px 18px', background: '#F3F9F4', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 11, color: '#556C5D', fontWeight: 600 }}>
          Showing {Math.min((currentPage - 1) * itemsPerPage + 1, records?.length || 0)}&#8211;{Math.min(currentPage * itemsPerPage, records?.length || 0)} of {records?.length || 0}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button className="page-btn" onClick={() => setCurrentPage(p => Math.max(p - 1, 1))} disabled={currentPage === 1} id="prev-page">
            <ChevronLeft style={{ width: 13, height: 13 }} />
          </button>
          <span style={{ fontSize: 11, color: '#0A2113', fontWeight: 700, minWidth: 80, textAlign: 'center' }}>
            Page {currentPage} / {totalPages}
          </span>
          <button className="page-btn" onClick={() => setCurrentPage(p => Math.min(p + 1, totalPages))} disabled={currentPage === totalPages} id="next-page">
            <ChevronRight style={{ width: 13, height: 13 }} />
          </button>
        </div>
      </div>

      {/* Edit Record Modal */}
      {editingRecord && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 70,
            background: 'rgba(10, 33, 19, 0.65)', backdropFilter: 'blur(4px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20
          }}
          onClick={e => { if (e.target === e.currentTarget) setEditingRecord(null); }}
        >
          <div style={{ width: '100%', maxWidth: 500, background: '#FFFFFF', borderRadius: 12, border: '1px solid #009E49', boxShadow: '0 20px 40px rgba(0,158,73,0.2)', overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', background: '#009E49', color: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ fontSize: 14, fontWeight: 800 }}>Edit Live Attendance Record</div>
              <button onClick={() => setEditingRecord(null)} style={{ background: 'none', border: 'none', color: '#FFFFFF', cursor: 'pointer' }} id="close-edit-modal">
                <X style={{ width: 16, height: 16 }} />
              </button>
            </div>
            <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#0A2113', padding: '8px 12px', background: '#F0F9F3', borderRadius: 6, border: '1px solid #B3E6C4' }}>
                {editingRecord.employee_name} ({editingRecord.employee_id}) &bull; {editingRecord.attendance_date}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 11, fontWeight: 700, color: '#556C5D', display: 'block', marginBottom: 4 }}>Check In (HH:MM)</label>
                  <input type="text" className="input-enterprise" value={editingRecord.first_check_in} onChange={e => setEditingRecord({ ...editingRecord, first_check_in: e.target.value })} id="edit-checkin" />
                </div>
                <div>
                  <label style={{ fontSize: 11, fontWeight: 700, color: '#556C5D', display: 'block', marginBottom: 4 }}>Check Out (HH:MM)</label>
                  <input type="text" className="input-enterprise" value={editingRecord.last_check_out} onChange={e => setEditingRecord({ ...editingRecord, last_check_out: e.target.value })} id="edit-checkout" />
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 11, fontWeight: 700, color: '#556C5D', display: 'block', marginBottom: 4 }}>Shift</label>
                  <select className="input-enterprise" value={editingRecord.shift} onChange={e => setEditingRecord({ ...editingRecord, shift: e.target.value })} id="edit-shift">
                    <option value="A">Shift A (06:00 - 14:00)</option>
                    <option value="General">General (09:00 - 17:30)</option>
                    <option value="B">Shift B (14:00 - 22:00)</option>
                    <option value="B1">Shift B1 (17:30 - 06:00)</option>
                    <option value="C">Shift C (22:00 - 06:00)</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 11, fontWeight: 700, color: '#556C5D', display: 'block', marginBottom: 4 }}>Status</label>
                  <select className="input-enterprise" value={editingRecord.status} onChange={e => setEditingRecord({ ...editingRecord, status: e.target.value })} id="edit-status">
                    <option value="Present (Full Day)">Present (Full Day)</option>
                    <option value="Present (Half Day)">Present (Half Day)</option>
                    <option value="Late Login">Late Login</option>
                    <option value="Short Hours">Short Hours</option>
                    <option value="Needs Manual Review">Needs Manual Review</option>
                    <option value="Absent">Absent</option>
                  </select>
                </div>
              </div>
              <div>
                <label style={{ fontSize: 11, fontWeight: 700, color: '#556C5D', display: 'block', marginBottom: 4 }}>Remarks</label>
                <input type="text" className="input-enterprise" value={editingRecord.remarks} onChange={e => setEditingRecord({ ...editingRecord, remarks: e.target.value })} id="edit-remarks" />
              </div>
            </div>
            <div style={{ padding: '12px 18px', background: '#F8FAF7', borderTop: '1px solid #E2EDE5', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button onClick={() => setEditingRecord(null)} className="btn-ghost" id="cancel-edit-btn">Cancel</button>
              <button onClick={handleSaveEdit} disabled={savingEdit} className="btn-primary" id="save-edit-btn">
                {savingEdit ? <RefreshCw className="spin" style={{ width: 14, height: 14 }} /> : <Save style={{ width: 14, height: 14 }} />}
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}