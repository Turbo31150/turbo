import React, { useState } from 'react';
import { useClusterContext } from '../../hooks/ClusterContext';
import { APP_VERSION } from '../../lib/config';
import type { Page } from '../../lib/types';

interface SidebarProps {
  currentPage: Page;
  onPageChange: (page: Page) => void;
}

interface NavItem {
  id: Page;
  label: string;
  icon: React.ReactNode;
  badge?: () => React.ReactNode;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

// ═══════════════════════════════════════════════════════════════
// SVG Icons
// ═══════════════════════════════════════════════════════════════

const GridIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" />
    <rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" />
  </svg>
);
const MessageIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);
const ServerIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="2" y="2" width="20" height="8" rx="2" /><rect x="2" y="14" width="20" height="8" rx="2" />
    <circle cx="6" cy="6" r="1" fill="currentColor" /><circle cx="6" cy="18" r="1" fill="currentColor" />
  </svg>
);
const MicIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10a7 7 0 0 0 14 0" />
    <line x1="12" y1="19" x2="12" y2="22" />
  </svg>
);
const BookIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
  </svg>
);
const PipelineIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="5" cy="6" r="3" /><circle cx="19" cy="6" r="3" /><circle cx="12" cy="18" r="3" />
    <path d="M5 9v3a3 3 0 0 0 3 3h8a3 3 0 0 0 3-3V9" /><line x1="12" y1="15" x2="12" y2="12" />
  </svg>
);
const ToolboxIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
  </svg>
);
const ChartIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </svg>
);
const LogsIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
  </svg>
);
const GearIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);
const CollapseIcon = ({ collapsed }: { collapsed: boolean }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    style={{ transform: collapsed ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}>
    <polyline points="15 18 9 12 15 6" />
  </svg>
);

// ═══════════════════════════════════════════════════════════════
// Navigation structure
// ═══════════════════════════════════════════════════════════════

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Principal',
    items: [
      { id: 'dashboard', label: 'Dashboard', icon: <GridIcon /> },
      { id: 'chat', label: 'Chat', icon: <MessageIcon /> },
    ],
  },
  {
    label: 'IA & Modeles',
    items: [
      { id: 'lmstudio', label: 'AI Cluster', icon: <ServerIcon /> },
      { id: 'voice', label: 'Voice', icon: <MicIcon /> },
    ],
  },
  {
    label: 'Outils',
    items: [
      { id: 'dictionary', label: 'Dictionary', icon: <BookIcon /> },
      { id: 'pipelines', label: 'Pipelines', icon: <PipelineIcon /> },
      { id: 'toolbox', label: 'Toolbox', icon: <ToolboxIcon /> },
    ],
  },
  {
    label: 'Systeme',
    items: [
      { id: 'trading', label: 'Trading', icon: <ChartIcon /> },
      { id: 'logs', label: 'Logs', icon: <LogsIcon /> },
      { id: 'settings', label: 'Settings', icon: <GearIcon /> },
    ],
  },
];

// ═══════════════════════════════════════════════════════════════
// Styles
// ═══════════════════════════════════════════════════════════════

const CSS = `
.sb-btn{transition:all .15s ease}
.sb-btn:hover{background:rgba(249,115,22,.06)!important;color:#e0e0e0!important}
.sb-toggle:hover{color:#e0e0e0!important}
@keyframes sb-pulse{0%,100%{opacity:1}50%{opacity:.6}}
`;

function Badge({ count, color }: { count: number; color: string }) {
  if (count <= 0) return null;
  return (
    <span style={{
      minWidth: 18, height: 18, borderRadius: 9, fontSize: 9, fontWeight: 700,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      backgroundColor: `${color}22`, color, border: `1px solid ${color}44`,
      padding: '0 4px', marginLeft: 'auto', flexShrink: 0,
    }}>{count}</span>
  );
}

function StatusDot({ online }: { online: boolean }) {
  return (
    <span style={{
      width: 6, height: 6, borderRadius: '50%', flexShrink: 0, marginLeft: 'auto',
      backgroundColor: online ? '#10b981' : '#ef4444',
      boxShadow: online ? '0 0 6px rgba(16,185,129,.5)' : 'none',
      animation: online ? 'sb-pulse 2s ease infinite' : 'none',
    }} />
  );
}

