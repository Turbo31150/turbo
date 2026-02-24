import React from 'react';
import { useCluster } from '../hooks/useCluster';
import NodeCard from '../components/cluster/NodeCard';

const styles = {
  page: {
    padding: 20,
    fontFamily: 'Consolas, Courier New, monospace',
    height: '100%',
    overflowY: 'auto' as const,
  },
  statusBar: {
    display: 'flex',
    gap: 16,
    marginBottom: 20,
    flexWrap: 'wrap' as const,
  },
  statCard: {
    backgroundColor: '#0d1117',
    border: '1px solid #1a2a3a',
    borderRadius: 6,
    padding: '12px 20px',
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 4,
    minWidth: 140,
  },
  statLabel: {
    fontSize: 10,
    color: '#4a6a8a',
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
  },
  statValue: {
    fontSize: 22,
    fontWeight: 'bold' as const,
    color: '#e0e0e0',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
    gap: 16,
  },
  headerRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  title: {
    fontSize: 18,
    fontWeight: 'bold' as const,
    color: '#e0e0e0',
  },
  refreshBtn: {
    padding: '6px 14px',
    borderRadius: 4,
    border: '1px solid #1a2a3a',
    backgroundColor: '#0d1117',
    color: '#4a6a8a',
    fontSize: 11,
    cursor: 'pointer',
    fontFamily: 'Consolas, Courier New, monospace',
    transition: 'all 0.2s ease',
  },
  errorBanner: {
    padding: '8px 14px',
    backgroundColor: 'rgba(255, 68, 68, 0.1)',
    border: '1px solid rgba(255, 68, 68, 0.25)',
    borderRadius: 6,
    color: '#ff4444',
    fontSize: 12,
    marginBottom: 16,
  },
  refreshIndicator: {
    position: 'fixed' as const,
    bottom: 16,
    right: 16,
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 10,
    color: '#4a6a8a',
    backgroundColor: '#0d1117',
    border: '1px solid #1a2a3a',
    borderRadius: 4,
    padding: '4px 10px',
  },
  refreshDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    backgroundColor: '#00d4ff',
  },
};

const pulseKeyframes = `
@keyframes refresh-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
`;

function formatVram(mb: number): string {
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${mb} MB`;
}

export default function DashboardPage() {
  const { nodes, loading, error, refreshCluster } = useCluster();

  const onlineCount = nodes.filter((n) => n.status === 'online').length;
  const degradedCount = nodes.filter((n) => n.status === 'degraded').length;
  const totalGPUs = nodes.reduce((sum, n) => sum + n.gpus.length, 0);
  const totalVRAM = nodes.reduce((sum, n) => sum + n.vram_total, 0);

  return (
    <>
      <style>{pulseKeyframes}</style>
      <div style={styles.page}>
        <div style={styles.headerRow}>
          <div style={styles.title}>Cluster Overview</div>
          <button
            style={styles.refreshBtn}
            onClick={refreshCluster}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = '#00d4ff';
              e.currentTarget.style.color = '#00d4ff';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = '#1a2a3a';
              e.currentTarget.style.color = '#4a6a8a';
            }}
          >
            {loading ? 'Actualisation...' : 'Actualiser'}
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div style={styles.errorBanner}>
            {error}
          </div>
        )}

        {/* Status Bar */}
        <div style={styles.statusBar}>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>Nodes</span>
            <span style={styles.statValue}>{nodes.length}</span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>Online</span>
            <span style={{ ...styles.statValue, color: onlineCount > 0 ? '#00ff88' : '#ff4444' }}>
              {onlineCount}
              {degradedCount > 0 && (
                <span style={{ fontSize: 12, color: '#ffaa00', marginLeft: 6 }}>
                  +{degradedCount} degraded
                </span>
              )}
            </span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>Total GPUs</span>
            <span style={{ ...styles.statValue, color: '#00d4ff' }}>{totalGPUs}</span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>Total VRAM</span>
            <span style={{ ...styles.statValue, color: '#00d4ff' }}>{formatVram(totalVRAM)}</span>
          </div>
        </div>

        {/* Node Grid */}
        <div style={styles.grid}>
          {nodes.map((node) => (
            <NodeCard key={node.name} node={node} />
          ))}
          {nodes.length === 0 && !loading && (
            <div
              style={{
                gridColumn: '1 / -1',
                textAlign: 'center',
                color: '#4a6a8a',
                padding: 40,
                fontSize: 13,
              }}
            >
              {error ? 'Impossible de charger les noeuds du cluster.' : 'En attente de connexion au cluster...'}
            </div>
          )}
        </div>

        {/* Loading indicator */}
        {loading && (
          <div style={styles.refreshIndicator}>
            <div
              style={{
                ...styles.refreshDot,
                animation: 'refresh-pulse 1s ease-in-out infinite',
              }}
            />
            <span>Actualisation...</span>
          </div>
        )}
      </div>
    </>
  );
}
