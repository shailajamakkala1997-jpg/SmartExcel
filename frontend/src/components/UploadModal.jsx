import React, { useState, useRef } from 'react';
import { Upload, X, FileSpreadsheet, CheckCircle2, AlertTriangle, RefreshCw, Layers, Plus } from 'lucide-react';
import axios from 'axios';

export default function UploadModal({ isOpen, onClose, onSuccess }) {
  const [file, setFile] = useState(null);
  const [totalPunchesFile, setTotalPunchesFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  const fileRef = useRef();
  const tpFileRef = useRef();

  if (!isOpen) return null;

  const validateFile = (f) => {
    if (!f) return false;
    const nameLower = (f.name || '').toLowerCase();
    const valid = ['.xlsx', '.xls', '.xlsm', '.csv'].some(ext => nameLower.endsWith(ext));
    if (!valid) {
      setError('Invalid file format. Please upload Excel (.xlsx, .xls, .xlsm) or CSV (.csv) files.');
      return false;
    }
    if (f.size > 50 * 1024 * 1024) {
      setError('File size exceeds 50MB limit. Please upload a smaller file.');
      return false;
    }
    return true;
  };

  const handleFilesAdded = (fileList) => {
    setError(null);
    setDone(false);

    if (!fileList || fileList.length === 0) return;

    const files = Array.from(fileList).filter(validateFile);
    if (files.length === 0) return;

    if (files.length === 1) {
      const f = files[0];
      const nameLower = f.name.toLowerCase();
      if (nameLower.includes('punch') && file) {
        setTotalPunchesFile(f);
      } else {
        setFile(f);
      }
    } else {
      // 2 or more files dropped at once
      const tp = files.find(f => f.name.toLowerCase().includes('punch'));
      const raw = files.find(f => f !== tp) || files[0];
      setFile(raw);
      if (tp) setTotalPunchesFile(tp);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files) {
      handleFilesAdded(e.dataTransfer.files);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select at least one main Excel or CSV file.');
      return;
    }
    setUploading(true);
    setError(null);
    const fd = new FormData();
    fd.append('file', file);
    if (totalPunchesFile) {
      fd.append('total_punches_file', totalPunchesFile);
    }

    try {
      const res = await axios.post('/api/upload', fd, { timeout: 300000 });
      onSuccess(res.data);
      setDone(true);
      setUploading(false);
      setTimeout(() => {
        setDone(false);
        setFile(null);
        setTotalPunchesFile(null);
        onClose();
      }, 1200);
    } catch (err) {
      setUploading(false);
      if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else if (err.code === 'ECONNREFUSED' || (err.message && err.message.includes('Network Error'))) {
        setError('Backend server on port 8005 is starting or offline. Please click "Process Sheet" again.');
      } else {
        setError(err.message || 'Upload failed. Please verify file format and data columns.');
      }
    }
  };

  const reset = () => {
    setFile(null);
    setTotalPunchesFile(null);
    setError(null);
    setDone(false);
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 60,
        background: 'rgba(10, 33, 19, 0.65)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="panel-raised fade-up"
        style={{
          width: '100%',
          maxWidth: 540,
          borderRadius: 14,
          overflow: 'hidden',
          background: '#FFFFFF',
          border: '1px solid #009E49',
          boxShadow: '0 20px 40px rgba(0, 158, 73, 0.15)'
        }}
      >
        {/* Header */}
        <div style={{ padding: '16px 20px', background: '#009E49', color: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 34, height: 34, borderRadius: 8, background: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
              <FileSpreadsheet style={{ width: 18, height: 18, color: '#009E49' }} />
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 800, color: '#FFFFFF', fontFamily: 'var(--font-ui)' }}>Import Attendance Batch</div>
              <div style={{ fontSize: 11, color: '#EBF5ED', marginTop: 1 }}>Single workbook or Dual-file upload (Raw Data + Total Punches)</div>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#FFFFFF', cursor: 'pointer', padding: 4 }} id="modal-close">
            <X style={{ width: 16, height: 16 }} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: 24, background: '#FFFFFF' }}>
          {done ? (
            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <div style={{ width: 48, height: 48, borderRadius: '50%', background: '#DFF6E6', border: '1px solid #B3E6C4', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
                <CheckCircle2 style={{ width: 24, height: 24, color: '#007334' }} />
              </div>
              <div style={{ fontSize: 15, fontWeight: 800, color: '#0A2113', marginBottom: 4 }}>Sheet Processed Successfully</div>
              <div style={{ fontSize: 12, color: '#556C5D' }}>Loading data into mini Excel grid...</div>
            </div>
          ) : (
            <>
              {/* File Dropzone */}
              <div
                className="dropzone"
                style={{
                  padding: '28px 20px',
                  textAlign: 'center',
                  cursor: 'pointer',
                  position: 'relative',
                  background: dragging ? '#EBF5ED' : '#F8FAF7',
                  border: dragging ? '2px dashed #009E49' : '1px dashed #B3E6C4',
                  borderRadius: 10,
                  transition: 'all 0.2s ease'
                }}
                onClick={() => fileRef.current?.click()}
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                id="upload-dropzone"
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept=".xlsx,.xls,.xlsm,.csv"
                  multiple
                  onChange={e => handleFilesAdded(e.target.files)}
                  style={{ display: 'none' }}
                  id="file-input"
                />
                <input
                  ref={tpFileRef}
                  type="file"
                  accept=".xlsx,.xls,.xlsm,.csv"
                  onChange={e => {
                    if (e.target.files?.[0] && validateFile(e.target.files[0])) {
                      setTotalPunchesFile(e.target.files[0]);
                    }
                  }}
                  style={{ display: 'none' }}
                  id="tp-file-input"
                />

                <FileSpreadsheet style={{ width: 38, height: 38, color: (file || totalPunchesFile) ? '#009E49' : '#94A3B8', margin: '0 auto 10px' }} />

                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#0A2113', marginBottom: 4 }}>
                    Drop Excel or CSV file(s) here
                  </div>
                  <div style={{ fontSize: 11, color: '#556C5D' }}>
                    Supports 1 combined workbook or 2 separate files (Raw Data + Total Punches)
                  </div>
                </div>
              </div>

              {/* Selected Files List */}
              {(file || totalPunchesFile) && (
                <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {file && (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: '#F0F9F3', border: '1px solid #B3E6C4', borderRadius: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <FileSpreadsheet style={{ width: 16, height: 16, color: '#009E49' }} />
                        <div>
                          <div style={{ fontSize: 12, fontWeight: 800, color: '#007334' }}>{file.name}</div>
                          <div style={{ fontSize: 10, color: '#556C5D' }}>Primary File (Raw Data / Workbook) · {(file.size / 1024).toFixed(1)} KB</div>
                        </div>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); setFile(null); }}
                        style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer', padding: 2 }}
                        title="Remove file"
                      >
                        <X style={{ width: 14, height: 14 }} />
                      </button>
                    </div>
                  )}

                  {totalPunchesFile ? (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: '#F0F9F3', border: '1px solid #B3E6C4', borderRadius: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Layers style={{ width: 16, height: 16, color: '#009E49' }} />
                        <div>
                          <div style={{ fontSize: 12, fontWeight: 800, color: '#007334' }}>{totalPunchesFile.name}</div>
                          <div style={{ fontSize: 10, color: '#556C5D' }}>Total Punches Report · {(totalPunchesFile.size / 1024).toFixed(1)} KB</div>
                        </div>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); setTotalPunchesFile(null); }}
                        style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer', padding: 2 }}
                        title="Remove file"
                      >
                        <X style={{ width: 14, height: 14 }} />
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={(e) => { e.stopPropagation(); tpFileRef.current?.click(); }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justify: 'center',
                        gap: 6,
                        padding: '8px 12px',
                        background: '#FFFFFF',
                        border: '1px dashed #009E49',
                        borderRadius: 8,
                        color: '#00873D',
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer'
                      }}
                      id="add-total-punches-btn"
                    >
                      <Plus style={{ width: 14, height: 14 }} />
                      Add Separate Total Punches File (Optional)
                    </button>
                  )}
                </div>
              )}

              {error && (
                <div style={{ marginTop: 12, padding: '10px 14px', borderRadius: 6, background: '#FEE2E2', border: '1px solid #FECACA', display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <AlertTriangle style={{ width: 14, height: 14, color: '#991B1B', flexShrink: 0, marginTop: 1 }} />
                  <span style={{ fontSize: 12, color: '#7F1D1D', fontWeight: 600 }}>{error}</span>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {!done && (
          <div style={{ padding: '12px 20px', background: '#F8FAF7', borderTop: '1px solid #E2EDE5', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 10 }}>
            {(file || totalPunchesFile) && <button onClick={reset} className="btn-ghost" id="reset-file">Clear All</button>}
            <button onClick={onClose} className="btn-ghost" id="cancel-upload">Cancel</button>
            <button onClick={handleUpload} disabled={uploading || !file} className="btn-primary" id="process-btn">
              {uploading ? <RefreshCw style={{ width: 12, height: 12 }} className="spin" /> : <Upload style={{ width: 12, height: 12 }} />}
              {uploading ? 'Processing Sheet...' : 'Process Sheet'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}