import React, { useState } from 'react';
import { ClusterNode } from '../../hooks/useCluster';

interface NodeCardProps {
  node: ClusterNode;
}

const styles = {
  card: {
    backgroundColor: '#0d1117',
    border: '1px solid #1a2a3a',
    borderRadius: 8,
    padding: 16,
    transition: 'border-color 0.3s ease, box-shadow 0.3s ease',
    fontFamily: 'Consolas, Courier New, monospace',
  },
  cardHover: {
    borderColor: '#00d4ff',
    boxShadow: '0 0 12px rgba(0, 212, 255, 0.15)',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 14,
  },
  name: {
    fontSize: 16,
    fontWeight: 'bold' as const,
    color: '#00d4ff',
  },
  badge: {
    fontSize: 10,
    fontWeight: 'bold' as const,
    padding: '3px 8px',
    borderRadius: 4,
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
  },
  badgeOnline: {
    backgroundColor: 'rgba(0, 255, 136, 0.15)',
    color: '#00ff88',
    border: '1px solid rgba(0, 255, 136, 0.3)',
  },
  badgeOffline: {
    backgroundColor: 'rgba(255, 68, 68, 0.15)',
    color: '#ff4444',
    border: '1px solid rgba(255, 68, 68, 0.3)',
  },
  badgeDegraded: {
    backgroundColor: 'rgba(255, 170, 0, 0.15)',
    color: '#ffaa00',
    border: '1px solid rgba(255, 170, 0, 0.3)',
  },
  infoGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 10,
    marginBottom: 14,
  },
  infoItem: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 2,
  },
  infoLabel: {
    fontSize: 10,
    color: '#4a6a8a',
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
  },
  infoValue: {
    fontSize: 13,
    color: '#e0e0e0',
  },
  latencyContainer: {
    marginBottom: 14,
  },
  latencyHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  latencyLabel: {
    fontSize: 10,
    color: '#4a6a8a',
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
  },
  latencyValue: {
    fontSize: 12,
    fontWeight: 'bold' as const,
  },
  latencyBarBg: {
    width: '100%',
    height: 4,
    backgroundColor: '#1a2a3a',
    borderRadius: 2,
    overflow: 'hidden' as const,
  },
  latencyBar: {
    height: '100%',
    borderRadius: 2,
    transition: 'width 0.5s ease',
  },
  gpuSection: {
    marginBottom: 10,
  },
  gpuBar: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    marginTop: 4,
    fontSize: 10,
    color: '#4a6a8a',
  },
  gpuBarBg: {
    flex: 1,
    height: 3,
    backgroundColor: '#1a2a3a',
    borderRadius: 2,
    overflow: 'hidden' as const,
  },
  gpuBarFill: {
    height: '100%',
    borderRadius: 2,
    backgroundColor: '#00d4ff',
  },
  modelsContainer: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: 4,
  },
  modelTag: {
    fontSize: 10,
    color: '#e0e0e0',
    backgroundColor: '#1a2a3a',
    padding: '2px 8px',
    borderRadius: 3,
    border: '1px solid #2a3a4a',
  },
  modelTagInactive: {
    color: '#4a6a8a',
    borderColor: '#1a2a3a',
    backgroundColor: '#0a0e14',
  },
};

function getLatencyColor(ms: number): string {
  if (ms < 500) return '#00ff88';
  if (ms < 2000) return '#ffaa00';
  return '#ff4444';
}

function getLatencyPercent(ms: number): number {
  return Math.min((ms / 5000) * 100, 100);
}

