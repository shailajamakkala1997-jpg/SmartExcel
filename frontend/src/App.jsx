import React, { useState, useMemo } from 'react';
import Navbar from './components/Navbar';
import SummaryCards from './components/SummaryCards';
import AttendanceTable from './components/AttendanceTable';
import UploadModal from './components/UploadModal';
import axios from 'axios';
import { Upload, FileSpreadsheet, ArrowRight } from 'lucide-react';

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
      if (selectedStatus !== 'ALL' && r.status !== selectedStatus) return false;
      if (selectedDept !== 'ALL' && r.department !== selectedDept) return false;
      return true;
    });
  }, [allProcessedRecords, searchTerm, selectedShift, selectedStatus, selectedDept]);

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

    const present = allProcessedRecords.filter(r => ['Present', 'Overtime', 'Late Login'].includes(r.status)).length;
    const absent = allProcessedRecords.filter(r => r.status === 'Absent').length;
    const shift_a = allProcessedRecords.filter(r => r.shift === 'A').length;
    const shift_b = allProcessedRecords.filter(r => r.shift === 'B').length;
    const shift_c = allProcessedRecords.filter(r => r.shift === 'C' || r.is_overnight).length;
    const late_login = allProcessedRecords.filter(r => r.status === 'Late Login' || (r.remarks && r.remarks.includes('Late'))).length;
    const missing_logout = allProcessedRecords.filter(r => r.status === 'Missing Logout').length;
    const missing_login = allProcessedRecords.filter(r => r.status === 'Missing Login').length;
    const overtime = allProcessedRecords.filter(r => r.status === 'Overtime' || (r.remarks && r.remarks.includes('Overtime'))).length;

    return {
      summary: {
        total_records, total_employees, present, absent,
        shift_a, shift_b, shift_c,
        late_login, missing_logout, missing_login, overtime
      },
      shifts: { shift_a, shift_b, shift_c }
    };
  }, [allProcessedRecords]);

  const handleStatusCardSelect = (cardId) => {
    if (cardId === 'Shift A') {
      setSelectedShift('A');
      setSelectedStatus('ALL');
    } else if (cardId === 'Shift B') {
      setSelectedShift('B');
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

    try {
      const response = await axios.post('/api/export/excel-direct', {
        records: targetRecords,
        columns: excelColumns
      }, {
        responseType: 'blob'
      });

      const prefix = scope === 'full' ? 'Full' : 'Filtered';
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${prefix}_Attendance_${uploadedFileName || 'Report'}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error("Export error:", err);
      alert("Failed to export Excel file. Please try again.");
    }
  };

  // Chart Data preparation
  const pieData = (dashboardData && dashboardData.shifts) ? [
    { name: 'Shift A (06:00-14:00)', value: dashboardData.shifts.shift_a || 0, color: '#3B82F6' },
    { name: 'Shift B (14:00-22:00)', value: dashboardData.shifts.shift_b || 0, color: '#A855F7' },
    { name: 'Shift C (Night 22:00-06:00)', value: dashboardData.shifts.shift_c || 0, color: '#6366F1' },
  ] : [];

  const hasData = allProcessedRecords.length > 0;

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)', color: 'var(--text-primary)', fontFamily: 'var(--font-ui)' }}>

      <Navbar
        onOpenUpload={() => setIsUploadOpen(true)}
        onExport={handleExport}
        hasData={hasData}
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
                activeStatusFilter={selectedStatus === 'ALL' && selectedShift === 'C' ? 'Night Shift' : selectedStatus}
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
              onRefresh={() => {}}
              onUpdateRecord={handleUpdateRecord}
              onDeleteRecord={handleDeleteRecord}
              onExport={handleExport}
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
