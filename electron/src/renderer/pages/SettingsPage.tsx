import React, { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

interface ClusterNodeConfig {
  name: string;
  url: string;
  status: 'online' | 'offline' | 'degraded';
  enabled: boolean;
}

interface TradingConfig {
  pairs: string[];
  leverage: number;
  tpPercent: number;
  slPercent: number;
  sizeUSDT: number;
  dryRun: boolean;
}

interface VoiceConfig {
  wakeWord: string;
  confidenceThreshold: number;
  ttsEngine: string;
}

interface GeneralConfig {
  theme: string;
  language: string;
  autoStart: boolean;
}

interface AppConfig {
  cluster: ClusterNodeConfig[];
  trading: TradingConfig;
  voice: VoiceConfig;
  general: GeneralConfig;
}

const DEFAULT_CONFIG: AppConfig = {
  cluster: [
    { name: 'M1', url: 'http://10.5.0.2:1234', status: 'offline', enabled: true },
    { name: 'M2', url: 'http://192.168.1.26:1234', status: 'offline', enabled: true },
    { name: 'M3', url: 'http://192.168.1.113:1234', status: 'offline', enabled: true },
    { name: 'OL1', url: 'http://127.0.0.1:11434', status: 'offline', enabled: true },
    { name: 'GEMINI', url: 'gemini-proxy.js', status: 'offline', enabled: true },
  ],
  trading: {
    pairs: ['BTC', 'ETH', 'SOL', 'SUI', 'PEPE', 'DOGE', 'XRP', 'ADA', 'AVAX', 'LINK'],
    leverage: 10,
    tpPercent: 0.4,
    slPercent: 0.25,
    sizeUSDT: 10,
    dryRun: false,
  },
  voice: {
    wakeWord: 'jarvis',
    confidenceThreshold: 0.85,
    ttsEngine: 'windows',
  },
  general: {
    theme: 'dark',
    language: 'fr',
    autoStart: false,
  },
};

const styles = {
  page: {
    padding: 20,
    fontFamily: 'Consolas, Courier New, monospace',
    height: '100%',
    overflowY: 'auto' as const,
  },
  title: {
    fontSize: 18,
    fontWeight: 'bold' as const,
    color: '#e0e0e0',
    marginBottom: 20,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  section: {
    backgroundColor: '#0d1117',
    border: '1px solid #1a2a3a',
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: 'bold' as const,
    color: '#00d4ff',
    marginBottom: 14,
    paddingBottom: 8,
    borderBottom: '1px solid #1a2a3a',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  row: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 0',
    borderBottom: '1px solid #0a0e14',
  },
  rowLabel: {
    fontSize: 12,
    color: '#4a6a8a',
  },
  rowValue: {
    fontSize: 12,
    color: '#e0e0e0',
  },
  toggleTrack: {
    width: 36,
    height: 18,
    borderRadius: 9,
    position: 'relative' as const,
    cursor: 'default',
    transition: 'background-color 0.2s ease',
  },
  toggleTrackOn: {
    backgroundColor: 'rgba(0, 212, 255, 0.4)',
  },
  toggleTrackOff: {
    backgroundColor: '#1a2a3a',
  },
  toggleThumb: {
    width: 14,
    height: 14,
    borderRadius: '50%',
    position: 'absolute' as const,
    top: 2,
    transition: 'left 0.2s ease',
  },
  toggleThumbOn: {
    left: 20,
    backgroundColor: '#00d4ff',
  },
  toggleThumbOff: {
    left: 2,
    backgroundColor: '#4a6a8a',
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    display: 'inline-block',
    marginRight: 6,
  },
  nodeRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 0',
    borderBottom: '1px solid #0a0e14',
    gap: 12,
  },
  nodeInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flex: 1,
  },
  nodeName: {
    fontSize: 12,
    fontWeight: 'bold' as const,
    color: '#e0e0e0',
    minWidth: 50,
  },
  nodeUrl: {
    fontSize: 11,
    color: '#4a6a8a',
  },
  pairTag: {
    display: 'inline-block',
    padding: '2px 8px',
    backgroundColor: '#1a2a3a',
    borderRadius: 3,
    fontSize: 10,
    color: '#e0e0e0',
    border: '1px solid #2a3a4a',
    margin: 2,
  },
  pairsContainer: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: 4,
  },
  saveBtn: {
    padding: '10px 24px',
    backgroundColor: '#00d4ff',
    color: '#0a0e14',
    border: 'none',
    borderRadius: 6,
    fontWeight: 'bold' as const,
    fontFamily: 'Consolas, Courier New, monospace',
    fontSize: 12,
    cursor: 'pointer',
    letterSpacing: 1,
    textTransform: 'uppercase' as const,
    transition: 'opacity 0.2s ease',
    marginTop: 8,
  },
  readOnlyBadge: {
    fontSize: 9,
    color: '#4a6a8a',
    backgroundColor: '#1a2a3a',
    padding: '2px 6px',
    borderRadius: 3,
  },
  nodeStatusLabel: {
    fontSize: 9,
    fontWeight: 'bold' as const,
    textTransform: 'uppercase' as const,
    letterSpacing: 0.5,
    padding: '1px 5px',
    borderRadius: 3,
    marginRight: 8,
  },
};

