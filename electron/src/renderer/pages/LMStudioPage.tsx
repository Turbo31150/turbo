import React, { useState } from 'react';
import { useLMStudio, LMNode, LMModel } from '../hooks/useLMStudio';

const s = {
  page: { padding: 20, fontFamily: 'Consolas, Courier New, monospace', height: '100%', overflowY: 'auto' as const },
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  title: { fontSize: 18, fontWeight: 'bold' as const, color: '#e0e0e0' },
  btn: { padding: '6px 14px', borderRadius: 4, border: '1px solid #1a2a3a', backgroundColor: '#0d1117', color: '#4a6a8a', fontSize: 11, cursor: 'pointer', fontFamily: 'Consolas, Courier New, monospace', transition: 'all 0.2s' },
  statsRow: { display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap' as const },
  stat: { backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 6, padding: '12px 20px', display: 'flex', flexDirection: 'column' as const, gap: 4, minWidth: 130 },
  statLabel: { fontSize: 10, color: '#4a6a8a', textTransform: 'uppercase' as const, letterSpacing: 1 },
  statVal: { fontSize: 22, fontWeight: 'bold' as const, color: '#e0e0e0' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 16 },
  card: { backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 8, padding: 16, transition: 'border-color 0.3s' },
  cardHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 },
  nodeName: { fontSize: 16, fontWeight: 'bold' as const, color: '#00d4ff' },
  badge: { fontSize: 10, fontWeight: 'bold' as const, padding: '3px 8px', borderRadius: 4, textTransform: 'uppercase' as const, letterSpacing: 1 },
  online: { backgroundColor: 'rgba(0,255,136,0.15)', color: '#00ff88', border: '1px solid rgba(0,255,136,0.3)' },
  offline: { backgroundColor: 'rgba(255,68,68,0.15)', color: '#ff4444', border: '1px solid rgba(255,68,68,0.3)' },
  loading: { backgroundColor: 'rgba(255,170,0,0.15)', color: '#ffaa00', border: '1px solid rgba(255,170,0,0.3)' },
  modelRow: { display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: '1px solid #1a2a3a' },
  modelName: { flex: 1, fontSize: 12, color: '#e0e0e0', fontWeight: 500 as const },
  modelMeta: { fontSize: 10, color: '#4a6a8a' },
  modelLoaded: { width: 8, height: 8, borderRadius: '50%', backgroundColor: '#00ff88', boxShadow: '0 0 6px rgba(0,255,136,0.5)' },
  modelUnloaded: { width: 8, height: 8, borderRadius: '50%', backgroundColor: '#4a6a8a' },
  testArea: { marginTop: 12, backgroundColor: '#0a0e14', borderRadius: 6, padding: 12, border: '1px solid #1a2a3a' },
  testInput: { width: '100%', padding: '8px 10px', backgroundColor: '#0d1117', border: '1px solid #2a3a4a', borderRadius: 4, color: '#e0e0e0', fontSize: 12, fontFamily: 'Consolas, Courier New, monospace', outline: 'none', marginBottom: 8 },
  testBtn: { padding: '5px 12px', borderRadius: 4, border: '1px solid #00d4ff', backgroundColor: 'rgba(0,212,255,0.08)', color: '#00d4ff', fontSize: 11, cursor: 'pointer', fontFamily: 'Consolas, Courier New, monospace' },
  testResult: { marginTop: 8, fontSize: 11, color: '#e0e0e0', whiteSpace: 'pre-wrap' as const, maxHeight: 200, overflowY: 'auto' as const, lineHeight: 1.5 },
  latency: { fontSize: 10, color: '#00ff88', marginTop: 4 },
  errorText: { fontSize: 11, color: '#ff4444', padding: 8 },
};

function ModelItem({ model }: { model: LMModel }) {
  return (
    <div style={s.modelRow}>
      <div style={model.loaded ? s.modelLoaded : s.modelUnloaded} />
      <span style={s.modelName}>{model.id}</span>
      {model.size_gb && <span style={s.modelMeta}>{model.size_gb} GB</span>}
      {model.context_length && <span style={s.modelMeta}>ctx:{model.context_length}</span>}
      {model.gpu_offload && <span style={s.modelMeta}>GPU:{model.gpu_offload}</span>}
      {model.loaded && <span style={{ ...s.modelMeta, color: '#00ff88' }}>LOADED</span>}
    </div>
  );
}

