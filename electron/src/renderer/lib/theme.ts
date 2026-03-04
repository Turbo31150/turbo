/**
 * JARVIS Desktop — Centralized theme tokens.
 * Supports dark (default) and light themes via CSS custom properties.
 * Used by new components; legacy components keep their inline styles.
 */

export type ThemeMode = 'dark' | 'light';

const DARK_COLORS = {
  bg: '#0a0e14',
  bgCard: '#0d1117',
  bgInput: '#0a0e14',
  border: '#1a2a3a',
  borderHover: 'rgba(249,115,22,.25)',
  text: '#e0e0e0',
  textMuted: '#c0c0c0',
  textDim: '#6b7280',
  textDimmer: '#4b5563',
  overlay: 'rgba(0,0,0,.6)',
  bgDarker: '#1a1a2e',
  scrollTrack: '#0a0e14',
  scrollThumb: '#1a2a3a',
};

const LIGHT_COLORS = {
  bg: '#f8fafc',
  bgCard: '#ffffff',
  bgInput: '#f1f5f9',
  border: '#e2e8f0',
  borderHover: 'rgba(249,115,22,.15)',
  text: '#1e293b',
  textMuted: '#475569',
  textDim: '#94a3b8',
  textDimmer: '#cbd5e1',
  overlay: 'rgba(0,0,0,.3)',
  bgDarker: '#e2e8f0',
  scrollTrack: '#f1f5f9',
  scrollThumb: '#cbd5e1',
};

export function getThemeColors(mode: ThemeMode) {
  return mode === 'light' ? LIGHT_COLORS : DARK_COLORS;
}

export function applyTheme(mode: ThemeMode) {
  const colors = getThemeColors(mode);
  const root = document.documentElement;
  root.style.setProperty('--bg', colors.bg);
  root.style.setProperty('--bg-card', colors.bgCard);
  root.style.setProperty('--bg-input', colors.bgInput);
  root.style.setProperty('--border', colors.border);
  root.style.setProperty('--text', colors.text);
  root.style.setProperty('--text-muted', colors.textMuted);
  root.style.setProperty('--text-dim', colors.textDim);
  root.style.setProperty('--overlay', colors.overlay);
  root.setAttribute('data-theme', mode);
  localStorage.setItem('jarvis-theme', mode);
}

export function getStoredTheme(): ThemeMode {
  const stored = localStorage.getItem('jarvis-theme') as ThemeMode | null;
  if (stored) return stored;
  // Detect system preference
  if (window.matchMedia?.('(prefers-color-scheme: light)').matches) return 'light';
  return 'dark';
}

export const COLORS = {
  // Backgrounds — default dark (live values read from CSS vars in new code)
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
  cyan: '#38bdf8',
  amber: '#f59e0b',

  // Status
  online: '#10b981',
  offline: '#ef4444',
  degraded: '#f97316',

  pinkDark: '#be185d',

  // Overlays
  overlay: 'rgba(0,0,0,.6)',
  bgDarker: '#1a1a2e',

  // Transparent / Alpha helpers
  greenAlpha: (a: number) => `rgba(16,185,129,${a})`,
  redAlpha: (a: number) => `rgba(239,68,68,${a})`,
  orangeAlpha: (a: number) => `rgba(249,115,22,${a})`,
  purpleAlpha: (a: number) => `rgba(192,132,252,${a})`,
  blueAlpha: (a: number) => `rgba(59,130,246,${a})`,
  pinkAlpha: (a: number) => `rgba(236,72,153,${a})`,
} as const;

// Agent/node color mapping for consistent visual identity
export const NODE_COLORS: Record<string, string> = {
  M1: '#38bdf8',       // cyan
  M2: '#a78bfa',       // purple
  M3: '#fb923c',       // orange
  OL1: '#34d399',      // emerald
  GEMINI: '#fbbf24',   // amber
  CLAUDE: '#c084fc',   // purple
  LOCAL: '#6b7280',    // gray
  // Cloud agents (MAO cluster)
  'GPT-OSS': '#f43f5e',    // rose
  'DEVSTRAL-2': '#8b5cf6', // violet
  'DEVSTRAL': '#8b5cf6',   // violet
  'GLM-4': '#facc15',      // yellow
  'GLM': '#facc15',        // yellow
  'MINIMAX': '#06b6d4',    // teal
  'MINIMAX-M2': '#06b6d4', // teal
  'QWEN3': '#38bdf8',      // sky
};

export const TOAST_COLORS: Record<string, string> = {
  error: '#ef4444',
  warning: '#f97316',
  success: '#10b981',
  info: '#3b82f6',
};

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
