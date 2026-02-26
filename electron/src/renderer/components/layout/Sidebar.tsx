import React, { useState } from 'react';

type Page = 'dashboard' | 'chat' | 'trading' | 'voice' | 'lmstudio' | 'settings';

interface SidebarProps {
  currentPage: Page;
  onPageChange: (page: Page) => void;
}

interface NavItem {
  id: Page;
  label: string;
  icon: React.ReactNode;
}

const GridIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="7" height="7" rx="1" />
    <rect x="14" y="3" width="7" height="7" rx="1" />
    <rect x="3" y="14" width="7" height="7" rx="1" />
    <rect x="14" y="14" width="7" height="7" rx="1" />
  </svg>
);

const MessageIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

const ChartIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </svg>
);

const MicIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="9" y="2" width="6" height="12" rx="3" />
    <path d="M5 10a7 7 0 0 0 14 0" />
    <line x1="12" y1="19" x2="12" y2="22" />
  </svg>
);

const ServerIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="2" y="2" width="20" height="8" rx="2" />
    <rect x="2" y="14" width="20" height="8" rx="2" />
    <circle cx="6" cy="6" r="1" fill="currentColor" />
    <circle cx="6" cy="18" r="1" fill="currentColor" />
    <line x1="10" y1="6" x2="18" y2="6" />
    <line x1="10" y1="18" x2="18" y2="18" />
  </svg>
);

const GearIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: <GridIcon /> },
  { id: 'chat', label: 'Chat', icon: <MessageIcon /> },
  { id: 'trading', label: 'Trading', icon: <ChartIcon /> },
  { id: 'voice', label: 'Voice', icon: <MicIcon /> },
  { id: 'lmstudio', label: 'LM Studio', icon: <ServerIcon /> },
  { id: 'settings', label: 'Settings', icon: <GearIcon /> },
];

const styles = {
  sidebar: {
    width: 60,
    height: '100vh',
    backgroundColor: '#0d1117',
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    borderRight: '1px solid #1a2a3a',
    flexShrink: 0,
    zIndex: 10,
  },
  nav: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: 2,
    marginTop: 8,
    flex: 1,
  },
  button: {
    width: 60,
    height: 50,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'none',
    border: 'none',
    borderLeft: '3px solid transparent',
    cursor: 'pointer',
    color: '#4a6a8a',
    transition: 'all 0.2s ease',
    position: 'relative' as const,
    padding: 0,
  },
  buttonActive: {
    borderLeft: '3px solid #f97316',
    color: '#f97316',
  },
  buttonHover: {
    color: '#e0e0e0',
  },
  tooltip: {
    position: 'absolute' as const,
    left: 65,
    top: '50%',
    transform: 'translateY(-50%)',
    backgroundColor: '#1a2a3a',
    color: '#e0e0e0',
    padding: '4px 10px',
    borderRadius: 4,
    fontSize: 12,
    fontFamily: 'Consolas, Courier New, monospace',
    whiteSpace: 'nowrap' as const,
    pointerEvents: 'none' as const,
    zIndex: 100,
    border: '1px solid #2a3a4a',
  },
  logo: {
    width: 36,
    height: 36,
    borderRadius: '50%',
    backgroundColor: 'transparent',
    border: '2px solid #f97316',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#f97316',
    fontSize: 16,
    fontWeight: 'bold' as const,
    fontFamily: 'Consolas, Courier New, monospace',
    marginBottom: 16,
    marginTop: 8,
  },
};

export default function Sidebar({ currentPage, onPageChange }: SidebarProps) {
  const [hoveredItem, setHoveredItem] = useState<Page | null>(null);

  return (
    <div style={styles.sidebar}>
      <div style={styles.logo}>J</div>
      <nav style={styles.nav}>
        {NAV_ITEMS.map((item) => {
          const isActive = currentPage === item.id;
          const isHovered = hoveredItem === item.id;
          return (
            <button
              key={item.id}
              style={{
                ...styles.button,
                ...(isActive ? styles.buttonActive : {}),
                ...(isHovered && !isActive ? styles.buttonHover : {}),
              }}
              onClick={() => onPageChange(item.id)}
              onMouseEnter={() => setHoveredItem(item.id)}
              onMouseLeave={() => setHoveredItem(null)}
              title=""
            >
              {item.icon}
              {isHovered && (
                <span style={styles.tooltip}>{item.label}</span>
              )}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
