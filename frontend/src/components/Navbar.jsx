import React from 'react';
import { FileSpreadsheet, Upload, Download, Loader2 } from 'lucide-react';

export default function Navbar({ onOpenUpload, onExport, hasData, activeFilterLabel, exporting }) {
  return (
    <header className="enterprise-nav sticky top-0 z-40 w-full shadow-md">
      <div className="max-w-screen-2xl mx-auto px-6 h-14 flex items-center justify-between">

        {/* Brand Logo & Name */}
        <div className="flex items-center gap-3">
          <div style={{
            width: 34, height: 34, borderRadius: 8,
            background: '#FFFFFF',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 2px 8px rgba(0,0,0,0.12)'
          }}>
            <FileSpreadsheet style={{ width: 20, height: 20, color: '#009E49' }} />
          </div>
          <div className="flex items-baseline gap-2">
            <span style={{ fontFamily: 'var(--font-ui)', fontSize: 17, fontWeight: 800, color: '#FFFFFF', letterSpacing: '-0.01em' }}>
              AttendanceIQ
            </span>
            <span style={{ fontSize: 10, fontWeight: 700, color: '#FFFFFF', background: 'rgba(255,255,255,0.2)', border: '1px solid rgba(255,255,255,0.3)', borderRadius: 4, padding: '1px 7px', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              Pro
            </span>
          </div>
        </div>

        {/* Live indicator + Actions */}
        <div className="flex items-center gap-3">
          {hasData && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#EBF5ED', fontWeight: 700 }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#69F0AE', display: 'inline-block' }} className="pulse-dot" />
              {activeFilterLabel ? `Filtered: ${activeFilterLabel}` : 'Live Data'}
            </div>
          )}

          <button
            onClick={onOpenUpload}
            className="btn-primary"
            style={{ background: '#FFFFFF', color: '#00873D', border: '1px solid #FFFFFF', fontWeight: 800 }}
            id="nav-upload-btn"
          >
            <Upload style={{ width: 13, height: 13, color: '#00873D' }} />
            Upload Batch
          </button>

          {hasData && (
            <button
              onClick={() => !exporting && onExport && onExport('full')}
              className="btn-export"
              disabled={exporting}
              style={{
                background: exporting ? '#005F2B' : '#007334',
                color: '#FFFFFF',
                border: '1px solid #005F2B',
                opacity: exporting ? 0.75 : 1,
                cursor: exporting ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', gap: 5
              }}
              id="nav-export-btn"
              title={exporting ? 'Generating Excel file, please wait...' : 'Download ALL processed records — 3 sheets (Daily Detail + Monthly Summary + Manual Review)'}
            >
              {exporting
                ? <Loader2 style={{ width: 13, height: 13, animation: 'spin 1s linear infinite' }} />
                : <Download style={{ width: 13, height: 13 }} />}
              {exporting ? 'Downloading...' : 'Export Full XLSX'}
            </button>
          )}
        </div>

      </div>
    </header>
  );
}