export default function Sidebar({ currentPage, onPageChange }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [hoveredItem, setHoveredItem] = useState<Page | null>(null);
  const { nodes } = useClusterContext();
  const width = collapsed ? 52 : 180;
  const onlineCount = nodes.filter(n => n.status === 'online').length;
  const modelsLoaded = nodes.reduce((sum, n) => sum + n.models.filter(m => m.loaded).length, 0);

  return (
    <>
      <style>{CSS}</style>
      <div style={{
        width, height: '100vh', backgroundColor: '#0d1117', display: 'flex', flexDirection: 'column',
        borderRight: '1px solid #1a2a3a', flexShrink: 0, zIndex: 10, transition: 'width .2s ease',
        overflow: 'hidden',
      }}>
        {/* Logo + collapse toggle */}
        <div style={{ display: 'flex', alignItems: 'center', padding: collapsed ? '10px 8px' : '10px 12px', gap: 10, borderBottom: '1px solid #1a2a3a' }}>
          <div style={{
            width: 32, height: 32, borderRadius: '50%', border: '2px solid #f97316', display: 'flex',
            alignItems: 'center', justifyContent: 'center', color: '#f97316', fontSize: 14, fontWeight: 'bold',
            fontFamily: 'Consolas, Courier New, monospace', flexShrink: 0,
          }}>J</div>
          {!collapsed && (
            <span style={{ fontSize: 13, fontWeight: 700, color: '#e0e0e0', fontFamily: 'inherit', letterSpacing: 1 }}>JARVIS</span>
          )}
          <button className="sb-toggle" onClick={() => setCollapsed(!collapsed)} style={{
            marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280',
            padding: 4, display: 'flex', alignItems: 'center',
          }}>
            <CollapseIcon collapsed={collapsed} />
          </button>
        </div>

        {/* Nav groups */}
        <nav aria-label="Navigation principale" style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
          {NAV_GROUPS.map(group => (
            <div key={group.label} style={{ marginBottom: 4 }}>
              {!collapsed && (
                <div style={{
                  fontSize: 9, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1.5,
                  padding: '10px 14px 4px', fontWeight: 700,
                }}>{group.label}</div>
              )}
              {collapsed && <div style={{ height: 6 }} />}

              {group.items.map(item => {
                const isActive = currentPage === item.id;
                const isHovered = hoveredItem === item.id;
                return (
                  <button key={item.id} className="sb-btn"
                    aria-label={collapsed ? item.label : undefined}
                    style={{
                      width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                      padding: collapsed ? '10px 0' : '8px 14px',
                      justifyContent: collapsed ? 'center' : 'flex-start',
                      background: 'none', border: 'none', cursor: 'pointer',
                      borderLeft: collapsed ? 'none' : `3px solid ${isActive ? '#f97316' : 'transparent'}`,
                      color: isActive ? '#f97316' : '#6b7280',
                      fontFamily: 'Consolas, Courier New, monospace', fontSize: 12, fontWeight: isActive ? 600 : 400,
                      position: 'relative',
                    }}
                    onClick={() => onPageChange(item.id)}
                    onMouseEnter={() => setHoveredItem(item.id)}
                    onMouseLeave={() => setHoveredItem(null)}
                  >
                    <span style={{ flexShrink: 0, display: 'flex' }}>{item.icon}</span>
                    {!collapsed && <span>{item.label}</span>}
                    {!collapsed && item.id === 'lmstudio' && <Badge count={onlineCount} color="#10b981" />}
                    {!collapsed && item.id === 'dashboard' && modelsLoaded > 0 && <Badge count={modelsLoaded} color="#c084fc" />}
                    {collapsed && item.id === 'lmstudio' && onlineCount > 0 && (
                      <span style={{
                        position: 'absolute', top: 4, right: 6, width: 8, height: 8,
                        borderRadius: '50%', backgroundColor: '#10b981',
                        border: '2px solid #0d1117',
                      }} />
                    )}
                    {collapsed && isHovered && (
                      <span style={{
                        position: 'absolute', left: 56, top: '50%', transform: 'translateY(-50%)',
                        backgroundColor: '#1a2a3a', color: '#e0e0e0', padding: '4px 10px', borderRadius: 4,
                        fontSize: 12, whiteSpace: 'nowrap', pointerEvents: 'none', zIndex: 100,
                        border: '1px solid #2a3a4a', fontFamily: 'inherit',
                      }}>{item.label}</span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Bottom version */}
        {!collapsed && (
          <div style={{ padding: '8px 14px', fontSize: 9, color: '#4b5563', borderTop: '1px solid #1a2a3a' }}>
            JARVIS v{APP_VERSION}
          </div>
        )}
      </div>
    </>
  );
}
