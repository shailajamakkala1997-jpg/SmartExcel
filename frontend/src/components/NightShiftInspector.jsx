import React from 'react';
import { Moon, ArrowRight, CheckCircle2, Sparkles, AlertCircle, Calendar, Clock } from 'lucide-react';

export default function NightShiftInspector() {
  return (
    <div className="glass-panel rounded-2xl p-6 mb-6 border border-slate-700/60 bg-slate-850/60 shadow-xl relative overflow-hidden">
      
      {/* Background Glow */}
      <div className="absolute -top-24 -right-24 w-72 h-72 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-24 -left-24 w-72 h-72 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <Moon className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              Overnight Shift C Correction Inspector <Sparkles className="w-4 h-4 text-amber-400" />
            </h2>
            <p className="text-xs text-slate-400">Automatic cross-midnight punch pairing & hour calculation demonstration</p>
          </div>
        </div>

        <span className="text-xs px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/30">
          Smart Algorithm Active
        </span>
      </div>

      {/* Visual Timeline Comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
        
        {/* Raw Excel Input Card */}
        <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 relative">
          <div className="text-xs font-semibold text-amber-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5" /> Raw Unprocessed Attendance Excel Entry
          </div>

          <div className="bg-slate-950 rounded-lg p-3 border border-slate-800 text-xs font-mono">
            <div className="grid grid-cols-4 text-slate-400 border-b border-slate-800 pb-1.5 mb-2 font-sans font-medium">
              <span>Employee</span>
              <span>Date</span>
              <span>Check In</span>
              <span>Check Out</span>
            </div>
            <div className="grid grid-cols-4 text-slate-200 py-1">
              <span className="font-semibold text-blue-300">Kavitha</span>
              <span>03-06-2026</span>
              <span className="text-amber-300 font-bold">21:52</span>
              <span className="text-amber-300 font-bold">06:12</span>
            </div>
          </div>

          <div className="mt-3 text-[11px] text-slate-400 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <span>Issue in traditional systems: Logout (06:12) &lt; Login (21:52) causes negative time diff (-15h 40m).</span>
          </div>
        </div>

        {/* AI Processed Output Card */}
        <div className="p-4 rounded-xl bg-gradient-to-br from-emerald-950/40 to-slate-900 border border-emerald-500/30 relative">
          <div className="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" /> Auto-Corrected Attendance Output
          </div>

          <div className="bg-slate-950/80 rounded-lg p-3 border border-emerald-500/20 text-xs">
            <div className="grid grid-cols-5 text-slate-400 border-b border-slate-800 pb-1.5 mb-2 font-medium">
              <span>Shift Date</span>
              <span>Shift</span>
              <span>Login</span>
              <span>Logout</span>
              <span>Working Hours</span>
            </div>
            <div className="grid grid-cols-5 text-slate-200 py-1 items-center font-mono">
              <span className="font-sans">03-Jun-2026</span>
              <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-bold w-fit">Shift C</span>
              <span className="text-slate-200">21:52</span>
              <span className="text-slate-200">06:12 (+1d)</span>
              <span className="text-emerald-400 font-bold text-sm">08:20</span>
            </div>
          </div>

          <div className="mt-3 text-[11px] text-emerald-300 flex items-center justify-between">
            <span className="flex items-center gap-1.5 font-semibold">
              <CheckCircle2 className="w-3.5 h-3.5" /> Status: Present (08h 20m calculated)
            </span>
            <span className="text-[10px] bg-emerald-500/10 px-2 py-0.5 rounded text-emerald-400 border border-emerald-500/20">
              Zero Manual Verification
            </span>
          </div>
        </div>

      </div>

      {/* Logic Steps Bar */}
      <div className="mt-5 pt-4 border-t border-slate-800/80 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div className="flex items-center gap-2 text-slate-300">
          <div className="w-5 h-5 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-[10px]">1</div>
          <span>1. Detect Check In 21:52 &rarr; Assign Shift C</span>
        </div>
        <div className="flex items-center gap-2 text-slate-300">
          <div className="w-5 h-5 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-[10px]">2</div>
          <span>2. Detect Logout &lt; Login &rarr; Flag Cross-Midnight</span>
        </div>
        <div className="flex items-center gap-2 text-slate-300">
          <div className="w-5 h-5 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-[10px]">3</div>
          <span>3. Add +24h to Logout &rarr; Calc 500 mins</span>
        </div>
        <div className="flex items-center gap-2 text-slate-300">
          <div className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-[10px]">4</div>
          <span>4. Format Output &rarr; 08:20 (Present)</span>
        </div>
      </div>

    </div>
  );
}
