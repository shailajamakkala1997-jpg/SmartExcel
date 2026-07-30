import React, { useEffect, useState } from 'react';
import { FileText, History, ShieldAlert, CheckCircle2 } from 'lucide-react';
import axios from 'axios';

export default function AuditLogs() {
  const [uploadHistory, setUploadHistory] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [activeSubTab, setActiveSubTab] = useState('uploads');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const [histRes, auditRes] = await Promise.all([
        axios.get('/api/upload-history'),
        axios.get('/api/audit-logs')
      ]);
      setUploadHistory(histRes.data);
      setAuditLogs(auditRes.data);
    } catch (err) {
      console.error("Failed to fetch logs:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-6 border border-slate-700/60 shadow-xl bg-slate-850/70">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            System Processing History & Audit Trail
          </h2>
          <p className="text-xs text-slate-400">Detailed records of Excel uploads, shift pairings, and administrative overrides</p>
        </div>

        <div className="flex items-center space-x-1 bg-slate-800 p-1 rounded-xl border border-slate-700">
          <button
            onClick={() => setActiveSubTab('uploads')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeSubTab === 'uploads' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <History className="w-3.5 h-3.5" /> Upload History
          </button>
          <button
            onClick={() => setActiveSubTab('audit')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeSubTab === 'audit' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" /> System Audit Trail
          </button>
        </div>
      </div>

      {activeSubTab === 'uploads' ? (
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900 text-slate-300 uppercase tracking-wider font-semibold">
              <tr>
                <th className="py-3 px-4">Filename</th>
                <th className="py-3 px-4">Uploaded At</th>
                <th className="py-3 px-4">Total Rows</th>
                <th className="py-3 px-4">Processed</th>
                <th className="py-3 px-4">Exceptions</th>
                <th className="py-3 px-4">Uploaded By</th>
                <th className="py-3 px-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {uploadHistory.length === 0 ? (
                <tr>
                  <td colSpan="7" className="py-8 text-center text-slate-400">No upload history available.</td>
                </tr>
              ) : (
                uploadHistory.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-800/40">
                    <td className="py-3 px-4 font-semibold text-blue-300">{item.filename}</td>
                    <td className="py-3 px-4 text-slate-400">{new Date(item.uploaded_at).toLocaleString()}</td>
                    <td className="py-3 px-4 text-slate-200">{item.record_count}</td>
                    <td className="py-3 px-4 text-emerald-400 font-bold">{item.processed_count}</td>
                    <td className="py-3 px-4 text-amber-400 font-bold">{item.exception_count}</td>
                    <td className="py-3 px-4 text-slate-300">{item.uploaded_by}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                        {item.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900 text-slate-300 uppercase tracking-wider font-semibold">
              <tr>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Entity</th>
                <th className="py-3 px-4">Details</th>
                <th className="py-3 px-4">Performed By</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {auditLogs.length === 0 ? (
                <tr>
                  <td colSpan="5" className="py-8 text-center text-slate-400">No audit logs recorded yet.</td>
                </tr>
              ) : (
                auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-800/40">
                    <td className="py-3 px-4 text-slate-400">{new Date(log.timestamp).toLocaleString()}</td>
                    <td className="py-3 px-4 font-bold text-amber-300">{log.action}</td>
                    <td className="py-3 px-4 text-slate-300">{log.entity_type} #{log.entity_id || '--'}</td>
                    <td className="py-3 px-4 text-slate-200">{log.details}</td>
                    <td className="py-3 px-4 text-blue-300">{log.performed_by}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
