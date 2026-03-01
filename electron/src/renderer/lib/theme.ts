/**
 * JARVIS Desktop — Centralized theme tokens.
 * Used by new components; legacy components keep their inline styles.
 */

export const COLORS = {
  // Backgrounds
  bg: '#0a0e14',
  bgCard: '#0d1117',
  bgInput: '#0a0e14',

  // Borders
  border: '#1a2a3a',
  borderHover: 'rgba(249,115,22,.25)',

  // Text
  text: '#e0e0e0',
  textMuted: '#c0c0c0',
  textDim: '#6b7280',
  textDimmer: '#4b5563',

  // Brand
  orange: '#f97316',
  orangeDark: '#ea580c',

  // Semantic
  green: '#10b981',
  red: '#ef4444',
  blue: '#3b82f6',
  purple: '#c084fc',
  yellow: '#f59e0b',
  pink: '#ec4899',

  // Status
  online: '#10b981',
  offline: '#ef4444',
  degraded: '#f97316',
} as const;

export const FONT = 'Consolas, "Courier New", monospace';

export function statusColor(status: 'online' | 'offline' | 'degraded') {
  return {
    online: { bg: 'rgba(16,185,129,.12)', border: 'rgba(16,185,129,.3)', text: '#10b981' },
    offline: { bg: 'rgba(239,68,68,.08)', border: 'rgba(239,68,68,.25)', text: '#ef4444' },
    degraded: { bg: 'rgba(249,115,22,.08)', border: 'rgba(249,115,22,.25)', text: '#f97316' },
  }[status];
}

export function pctColor(pct: number, thresholds = { warn: 70, critical: 90 }) {
  if (pct >= thresholds.critical) return COLORS.red;
  if (pct >= thresholds.warn) return COLORS.orange;
  return COLORS.green;
}

export function latencyColor(ms: number) {
  if (ms <= 0) return COLORS.textDimmer;
  if (ms < 500) return COLORS.green;
  if (ms < 2000) return COLORS.orange;
  return COLORS.red;
}
