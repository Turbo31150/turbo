import React, { memo } from 'react';
import { ClusterNode } from '../../hooks/useCluster';
import { COLORS, FONT, latencyColor, pctColor } from '../../lib/theme';

interface NodeCardProps {
  node: ClusterNode;
}

const CSS = `
@keyframes ncFadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.nc-card{animation:ncFadeIn .3s ease;transition:border-color .3s,box-shadow .3s}
.nc-card:hover{border-color:${COLORS.orangeAlpha(0.3)}!important;box-shadow:0 0 12px ${COLORS.orangeAlpha(0.1)}!important}
`;

const S = {
  card: { backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 10, padding: 16, fontFamily: FONT } as React.CSSProperties,
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 } as React.CSSProperties,
  name: { fontSize: 16, fontWeight: 700, color: COLORS.orange } as React.CSSProperties,
  badge: { fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 6, textTransform: 'uppercase', letterSpacing: 1 } as React.CSSProperties,
  online: { backgroundColor: COLORS.greenAlpha(0.12), color: COLORS.green, border: `1px solid ${COLORS.greenAlpha(0.25)}` },
  offline: { backgroundColor: COLORS.redAlpha(0.12), color: COLORS.red, border: `1px solid ${COLORS.redAlpha(0.25)}` },
  degraded: { backgroundColor: COLORS.orangeAlpha(0.12), color: COLORS.orange, border: `1px solid ${COLORS.orangeAlpha(0.25)}` },
  infoGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 } as React.CSSProperties,
  infoItem: { display: 'flex', flexDirection: 'column', gap: 2 } as React.CSSProperties,
  infoLabel: { fontSize: 10, color: COLORS.textDim, textTransform: 'uppercase', letterSpacing: 1 } as React.CSSProperties,
  infoValue: { fontSize: 13, color: COLORS.text } as React.CSSProperties,
  latWrap: { marginBottom: 14 } as React.CSSProperties,
  latHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 } as React.CSSProperties,
  latLabel: { fontSize: 10, color: COLORS.textDim, textTransform: 'uppercase', letterSpacing: 1 } as React.CSSProperties,
  latValue: { fontSize: 12, fontWeight: 700 } as React.CSSProperties,
  barBg: { width: '100%', height: 4, backgroundColor: COLORS.border, borderRadius: 2, overflow: 'hidden' } as React.CSSProperties,
  barFill: { height: '100%', borderRadius: 2, transition: 'width .5s ease' } as React.CSSProperties,
  gpuSection: { marginBottom: 10 } as React.CSSProperties,
  gpuBar: { display: 'flex', alignItems: 'center', gap: 6, marginTop: 4, fontSize: 10, color: COLORS.textDim } as React.CSSProperties,
  gpuBarBg: { flex: 1, height: 3, backgroundColor: COLORS.border, borderRadius: 2, overflow: 'hidden' } as React.CSSProperties,
  gpuBarFill: { height: '100%', borderRadius: 2, backgroundColor: COLORS.orange } as React.CSSProperties,
  modelsWrap: { display: 'flex', flexWrap: 'wrap', gap: 4 } as React.CSSProperties,
  modelTag: { fontSize: 10, color: COLORS.text, backgroundColor: COLORS.border, padding: '2px 8px', borderRadius: 4, border: `1px solid ${COLORS.border}` } as React.CSSProperties,
  modelInactive: { color: COLORS.textDim, borderColor: COLORS.border, backgroundColor: COLORS.bg },
};

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

export default memo(function NodeCard({ node }: NodeCardProps) {
  const isOnline = node.status !== 'offline';
  const latColor = latencyColor(node.latency);
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
            <span style={{ ...S.infoValue, color: pctColor(vramPercent) }}>
              {formatVram(node.vram_used)}
            </span>
          </div>
        </div>

        {node.vram_total > 0 && (
          <div style={S.gpuSection}>
            <div style={S.gpuBar}>
              <span>VRAM</span>
              <div style={S.gpuBarBg}>
                <div style={{ ...S.gpuBarFill, width: `${vramPercent}%`, backgroundColor: pctColor(vramPercent) }} />
              </div>
              <span>{vramPercent.toFixed(0)}%</span>
            </div>
          </div>
        )}

        {node.gpus.length > 0 && node.gpus.some(g => g.temperature != null) && (
          <div style={{ marginBottom: 10 }}>
            {node.gpus.map((gpu, i) => (
              <div key={i} style={{ fontSize: 10, color: COLORS.textDim, marginBottom: 2 }}>
                <span style={{ color: COLORS.text }}>{gpu.name}</span>
                {gpu.temperature != null && (
                  <span style={{ marginLeft: 8, color: gpu.temperature > 85 ? COLORS.red : gpu.temperature > 75 ? COLORS.orange : COLORS.green }}>
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
            <span style={{ ...S.latValue, color: latColor }}>{isOnline ? `${node.latency}ms` : '---'}</span>
          </div>
          <div style={S.barBg}>
            <div style={{ ...S.barFill, width: isOnline ? `${Math.min((node.latency / 5000) * 100, 100)}%` : '0%', backgroundColor: latColor }} />
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
});
