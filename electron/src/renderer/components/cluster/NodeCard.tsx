import React, { useState } from 'react';
import { ClusterNode } from '../../hooks/useCluster';

interface NodeCardProps {
  node: ClusterNode;
}

const CSS = `
@keyframes ncFadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.nc-card{animation:ncFadeIn .3s ease;transition:border-color .3s,box-shadow .3s}
.nc-card:hover{border-color:rgba(249,115,22,.3)!important;box-shadow:0 0 12px rgba(249,115,22,.1)!important}
`;

const S = {
  card: { backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 10, padding: 16, fontFamily: 'Consolas, "Courier New", monospace' } as React.CSSProperties,
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 } as React.CSSProperties,
  name: { fontSize: 16, fontWeight: 700, color: '#f97316' } as React.CSSProperties,
  badge: { fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 6, textTransform: 'uppercase', letterSpacing: 1 } as React.CSSProperties,
  online: { backgroundColor: 'rgba(16,185,129,.12)', color: '#10b981', border: '1px solid rgba(16,185,129,.25)' },
  offline: { backgroundColor: 'rgba(239,68,68,.12)', color: '#ef4444', border: '1px solid rgba(239,68,68,.25)' },
  degraded: { backgroundColor: 'rgba(249,115,22,.12)', color: '#f97316', border: '1px solid rgba(249,115,22,.25)' },
  infoGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 } as React.CSSProperties,
  infoItem: { display: 'flex', flexDirection: 'column', gap: 2 } as React.CSSProperties,
  infoLabel: { fontSize: 10, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1 } as React.CSSProperties,
  infoValue: { fontSize: 13, color: '#e0e0e0' } as React.CSSProperties,
  latWrap: { marginBottom: 14 } as React.CSSProperties,
  latHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 } as React.CSSProperties,
  latLabel: { fontSize: 10, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1 } as React.CSSProperties,
  latValue: { fontSize: 12, fontWeight: 700 } as React.CSSProperties,
  barBg: { width: '100%', height: 4, backgroundColor: '#1a2a3a', borderRadius: 2, overflow: 'hidden' } as React.CSSProperties,
  barFill: { height: '100%', borderRadius: 2, transition: 'width .5s ease' } as React.CSSProperties,
  gpuSection: { marginBottom: 10 } as React.CSSProperties,
  gpuBar: { display: 'flex', alignItems: 'center', gap: 6, marginTop: 4, fontSize: 10, color: '#6b7280' } as React.CSSProperties,
  gpuBarBg: { flex: 1, height: 3, backgroundColor: '#1a2a3a', borderRadius: 2, overflow: 'hidden' } as React.CSSProperties,
  gpuBarFill: { height: '100%', borderRadius: 2, backgroundColor: '#f97316' } as React.CSSProperties,
  modelsWrap: { display: 'flex', flexWrap: 'wrap', gap: 4 } as React.CSSProperties,
  modelTag: { fontSize: 10, color: '#e0e0e0', backgroundColor: '#1a2a3a', padding: '2px 8px', borderRadius: 4, border: '1px solid #2a3a4a' } as React.CSSProperties,
  modelInactive: { color: '#6b7280', borderColor: '#1a2a3a', backgroundColor: '#0a0e14' },
};

function getLatencyColor(ms: number): string {
  if (ms < 500) return '#10b981';
  if (ms < 2000) return '#f97316';
  return '#ef4444';
}

function formatVram(mb: number): string {
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${mb} MB`;
}

function getStatusStyle(status: ClusterNode['status']) {
  switch (status) {
    case 'online': return S.online;
    case 'offline': return S.offline;
    case 'degraded': return S.degraded;
    default: return S.offline;
  }
}

export default function NodeCard({ node }: NodeCardProps) {
  const isOnline = node.status !== 'offline';
  const latencyColor = getLatencyColor(node.latency);
  const loadedModels = node.models.filter(m => m.loaded);
  const firstModel = loadedModels.length > 0 ? loadedModels[0].name : (node.models[0]?.name || 'N/A');
  const vramPercent = node.vram_total > 0 ? (node.vram_used / node.vram_total) * 100 : 0;

  return (
    <>
      <style>{CSS}</style>
      <div className="nc-card" style={S.card}>
        <div style={S.header}>
          <span style={S.name}>{node.name}</span>
          <span style={{ ...S.badge, ...getStatusStyle(node.status) }}>
            {node.status === 'online' ? 'ONLINE' : node.status === 'offline' ? 'OFFLINE' : 'DEGRADED'}
          </span>
        </div>

        <div style={S.infoGrid}>
          <div style={S.infoItem}>
            <span style={S.infoLabel}>Model</span>
            <span style={{ ...S.infoValue, fontSize: 11 }}>{firstModel}</span>
          </div>
          <div style={S.infoItem}>
            <span style={S.infoLabel}>GPUs</span>
            <span style={S.infoValue}>{node.gpus.length}</span>
          </div>
          <div style={S.infoItem}>
            <span style={S.infoLabel}>VRAM Total</span>
            <span style={S.infoValue}>{formatVram(node.vram_total)}</span>
          </div>
          <div style={S.infoItem}>
            <span style={S.infoLabel}>VRAM Used</span>
            <span style={{ ...S.infoValue, color: vramPercent > 90 ? '#ef4444' : vramPercent > 70 ? '#f97316' : '#e0e0e0' }}>
              {formatVram(node.vram_used)}
            </span>
          </div>
        </div>

        {node.vram_total > 0 && (
          <div style={S.gpuSection}>
            <div style={S.gpuBar}>
              <span>VRAM</span>
              <div style={S.gpuBarBg}>
                <div style={{ ...S.gpuBarFill, width: `${vramPercent}%`, backgroundColor: vramPercent > 90 ? '#ef4444' : vramPercent > 70 ? '#f97316' : '#f97316' }} />
              </div>
              <span>{vramPercent.toFixed(0)}%</span>
            </div>
          </div>
        )}

        {node.gpus.length > 0 && node.gpus.some(g => g.temperature != null) && (
          <div style={{ marginBottom: 10 }}>
            {node.gpus.map((gpu, i) => (
              <div key={i} style={{ fontSize: 10, color: '#6b7280', marginBottom: 2 }}>
                <span style={{ color: '#e0e0e0' }}>{gpu.name}</span>
                {gpu.temperature != null && (
                  <span style={{ marginLeft: 8, color: gpu.temperature > 85 ? '#ef4444' : gpu.temperature > 75 ? '#f97316' : '#10b981' }}>
                    {gpu.temperature}C
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        <div style={S.latWrap}>
          <div style={S.latHeader}>
            <span style={S.latLabel}>Latency</span>
            <span style={{ ...S.latValue, color: latencyColor }}>{isOnline ? `${node.latency}ms` : '---'}</span>
          </div>
          <div style={S.barBg}>
            <div style={{ ...S.barFill, width: isOnline ? `${Math.min((node.latency / 5000) * 100, 100)}%` : '0%', backgroundColor: latencyColor }} />
          </div>
        </div>

        {node.models.length > 0 && (
          <div style={S.modelsWrap}>
            {node.models.map(model => (
              <span key={model.id} style={{ ...S.modelTag, ...(model.loaded ? {} : S.modelInactive) }}>
                {model.name}
              </span>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