function Toggle({ on }: { on: boolean }) {
  return (
    <div
      style={{
        ...styles.toggleTrack,
        ...(on ? styles.toggleTrackOn : styles.toggleTrackOff),
      }}
    >
      <div
        style={{
          ...styles.toggleThumb,
          ...(on ? styles.toggleThumbOn : styles.toggleThumbOff),
        }}
      />
    </div>
  );
}

function getStatusDotColor(status: string): string {
  switch (status) {
    case 'online': return '#00ff88';
    case 'degraded': return '#ffaa00';
    default: return '#ff4444';
  }
}

export default function SettingsPage() {
  const { connected, request } = useWebSocket();
  const [config, setConfig] = useState<AppConfig>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);

  // Fetch config via WebSocket
  useEffect(() => {
    if (!connected) {
      setLoading(false);
      return;
    }

    (async () => {
      try {
        const response = await request('system', 'get_config');
        if (response.payload) {
          setConfig((prev) => ({ ...prev, ...response.payload }));
        }
      } catch {
        // Config not available, use defaults
      }
      setLoading(false);
    })();
  }, [connected, request]);

  const saveConfig = useCallback(async () => {
    if (!connected) return;
    try {
      await request('system', 'update_config', config);
    } catch {
      // Save failed
    }
  }, [connected, config, request]);

  if (loading) {
    return (
      <div style={{ ...styles.page, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: '#4a6a8a', fontSize: 13 }}>Chargement de la configuration...</span>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.title}>
        Configuration
        <span style={styles.readOnlyBadge}>LECTURE SEULE v1</span>
      </div>

      {/* Cluster Section */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <span>&#x25A6;</span> Cluster
        </div>
        {config.cluster.map((node) => (
          <div key={node.name} style={styles.nodeRow}>
            <div style={styles.nodeInfo}>
              <span
                style={{
                  ...styles.statusDot,
                  backgroundColor: getStatusDotColor(node.status),
                }}
              />
              <span style={styles.nodeName}>{node.name}</span>
              <span style={styles.nodeUrl}>{node.url}</span>
            </div>
            <Toggle on={node.enabled} />
          </div>
        ))}
      </div>

      {/* Trading Section */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <span>&#x25B2;</span> Trading
        </div>
        <div style={styles.row}>
          <span style={styles.rowLabel}>Paires</span>
          <div style={styles.pairsContainer}>
            {config.trading.pairs.map((pair) => (
              <span key={pair} style={styles.pairTag}>{pair}</span>
            ))}
          </div>
        </div>
        <div style={styles.row}>
          <span style={styles.rowLabel}>Levier</span>
          <span style={styles.rowValue}>{config.trading.leverage}x</span>
        </div>
        <div style={styles.row}>
          <span style={styles.rowLabel}>Take Profit</span>
          <span style={{ ...styles.rowValue, color: '#00ff88' }}>{config.trading.tpPercent}%</span>
        </div>
        <div style={styles.row}>
          <span style={styles.rowLabel}>Stop Loss</span>
          <span style={{ ...styles.rowValue, color: '#ff4444' }}>{config.trading.slPercent}%</span>
        </div>
        <div style={styles.row}>
          <span style={styles.rowLabel}>Taille Position</span>
          <span style={styles.rowValue}>{config.trading.sizeUSDT} USDT</span>
        </div>
        <div style={styles.row}>
          <span style={styles.rowLabel}>Dry Run</span>
          <Toggle on={config.trading.dryRun} />
        </div>
      </div>

      {/* Voice Section */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <span>&#x25C9;</span> Voice
        </div>
        <div style={styles.row}>
          <span style={styles.rowLabel}>Wake Word</span>
          <span style={{ ...styles.rowValue, color: '#00d4ff' }}>"{config.voice.wakeWord}"</span>
        </div>
        <div style={styles.row}>
          <span style={styles.rowLabel}>Confidence Threshold</span>
          <span style={styles.rowValue}>{config.voice.confidenceThreshold}</span>
        </div>
        <div style={styles.row}>
          <span style={styles.rowLabel}>TTS Engine</span>
          <span style={styles.rowValue}>{config.voice.ttsEngine}</span>
        </div>
      </div>

      {/* General Section */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <span>&#x2699;</span> General
        </div>
        <div style={styles.row}>
          <span style={styles.rowLabel}>Theme</span>
          <span style={styles.rowValue}>{config.general.theme}</span>
        </div>
        <div style={styles.row}>
          <span style={styles.rowLabel}>Langue</span>
          <span style={styles.rowValue}>{config.general.language}</span>
        </div>
        <div style={styles.row}>
          <span style={styles.rowLabel}>Auto-start</span>
          <Toggle on={config.general.autoStart} />
        </div>
      </div>

      {/* Save button */}
      <button
        style={styles.saveBtn}
        onClick={saveConfig}
        onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.8'; }}
        onMouseLeave={(e) => { e.currentTarget.style.opacity = '1'; }}
      >
        Sauvegarder
      </button>
    </div>
  );
}
