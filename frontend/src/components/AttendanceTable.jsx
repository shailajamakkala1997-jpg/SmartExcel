import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Search, ChevronLeft, ChevronRight, CheckCircle2, AlertTriangle, AlertCircle, TrendingUp, X, Download, RefreshCw, Moon } from 'lucide-react';

export default function AttendanceTable({
  records, columns, loading, searchTerm, setSearchTerm,
  selectedShift, setSelectedShift, selectedStatus, setSelectedStatus,
  selectedDept, setSelectedDept, onExport
}) {
  const [currentPage, setCurrentPage] = useState(1);
  const [showSuggestions, setShowSuggestions] = useState(false);
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

  const defaultHeaders = ['Emp ID', 'Employee Name', 'Date', 'Shift', 'Check In', 'Check Out', 'Working Hours', 'Status'];
  const displayHeaders = (columns && columns.length > 0) ? columns : defaultHeaders;

  const getStatusBadge = (status) => {
    const st = String(status || '').toLowerCase();
    if (st.includes('present'))        return <span className="badge badge-present"><CheckCircle2 style={{width:8,height:8}} /> Present</span>;
    if (st.includes('overtime'))       return <span className="badge badge-overtime"><TrendingUp style={{width:8,height:8}} /> Overtime</span>;
    if (st.includes('late'))           return <span className="badge badge-late"><AlertTriangle style={{width:8,height:8}} /> Late Login</span>;
    if (st.includes('missing logout')) return <span className="badge badge-missing"><AlertTriangle style={{width:8,height:8}} /> Missing Logout</span>;
    if (st.includes('missing login'))  return <span className="badge badge-missing"><AlertCircle style={{width:8,height:8}} /> Missing Login</span>;
    if (st.includes('absent'))         return <span className="badge badge-absent">Absent</span>;
    return <span className="badge badge-absent">{status || '--'}</span>;
  };

  const getShiftBadge = (shift) => {
    if (shift === 'A') return <span className="badge badge-shift-a">Shift A</span>;
    if (shift === 'B') return <span className="badge badge-shift-b">Shift B</span>;
    if (shift === 'C') return <span className="badge badge-shift-c"><Moon style={{width:8,height:8}} /> Shift C</span>;
    return <span style={{color:'var(--text-muted)',fontSize:11}}>--</span>;
  };

  const renderCell = (rec, colName) => {
    const colLower = String(colName || '').toLowerCase().trim();
    if (colLower === 'status')      return getStatusBadge(rec.status);
    if (colLower === 'shift')       return getShiftBadge(rec.shift);
    if (colLower === 'working hours' || colLower === 'working_hours')
      return <span className="mono-cell" style={{color:'#00873D',fontWeight:700}}>{rec.working_hours || '00:00'}</span>;
    if (['check out','checkout','last check out','out time'].includes(colLower))
      return <span className="mono-cell">{rec.last_check_out || rec[colName] || '--'}</span>;
    if (['logout date','logout_date','check-out date','checkout date'].includes(colLower)) {
      const dv = rec.logout_date_str || rec.logout_date || rec['Logout Date'] || rec[colName] || '--';
      return <span className="mono-cell">{dv && dv !== 'None' ? dv : '--'}</span>;
    }
    if (['check in','checkin','first check in','in time'].includes(colLower))
      return <span className="mono-cell">{rec.first_check_in || rec[colName] || '--'}</span>;
    if (['date','attendance_date'].includes(colLower))
      return <span className="mono-cell">{rec.attendance_date || rec[colName] || '--'}</span>;
    if (['no.','no','sl no','sl.no','s.no','sr no'].includes(colLower)) {
      const v = rec[colName] ?? rec['NO.'] ?? rec['No.'] ?? '--';
      return <span className="mono-cell" style={{color:'var(--text-muted)'}}>{v}</span>;
    }
    let val = rec[colName];
    if (val === undefined || val === null || val === '') {
      const mk = Object.keys(rec).find(k => k.toLowerCase() === colLower);
      if (mk) val = rec[mk];
    }
    if (val === undefined || val === null || val === '') return <span style={{color:'var(--text-muted)'}}>--</span>;
    return String(val);
  };

  const totalPages = Math.ceil((records?.length || 0) / itemsPerPage) || 1;
  const paginatedRecords = (records || []).slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);
  const hasActiveFilters = searchTerm || selectedShift !== 'ALL' || selectedStatus !== 'ALL' || selectedDept !== 'ALL';

  const resetFilters = () => {
    setSearchTerm(''); setSelectedShift('ALL'); setSelectedStatus('ALL'); setSelectedDept('ALL');
  };

  return (
    <div className="panel-raised fade-up" style={{borderRadius: 14, overflow: 'hidden'}}>
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
            <button onClick={resetFilters} className="btn-ghost" id="reset-filters" style={{padding:'8px 14px'}}>
              <X style={{width:12,height:12}} /> Reset Filters
            </button>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 11, color: '#2C4234', fontWeight: 700 }}>
            {records?.length || 0} rows displayed
          </span>
          {onExport && records && records.length > 0 && (
            <button onClick={() => onExport('filtered')} className="btn-export" id="export-xlsx-btn" title="Download only the currently filtered records">
              <Download style={{width:12,height:12}} /> Export Filtered XLSX
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
            <ChevronLeft style={{width:13,height:13}} />
          </button>
          <span style={{ fontSize: 11, color: '#0A2113', fontWeight: 700, minWidth: 80, textAlign: 'center' }}>
            Page {currentPage} / {totalPages}
          </span>
          <button className="page-btn" onClick={() => setCurrentPage(p => Math.min(p + 1, totalPages))} disabled={currentPage === totalPages} id="next-page">
            <ChevronRight style={{width:13,height:13}} />
          </button>
        </div>
      </div>
    </div>
  );
}