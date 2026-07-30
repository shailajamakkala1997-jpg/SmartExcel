import React from 'react';
import { Users, UserCheck, Moon, AlertTriangle, Clock, TrendingUp, Sun, Briefcase } from 'lucide-react';

const KPI_DEFS = [
  { id: 'ALL',            label: 'Total Records',    sub: 'Processed Rows',     icon: Briefcase,     key: 'total_records',   accent: '#009E49' },
  { id: 'Present',        label: 'Present',          sub: 'Completed Shifts',   icon: UserCheck,     key: 'present',         accent: '#00873D' },
  { id: 'Shift A',        label: 'Shift A (Day)',    sub: '06:00 - 14:00',      icon: Sun,           key: 'shift_a',         accent: '#1E40AF' },
  { id: 'Shift B',        label: 'Shift B (Eve)',    sub: '14:00 - 22:00',      icon: Clock,         key: 'shift_b',         accent: '#7B1FA2' },
  { id: 'Shift C',        label: 'Shift C (Night)',  sub: '22:00 - 06:00',      icon: Moon,          key: 'shift_c',         accent: '#00873D' },
  { id: 'Late Login',     label: 'Late Login',        sub: 'Beyond Margin',      icon: Clock,         key: 'late_login',      accent: '#D97706' },
  { id: 'Missing Logout', label: 'Missing Logout',    sub: 'Checkout Missing',   icon: AlertTriangle, key: 'missing_logout',  accent: '#DC2626' },
  { id: 'Overtime',       label: 'Overtime',          sub: 'Worked > 8.5 hrs',   icon: TrendingUp,    key: 'overtime',        accent: '#00873D' },
];

export default function SummaryCards({ metrics, activeStatusFilter, onSelectStatusFilter }) {
  if (!metrics) return null;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(135px, 1fr))', gap: 12, marginBottom: 20 }}>
      {KPI_DEFS.map(def => {
        const Icon = def.icon;
        const val = metrics[def.key] !== undefined ? metrics[def.key] : 0;
        const isActive = activeStatusFilter === def.id;

        return (
          <button
            key={def.id}
            onClick={() => onSelectStatusFilter(def.id)}
            className={'kpi-card' + (isActive ? ' active' : '')}
            style={{ textAlign: 'left', width: '100%' }}
            id={'kpi-' + def.id.toLowerCase().replace(/\s+/g, '-')}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <div style={{
                width: 28, height: 28, borderRadius: 7,
                background: def.accent + '15',
                border: '1px solid ' + def.accent + '35',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <Icon style={{ width: 14, height: 14, color: def.accent }} />
              </div>
              {isActive && <span className="pulse-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: def.accent, display: 'inline-block' }} />}
            </div>
            <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1, marginBottom: 4, fontFamily: 'var(--font-ui)' }}>
              {val}
            </div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
              {def.label}
            </div>
            <div style={{ fontSize: 10, color: '#556C5D', fontWeight: 600 }}>
              {def.sub}
            </div>
          </button>
        );
      })}
    </div>
  );
}