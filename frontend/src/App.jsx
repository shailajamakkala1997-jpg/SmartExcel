import React, { useState, useMemo } from 'react';
import Navbar from './components/Navbar';
import SummaryCards from './components/SummaryCards';
import AttendanceTable from './components/AttendanceTable';
import UploadModal from './components/UploadModal';
import axios from 'axios';
import { Upload, FileSpreadsheet, ArrowRight, CheckCircle2, RefreshCw, X } from 'lucide-react';
import { exportToExcelClient } from './utils/excelExporter';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [userRole, setUserRole] = useState('Admin');
  const [darkMode, setDarkMode] = useState(true);
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  // In-Memory Data States
  const [allProcessedRecords, setAllProcessedRecords] = useState([]);
  const [excelColumns, setExcelColumns] = useState([]);
  const [uploadedFileName, setUploadedFileName] = useState('');
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportToast, setExportToast] = useState(null);

  // Filters State
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedShift, setSelectedShift] = useState('ALL');
  const [selectedStatus, setSelectedStatus] = useState('ALL');
  const [selectedDept, setSelectedDept] = useState('ALL');

  const handleUploadSuccess = (data) => {
    if (data && data.records) {
      setAllProcessedRecords(data.records);
      const cleanCols = (data.columns || []).filter(c => {
        const cClean = String(c).toLowerCase().replace(/_/g, '').replace(/\./g, '').replace(/\s+/g, '').trim();
        return !['totaltime', 'totalhours', 'totalhrs'].includes(cClean);
      });
      setExcelColumns(cleanCols);
      setUploadedFileName(data.filename || 'Uploaded File');
    }
  };

  // Compute filtered records in memory
  const filteredRecords = useMemo(() => {
    return allProcessedRecords.filter(r => {
      if (searchTerm) {
        const term = searchTerm.toLowerCase().trim();
        const matchesAnyField = Object.values(r).some(val => 
          val !== null && val !== undefined && String(val).toLowerCase().includes(term)
        );
        if (!matchesAnyField) return false;
      }
      if (selectedShift !== 'ALL' && r.shift !== selectedShift) return false;
      if (selectedDept !== 'ALL' && r.department !== selectedDept) return false;

      if (selectedStatus !== 'ALL') {
        if (selectedStatus === 'Present') {
          const st = String(r.status || '');
          if (!st.includes('Present') && !st.includes('Full Day') && !st.includes('Half Day') && !st.includes('Overtime') && !st.includes('Late') && !st.includes('Short Hours')) return false;
        } else if (selectedStatus === 'Late Login') {
          if (r.status !== 'Late Login' && !(r.remarks && String(r.remarks).includes('Late'))) return false;
        } else if (selectedStatus === 'Overtime') {
          const otStr = r.overtime_hours || r['Overtime Hours'] || r['OVERTIME HOURS'] || r.overtime || '';
          const otDec = Number(r.overtime_hours_decimal || 0);
          const whDec = Number(r.working_hours_decimal || 0);
          const isOtTime = otStr && otStr !== '00:00' && otStr !== '--' && otStr !== '0';
          if (!isOtTime && otDec <= 0 && whDec <= 8.0 && r.status !== 'Overtime' && !(r.remarks && String(r.remarks).includes('Overtime'))) return false;
        } else if (selectedStatus === 'Needs Manual Review') {
          const st = String(r.status || '').toLowerCase();
          const rem = String(r.remarks || '').toLowerCase();
          if (!st.includes('manual review') && !rem.includes('manual review')) return false;
        } else {
          if (r.status !== selectedStatus) return false;
        }
      }
      return true;
    });
  }, [allProcessedRecords, searchTerm, selectedShift, selectedStatus, selectedDept]);

  // Active KPI card highlighting
  const activeKpiFilter = useMemo(() => {
    if (selectedShift === 'A') return 'Shift A';
    if (selectedShift === 'General') return 'General';
    if (selectedShift === 'B') return 'Shift B';
    if (selectedShift === 'B1') return 'Shift B1';
    if (selectedShift === 'C') return 'Shift C';
    if (selectedStatus !== 'ALL') return selectedStatus;
    return 'ALL';
  }, [selectedShift, selectedStatus]);

  // Human-readable label for the current active filter (used on export button + filename)
  const activeFilterLabel = useMemo(() => {
    if (searchTerm && searchTerm.trim()) return `Search: ${searchTerm.trim()}`;
    if (selectedShift === 'A') return 'Shift A';
    if (selectedShift === 'General') return 'General Shift';
    if (selectedShift === 'B') return 'Shift B';
    if (selectedShift === 'B1') return 'Shift B1';
    if (selectedShift === 'C') return 'Shift C (Night)';
    if (selectedStatus === 'Needs Manual Review') return 'Manual Review';
    if (selectedStatus !== 'ALL') return selectedStatus;
    return null; // no active filter = export all
  }, [selectedShift, selectedStatus, searchTerm]);

  // Compute dashboard summary in memory
  const dashboardData = useMemo(() => {
    if (!allProcessedRecords || allProcessedRecords.length === 0) return null;

    const total_records = allProcessedRecords.length;
    const uniqueEmpSet = new Set();
    allProcessedRecords.forEach(r => {
      const id = (r.employee_id && r.employee_id !== '--') ? r.employee_id 
               : (r.employee_name && r.employee_name !== '--') ? r.employee_name 
               : (r['EMPLOYEE ID'] || r['EMP CODE'] || r['Emp ID'] || r['FIRST NAME'] || r['NAME'] || r['NO.'] || r.raw_idx);
      if (id && id !== '--' && id !== 'None' && id !== 'nan') uniqueEmpSet.add(String(id).trim());
    });
    const total_employees = uniqueEmpSet.size || total_records;

    const present = allProcessedRecords.filter(r => {
      const st = String(r.status || '');
      return st.includes('Present') || st.includes('Overtime') || st.includes('Late') || st.includes('Short Hours') || st.includes('Full Day') || st.includes('Half Day');
    }).length;
    const absent = allProcessedRecords.filter(r => r.status === 'Absent').length;
    const shift_a = allProcessedRecords.filter(r => r.shift === 'A' || r.shift === '1').length;
    const shift_general = allProcessedRecords.filter(r => r.shift === 'General' || r.shift === '4').length;
    const shift_b = allProcessedRecords.filter(r => r.shift === 'B' || r.shift === '2').length;
    const shift_b1 = allProcessedRecords.filter(r => r.shift === 'B1' || r.shift === '5').length;
    const shift_c = allProcessedRecords.filter(r => r.shift === 'C' || r.shift === '3' || r.is_overnight).length;
    const late_login = allProcessedRecords.filter(r => r.status === 'Late Login' || (r.remarks && String(r.remarks).includes('Late'))).length;
    const missing_logout = allProcessedRecords.filter(r => r.status === 'Missing Logout').length;
    const missing_login = allProcessedRecords.filter(r => r.status === 'Missing Login').length;
    const needs_manual_review = allProcessedRecords.filter(r => {
      const st = String(r.status || '').toLowerCase();
      const rem = String(r.remarks || '').toLowerCase();
      return st.includes('manual review') || rem.includes('manual review');
    }).length;
    const overtime = allProcessedRecords.filter(r => {
      const otStr = r.overtime_hours || r['Overtime Hours'] || r['OVERTIME HOURS'] || r.overtime || '';
      const otDec = Number(r.overtime_hours_decimal || 0);
      const whDec = Number(r.working_hours_decimal || 0);
      const isOtTime = otStr && otStr !== '00:00' && otStr !== '--' && otStr !== '0';
      return isOtTime || otDec > 0 || whDec > 8.0 || r.status === 'Overtime' || (r.remarks && String(r.remarks).includes('Overtime'));
    }).length;

    return {
      summary: {
        total_records, total_employees, present, absent,
        shift_a, shift_general, shift_b, shift_b1, shift_c,
        late_login, missing_logout, missing_login, needs_manual_review, overtime
      },
      shifts: { shift_a, shift_general, shift_b, shift_b1, shift_c }
    };
  }, [allProcessedRecords]);

  const handleStatusCardSelect = (cardId) => {
    if (cardId === 'Shift A') {
      setSelectedShift('A');
      setSelectedStatus('ALL');
    } else if (cardId === 'General') {
      setSelectedShift('General');
      setSelectedStatus('ALL');
    } else if (cardId === 'Shift B') {
      setSelectedShift('B');
      setSelectedStatus('ALL');
    } else if (cardId === 'Shift B1') {
      setSelectedShift('B1');
      setSelectedStatus('ALL');
    } else if (cardId === 'Shift C' || cardId === 'Night Shift') {
      setSelectedShift('C');
      setSelectedStatus('ALL');
    } else if (cardId === 'ALL' || cardId === 'EMPLOYEES') {
      setSelectedShift('ALL');
      setSelectedStatus('ALL');
    } else {
      setSelectedShift('ALL');
      setSelectedStatus(cardId);
    }
  };

  const handleUpdateRecord = (recordId, updatePayload) => {
    setAllProcessedRecords(prev => prev.map((r, idx) => {
      const currentId = r.id !== undefined ? r.id : idx;
      if (currentId === recordId) {
        return { ...r, ...updatePayload };
      }
      return r;
    }));
  };

  const handleDeleteRecord = (recordId) => {
    if (!window.confirm("Are you sure you want to remove this record from view?")) return;
    setAllProcessedRecords(prev => prev.filter((r, idx) => (r.id !== undefined ? r.id : idx) !== recordId));
  };

  const handleExport = async (scope = 'filtered') => {
    const targetRecords = scope === 'full' ? allProcessedRecords : filteredRecords;
    if (!targetRecords || targetRecords.length === 0) {
      alert("No records available to export for the selected view.");
      return;
    }

    setExporting(true);
    setExportToast(null);

    try {
      const cleanBaseName = uploadedFileName ? uploadedFileName.replace(/\.[^/.]+$/, '') : 'Attendance_Report';
      let filterTag;
      if (scope === 'full') {
        filterTag = 'Full_3Sheet';
      } else if (activeFilterLabel) {
        filterTag = activeFilterLabel.replace(/[^a-zA-Z0-9]/g, '_');
      } else {
        filterTag = 'Filtered';
      }
      const fileName = `${filterTag}_${cleanBaseName}.xlsx`;

      // Generate multi-sheet Excel file directly in browser memory
      // Eliminates 4.5MB Vercel serverless request body limits (413 Content Too Large) & CORS network issues
      exportToExcelClient(targetRecords, scope, fileName);

      setExporting(false);
      const filterDesc = scope === 'full'
        ? '3 sheets: Daily Detail, Monthly Summary, Manual Review'
        : (activeFilterLabel ? `"${activeFilterLabel}" filter` : 'filtered view');
      setExportToast({
        title: `✅ Download Ready — ${fileName}`,
        message: `${targetRecords.length} records exported (${filterDesc}). Check your Downloads folder!`
      });

      setTimeout(() => {
        setExportToast(null);
      }, 8000);
    } catch (err) {
      console.error('Export error:', err);
      setExporting(false);
      alert(`Export failed: ${err.message || 'Unknown error'}. Please try again.`);
    }
  };

  const hasData = allProcessedRecords.length > 0;

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)', color: 'var(--text-primary)', fontFamily: 'var(--font-ui)', position: 'relative' }}>

      {/* Floating Download Toast Notification */}
      {exportToast && (
        <div className="fade-up" style={{
          position: 'fixed', top: 20, right: 24, zIndex: 100,
          background: '#007334', color: '#FFFFFF',
          padding: '14px 20px', borderRadius: 10,
          boxShadow: '0 10px 30px rgba(0, 115, 52, 0.35)',
          display: 'flex', alignItems: 'center', gap: 12,
          border: '1px solid #69F0AE', maxWidth: 420
        }}>
          <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <CheckCircle2 style={{ width: 18, height: 18, color: '#FFFFFF' }} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 800, color: '#FFFFFF' }}>{exportToast.title}</div>
            <div style={{ fontSize: 11, color: '#EBF5ED', marginTop: 2 }}>{exportToast.message}</div>
          </div>
          <button onClick={() => setExportToast(null)} style={{ background: 'none', border: 'none', color: '#FFFFFF', cursor: 'pointer', padding: 4 }}>
            <X style={{ width: 14, height: 14 }} />
          </button>
        </div>
      )}

      <Navbar
        onOpenUpload={() => setIsUploadOpen(true)}
        onExport={handleExport}
        hasData={hasData}
        exporting={exporting}
        activeFilterLabel={activeFilterLabel}
      />

      <main style={{ maxWidth: 1600, margin: '0 auto', padding: '28px 24px' }}>

        {!hasData ? (
          /* Enterprise Excel Empty State */
          <div className="empty-state fade-up" style={{ marginTop: 30 }}>
            <div style={{ width: 58, height: 58, borderRadius: 14, background: '#E2F5E8', border: '1px solid #B3E6C4', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 18px', boxShadow: '0 4px 16px rgba(0, 158, 73, 0.12)' }}>
              <FileSpreadsheet style={{ width: 30, height: 30, color: '#009E49' }} />
            </div>
            <h2 style={{ fontSize: 19, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 8, fontFamily: 'var(--font-ui)' }}>Import Client Attendance Sheet</h2>
            <p style={{ fontSize: 13, color: '#556C5D', maxWidth: 460, margin: '0 auto 24px', lineHeight: 1.6 }}>
              Upload your raw Excel attendance sheet. AttendanceIQ automatically pairs 10 PM – 6 AM night shift rows, calculates working hours, and displays a clean mini Excel grid report.
            </p>
            <button
              onClick={() => setIsUploadOpen(true)}
              className="btn-primary"
              style={{ fontSize: 12, padding: '11px 24px' }}
              id="empty-upload-btn"
            >
              <Upload style={{ width: 14, height: 14 }} />
              Upload & Process Excel Sheet
              <ArrowRight style={{ width: 14, height: 14 }} />
            </button>
          </div>
        ) : (
          <>
            {/* KPI Summary Row */}
            {dashboardData && (
              <SummaryCards
                metrics={dashboardData.summary}
                activeStatusFilter={activeKpiFilter}
                onSelectStatusFilter={handleStatusCardSelect}
              />
            )}

            {/* Enterprise Data Grid */}
            <AttendanceTable
              records={filteredRecords}
              columns={excelColumns}
              loading={loading}
              searchTerm={searchTerm}
              setSearchTerm={setSearchTerm}
              selectedShift={selectedShift}
              setSelectedShift={setSelectedShift}
              selectedStatus={selectedStatus}
              setSelectedStatus={setSelectedStatus}
              selectedDept={selectedDept}
              setSelectedDept={setSelectedDept}
              onRefresh={() => { }}
              onUpdateRecord={handleUpdateRecord}
              onDeleteRecord={handleDeleteRecord}
              onExport={handleExport}
              exporting={exporting}
              activeFilterLabel={activeFilterLabel}
            />
          </>
        )}
      </main>

      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={handleUploadSuccess}
        onExport={handleExport}
      />
    </div>
  );
}
