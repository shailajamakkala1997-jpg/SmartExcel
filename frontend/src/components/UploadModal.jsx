import React, { useState, useRef } from 'react';
import { Upload, X, FileSpreadsheet, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';
import axios from 'axios';

export default function UploadModal({ isOpen, onClose, onSuccess }) {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const fileRef = useRef();

  if (!isOpen) return null;

  const pick = (f) => { if (!f) return; setFile(f); setError(null); setDone(false); };
  const handleDrop = (e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) pick(f); };

  const handleUpload = async () => {
    if (!file) { setError('Please select an Excel file (.xlsx or .xls)'); return; }
    setUploading(true); setError(null);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await axios.post('/api/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      onSuccess(res.data);
      setDone(true);
      setUploading(false);
      setTimeout(() => { setDone(false); setFile(null); onClose(); }, 1200);
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed. Please verify file format.');
      setUploading(false);
    }
  };

  const reset = () => { setFile(null); setError(null); setDone(false); };

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(10, 33, 19, 0.65)', backdropFilter: 'blur(6px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="panel-raised fade-up" style={{ width: '100%', maxWidth: 520, borderRadius: 14, overflow: 'hidden', background: '#FFFFFF', border: '1px solid #009E49' }}>

        {/* Header */}
        <div style={{ padding: '16px 20px', background: '#009E49', color: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 34, height: 34, borderRadius: 8, background: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
              <FileSpreadsheet style={{ width: 18, height: 18, color: '#009E49' }} />
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 800, color: '#FFFFFF', fontFamily: 'var(--font-ui)' }}>Import Attendance Batch</div>
              <div style={{ fontSize: 11, color: '#EBF5ED', marginTop: 1 }}>Supports Excel .xlsx and .xls sheets</div>
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
              <div
                className="dropzone"
                style={{ padding: '36px 24px', textAlign: 'center', cursor: 'pointer', position: 'relative', marginBottom: error ? 12 : 0, background: '#F8FAF7' }}
                onClick={() => fileRef.current?.click()}
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                id="upload-dropzone"
              >
                <input ref={fileRef} type="file" accept=".xlsx,.xls" onChange={e => pick(e.target.files[0])} style={{ display: 'none' }} id="file-input" />
                <FileSpreadsheet style={{ width: 42, height: 42, color: file ? '#009E49' : '#94A3B8', margin: '0 auto 12px' }} />
                {file ? (
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 800, color: '#00873D', marginBottom: 3 }}>{file.name}</div>
                    <div style={{ fontSize: 11, color: '#556C5D' }}>{(file.size / 1024).toFixed(1)} KB · Ready for processing</div>
                  </div>
                ) : (
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#0A2113', marginBottom: 4 }}>Drop your Excel sheet here</div>
                    <div style={{ fontSize: 11, color: '#556C5D' }}>or click to browse · auto-detects column headers</div>
                  </div>
                )}
              </div>
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
            {file && <button onClick={reset} className="btn-ghost" id="reset-file">Clear</button>}
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