import React, { useCallback } from 'react';

type Page = 'dashboard' | 'chat' | 'trading' | 'voice' | 'settings';

interface TopBarProps {
  connected: boolean;
  currentPage: Page;
  onDetach?: () => void;
}

const PAGE_LABELS: Record<Page, string> = {
  dashboard: 'DASHBOARD',
  chat: 'CHAT',
  trading: 'TRADING',
  voice: 'VOICE',
  settings: 'SETTINGS',
};

const styles = {
  topbar: {
    height: 40,
    backgroundColor: '#0d1117',
    borderBottom: '1px solid #1a2a3a',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    WebkitAppRegion: 'drag' as any,
    userSelect: 'none' as const,
    flexShrink: 0,
    paddingLeft: 16,
  },
  title: {
    color: '#00d4ff',
    fontSize: 13,
    fontWeight: 'bold' as const,
    letterSpacing: 4,
    fontFamily: 'Consolas, Courier New, monospace',
  },
  center: {
    color: '#4a6a8a',
    fontSize: 12,
    fontFamily: 'Consolas, Courier New, monospace',
    letterSpacing: 2,
  },
  right: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    WebkitAppRegion: 'no-drag' as any,
    paddingRight: 0,
  },
  connectionDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    marginRight: 4,
  },
  connectionDotConnected: {
    backgroundColor: '#00ff88',
    boxShadow: '0 0 6px #00ff88',
    animation: 'pulse-dot 2s ease-in-out infinite',
  },
  connectionDotDisconnected: {
    backgroundColor: '#ff4444',
    boxShadow: '0 0 6px #ff4444',
  },
  connectionLabel: {
    fontSize: 10,
    fontFamily: 'Consolas, Courier New, monospace',
    marginRight: 8,
  },
  winBtn: {
    width: 40,
    height: 40,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'none',
    border: 'none',
    color: '#4a6a8a',
    fontSize: 14,
    cursor: 'pointer',
    fontFamily: 'Consolas, Courier New, monospace',
    transition: 'background-color 0.15s ease, color 0.15s ease',
  },
  winBtnClose: {
    width: 40,
    height: 40,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'none',
    border: 'none',
    color: '#4a6a8a',
    fontSize: 14,
    cursor: 'pointer',
    fontFamily: 'Consolas, Courier New, monospace',
    transition: 'background-color 0.15s ease, color 0.15s ease',
  },
};

const pulseKeyframes = `
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
`;

const DETACHABLE_PAGES: Page[] = ['dashboard', 'trading', 'voice'];
const WIDGET_TYPES: Record<string, string> = {
  dashboard: 'MiniCluster',
  trading: 'MiniTrading',
  voice: 'MiniVoice',
};

export default function TopBar({ connected, currentPage, onDetach }: TopBarProps) {
  const canDetach = DETACHABLE_PAGES.includes(currentPage);
  const handleMinimize = useCallback(() => {
    (window as any).electronAPI?.minimize?.();
  }, []);

  const handleMaximize = useCallback(() => {
    (window as any).electronAPI?.maximize?.();
  }, []);

  const handleClose = useCallback(() => {
    (window as any).electronAPI?.close?.();
  }, []);

  return (
    <>
      <style>{pulseKeyframes}</style>
      <div style={styles.topbar}>
        <span style={styles.title}>JARVIS TURBO</span>
        <span style={styles.center}>{PAGE_LABELS[currentPage]}</span>
        <div style={styles.right}>
          {canDetach && (
            <button
              style={{
                background: 'none',
                border: '1px solid #1a2a3a',
                color: '#4a6a8a',
                fontSize: 9,
                padding: '3px 8px',
                borderRadius: 3,
                cursor: 'pointer',
                fontFamily: 'Consolas, Courier New, monospace',
                letterSpacing: 1,
                textTransform: 'uppercase' as const,
                transition: 'all 0.2s ease',
              }}
              onClick={onDetach}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#00d4ff';
                e.currentTarget.style.color = '#00d4ff';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#1a2a3a';
                e.currentTarget.style.color = '#4a6a8a';
              }}
              title="Detach as floating widget"
            >
              Detach
            </button>
          )}
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <div
              style={{
                ...styles.connectionDot,
                ...(connected ? styles.connectionDotConnected : styles.connectionDotDisconnected),
              }}
            />
            <span
              style={{
                ...styles.connectionLabel,
                color: connected ? '#00ff88' : '#ff4444',
              }}
            >
              {connected ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
          <button
            style={styles.winBtn}
            onClick={handleMinimize}
            title="Minimize"
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#1a2a3a';
              e.currentTarget.style.color = '#e0e0e0';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.color = '#4a6a8a';
            }}
          >
            &#x2014;
          </button>
          <button
            style={styles.winBtn}
            onClick={handleMaximize}
            title="Maximize"
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#1a2a3a';
              e.currentTarget.style.color = '#e0e0e0';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.color = '#4a6a8a';
            }}
          >
            &#x25A1;
          </button>
          <button
            style={styles.winBtnClose}
            onClick={handleClose}
            title="Close"
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#ff4444';
              e.currentTarget.style.color = '#ffffff';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.color = '#4a6a8a';
            }}
          >
            &#x2715;
          </button>
        </div>
      </div>
    </>
  );
}