function NodePanel({ node, onTest }: { node: LMNode; onTest: (nodeId: string, model: string, prompt: string) => Promise<{ text: string; latency: number }> }) {
  const [testPrompt, setTestPrompt] = useState('Reponds OK en 1 mot.');
  const [testResult, setTestResult] = useState<{ text: string; latency: number } | null>(null);
  const [testing, setTesting] = useState(false);
  const [showTest, setShowTest] = useState(false);

  const loadedModels = node.models.filter(m => m.loaded);
  const firstLoaded = loadedModels[0]?.id || '';

  const handleTest = async () => {
    if (!firstLoaded || testing) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await onTest(node.id, firstLoaded, testPrompt);
      setTestResult(res);
    } catch (e: any) {
      setTestResult({ text: `Erreur: ${e.message}`, latency: -1 });
    }
    setTesting(false);
  };

  const badgeStyle = node.status === 'online' ? s.online : node.status === 'offline' ? s.offline : s.loading;

  return (
    <div style={s.card}>
      <div style={s.cardHeader}>
        <span style={s.nodeName}>{node.id}</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {node.latency > 0 && (
            <span style={{ fontSize: 10, color: node.latency < 500 ? '#00ff88' : node.latency < 2000 ? '#ffaa00' : '#ff4444' }}>
              {node.latency}ms
            </span>
          )}
          <span style={{ ...s.badge, ...badgeStyle }}>{node.status}</span>
        </div>
      </div>

      <div style={{ fontSize: 10, color: '#4a6a8a', marginBottom: 10 }}>{node.name}</div>

      {node.error && <div style={s.errorText}>{node.error}</div>}

      {node.models.length > 0 ? (
        <>
          <div style={{ fontSize: 10, color: '#4a6a8a', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>
            Modeles ({loadedModels.length} charges / {node.models.length} total)
          </div>
          {node.models.map(m => <ModelItem key={m.id} model={m} />)}
        </>
      ) : node.status === 'online' ? (
        <div style={{ fontSize: 11, color: '#4a6a8a', padding: 8 }}>Aucun modele</div>
      ) : null}

      {node.status === 'online' && firstLoaded && (
        <>
          <button
            style={{ ...s.testBtn, marginTop: 12 }}
            onClick={() => setShowTest(!showTest)}
          >
            {showTest ? 'Masquer test' : 'Tester inference'}
          </button>

          {showTest && (
            <div style={s.testArea}>
              <input
                style={s.testInput}
                value={testPrompt}
                onChange={e => setTestPrompt(e.target.value)}
                placeholder="Prompt de test..."
                onKeyDown={e => e.key === 'Enter' && handleTest()}
              />
              <button style={s.testBtn} onClick={handleTest} disabled={testing}>
                {testing ? 'En cours...' : `Envoyer a ${node.id}`}
              </button>
              {testResult && (
                <>
                  <div style={s.testResult}>{testResult.text}</div>
                  {testResult.latency > 0 && <div style={s.latency}>{testResult.latency}ms</div>}
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function LMStudioPage() {
  const { nodes, refreshing, refresh, testModel } = useLMStudio();

  const onlineCount = nodes.filter(n => n.status === 'online').length;
  const totalLoaded = nodes.reduce((sum, n) => sum + n.models.filter(m => m.loaded).length, 0);
  const avgLatency = nodes.filter(n => n.latency > 0).reduce((sum, n, _, arr) => sum + n.latency / arr.length, 0);

  return (
    <div style={s.page}>
      <div style={s.header}>
        <div style={s.title}>LM Studio Cluster</div>
        <button
          style={s.btn}
          onClick={refresh}
          onMouseEnter={e => { e.currentTarget.style.borderColor = '#c084fc'; e.currentTarget.style.color = '#c084fc'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = '#1a2a3a'; e.currentTarget.style.color = '#4a6a8a'; }}
        >
          {refreshing ? 'Actualisation...' : 'Actualiser'}
        </button>
      </div>

      <div style={s.statsRow}>
        <div style={s.stat}>
          <span style={s.statLabel}>Nodes</span>
          <span style={{ ...s.statVal, color: onlineCount === nodes.length ? '#00ff88' : '#ffaa00' }}>{onlineCount}/{nodes.length}</span>
        </div>
        <div style={s.stat}>
          <span style={s.statLabel}>Modeles charges</span>
          <span style={{ ...s.statVal, color: '#c084fc' }}>{totalLoaded}</span>
        </div>
        <div style={s.stat}>
          <span style={s.statLabel}>Latence moy.</span>
          <span style={{ ...s.statVal, color: avgLatency < 500 ? '#00ff88' : '#ffaa00' }}>{avgLatency > 0 ? `${Math.round(avgLatency)}ms` : '---'}</span>
        </div>
      </div>

      <div style={s.grid}>
        {nodes.map(node => (
          <NodePanel key={node.id} node={node} onTest={testModel} />
        ))}
      </div>
    </div>
  );
}