function formatVram(mb: number): string {
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${mb} MB`;
}

function getStatusBadgeStyle(status: ClusterNode['status']) {
  switch (status) {
    case 'online': return styles.badgeOnline;
    case 'offline': return styles.badgeOffline;
    case 'degraded': return styles.badgeDegraded;
    default: return styles.badgeOffline;
  }
}

function getStatusLabel(status: ClusterNode['status']) {
  switch (status) {
    case 'online': return 'ONLINE';
    case 'offline': return 'OFFLINE';
    case 'degraded': return 'DEGRADED';
    default: return 'UNKNOWN';
  }
}

export default function NodeCard({ node }: NodeCardProps) {
  const [hovered, setHovered] = useState(false);
  const isOnline = node.status !== 'offline';
  const latencyColor = getLatencyColor(node.latency);

  // First loaded model name
  const loadedModels = node.models.filter((m) => m.loaded);
  const firstModel = loadedModels.length > 0 ? loadedModels[0].name : (node.models[0]?.name || 'N/A');

  // VRAM usage
  const vramPercent = node.vram_total > 0 ? (node.vram_used / node.vram_total) * 100 : 0;

  return (
    <div
      style={{
        ...styles.card,
        ...(hovered ? styles.cardHover : {}),
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Header */}
      <div style={styles.header}>
        <span style={styles.name}>{node.name}</span>
        <span
          style={{
            ...styles.badge,
            ...getStatusBadgeStyle(node.status),
          }}
        >
          {getStatusLabel(node.status)}
        </span>
      </div>

      {/* Info Grid */}
      <div style={styles.infoGrid}>
        <div style={styles.infoItem}>
          <span style={styles.infoLabel}>Model</span>
          <span style={{ ...styles.infoValue, fontSize: 11 }}>{firstModel}</span>
        </div>
        <div style={styles.infoItem}>
          <span style={styles.infoLabel}>GPUs</span>
          <span style={styles.infoValue}>{node.gpus.length}</span>
        </div>
        <div style={styles.infoItem}>
          <span style={styles.infoLabel}>VRAM Total</span>
          <span style={styles.infoValue}>{formatVram(node.vram_total)}</span>
        </div>
        <div style={styles.infoItem}>
          <span style={styles.infoLabel}>VRAM Used</span>
          <span style={{ ...styles.infoValue, color: vramPercent > 90 ? '#ff4444' : vramPercent > 70 ? '#ffaa00' : '#e0e0e0' }}>
            {formatVram(node.vram_used)}
          </span>
        </div>
      </div>

      {/* VRAM Usage Bar */}
      {node.vram_total > 0 && (
        <div style={styles.gpuSection}>
          <div style={styles.gpuBar}>
            <span>VRAM</span>
            <div style={styles.gpuBarBg}>
              <div
                style={{
                  ...styles.gpuBarFill,
                  width: `${vramPercent}%`,
                  backgroundColor: vramPercent > 90 ? '#ff4444' : vramPercent > 70 ? '#ffaa00' : '#00d4ff',
                }}
              />
            </div>
            <span>{vramPercent.toFixed(0)}%</span>
          </div>
        </div>
      )}

      {/* GPU Temperature if available */}
      {node.gpus.length > 0 && node.gpus.some((g) => g.temperature != null) && (
        <div style={{ marginBottom: 10 }}>
          {node.gpus.map((gpu, i) => (
            <div key={i} style={{ fontSize: 10, color: '#4a6a8a', marginBottom: 2 }}>
              <span style={{ color: '#e0e0e0' }}>{gpu.name}</span>
              {gpu.temperature != null && (
                <span
                  style={{
                    marginLeft: 8,
                    color: gpu.temperature > 85 ? '#ff4444' : gpu.temperature > 75 ? '#ffaa00' : '#00ff88',
                  }}
                >
                  {gpu.temperature}C
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Latency Bar */}
      <div style={styles.latencyContainer}>
        <div style={styles.latencyHeader}>
          <span style={styles.latencyLabel}>Latency</span>
          <span style={{ ...styles.latencyValue, color: latencyColor }}>
            {isOnline ? `${node.latency}ms` : '---'}
          </span>
        </div>
        <div style={styles.latencyBarBg}>
          <div
            style={{
              ...styles.latencyBar,
              width: isOnline ? `${getLatencyPercent(node.latency)}%` : '0%',
              backgroundColor: latencyColor,
            }}
          />
        </div>
      </div>

      {/* Models */}
      {node.models.length > 0 && (
        <div style={styles.modelsContainer}>
          {node.models.map((model) => (
            <span
              key={model.id}
              style={{
                ...styles.modelTag,
                ...(model.loaded ? {} : styles.modelTagInactive),
              }}
            >
              {model.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
