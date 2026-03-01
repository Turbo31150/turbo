import React, { useState, useEffect, memo, useMemo, useCallback } from 'react';
import { useLMStudio, LMNode, LMModel } from '../hooks/useLMStudio';

// ═══════════════════════════════════════════════════════════════
// Ollama models hook
// ═══════════════════════════════════════════════════════════════

interface OllamaModel {
  name: string;
  size: number;
  digest: string;
  modified_at: string;
  isCloud: boolean;
}

function useOllama() {
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [online, setOnline] = useState(false);
  const [latency, setLatency] = useState(-1);

  const refresh = useCallback(async () => {
    try {
      const t0 = performance.now();
      const r = await fetch('http://127.0.0.1:11434/api/tags', { signal: AbortSignal.timeout(5000) });
      setLatency(Math.round(performance.now() - t0));
      if (!r.ok) { setOnline(false); return; }
      const data = await r.json();
      const list = (data.models || []).map((m: any) => ({
        name: m.name || m.model || '',
        size: m.size || 0,
        digest: (m.digest || '').slice(0, 12),
        modified_at: m.modified_at || '',
        isCloud: (m.name || '').includes(':cloud') || (m.name || '').includes('cloud'),
      }));
      setModels(list);
      setOnline(true);
    } catch {
      setOnline(false);
      setModels([]);
      setLatency(-1);
    }
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 60000);
    return () => clearInterval(iv);
  }, [refresh]);

  return { models, online, latency, refresh };
}

// ═══════════════════════════════════════════════════════════════
// CSS
// ═══════════════════════════════════════════════════════════════

const CSS = `
@keyframes lmFadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.lm-card{animation:lmFadeIn .3s ease;transition:border-color .3s}
.lm-card:hover{border-color:rgba(249,115,22,.3)!important}
.lm-test:hover{opacity:.85}
.lm-tab:hover{color:#e0e0e0!important}
`;

const S = {
  page: { padding: 20, fontFamily: 'Consolas, "Courier New", monospace', height: '100%', overflowY: 'auto' } as React.CSSProperties,
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 } as React.CSSProperties,
  title: { fontSize: 18, fontWeight: 700, color: '#e0e0e0' } as React.CSSProperties,
  btn: { padding: '6px 14px', borderRadius: 6, border: '1px solid #2a3a4a', backgroundColor: 'transparent', color: '#6b7280', fontSize: 11, cursor: 'pointer', fontFamily: 'inherit', transition: 'all .2s' } as React.CSSProperties,
  tabs: { display: 'flex', gap: 2, marginBottom: 16, borderBottom: '1px solid #1a2a3a', paddingBottom: 0 } as React.CSSProperties,
  tab: { padding: '8px 16px', fontSize: 12, fontWeight: 600, color: '#6b7280', cursor: 'pointer', background: 'none', border: 'none', borderBottom: '2px solid transparent', fontFamily: 'inherit', transition: 'all .2s' } as React.CSSProperties,
  tabActive: { color: '#f97316', borderBottomColor: '#f97316' },
  stats: { display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' } as React.CSSProperties,
  stat: { backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 8, padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: 4, minWidth: 140 } as React.CSSProperties,
  statLabel: { fontSize: 10, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1.5 } as React.CSSProperties,
  statVal: { fontSize: 24, fontWeight: 700 } as React.CSSProperties,
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 16 } as React.CSSProperties,
  card: { backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 10, padding: 16 } as React.CSSProperties,
  cardHead: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 } as React.CSSProperties,
  nodeName: { fontSize: 16, fontWeight: 700, color: '#f97316' } as React.CSSProperties,
  badge: { fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 6, textTransform: 'uppercase', letterSpacing: 1 } as React.CSSProperties,
  online: { backgroundColor: 'rgba(16,185,129,.12)', color: '#10b981', border: '1px solid rgba(16,185,129,.25)' },
  offline: { backgroundColor: 'rgba(239,68,68,.12)', color: '#ef4444', border: '1px solid rgba(239,68,68,.25)' },
  loading: { backgroundColor: 'rgba(249,115,22,.12)', color: '#f97316', border: '1px solid rgba(249,115,22,.25)' },
  nodeDesc: { fontSize: 10, color: '#6b7280', marginBottom: 10 } as React.CSSProperties,
  secLabel: { fontSize: 10, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 } as React.CSSProperties,
  modelRow: { display: 'flex', alignItems: 'center', gap: 8, padding: '7px 0', borderBottom: '1px solid #0a0e14' } as React.CSSProperties,
  dot: { width: 8, height: 8, borderRadius: '50%', flexShrink: 0 } as React.CSSProperties,
  dotOn: { backgroundColor: '#10b981', boxShadow: '0 0 6px rgba(16,185,129,.5)' },
  dotOff: { backgroundColor: '#4b5563' },
  modelName: { flex: 1, fontSize: 12, color: '#e0e0e0', fontWeight: 500 } as React.CSSProperties,
  modelMeta: { fontSize: 10, color: '#6b7280' } as React.CSSProperties,
  loadedTag: { fontSize: 9, color: '#10b981', fontWeight: 700, letterSpacing: 1 } as React.CSSProperties,
  cloudTag: { fontSize: 9, color: '#c084fc', fontWeight: 700, letterSpacing: 1 } as React.CSSProperties,
  localTag: { fontSize: 9, color: '#f97316', fontWeight: 700, letterSpacing: 1 } as React.CSSProperties,
  latBadge: (ms: number) => ({ fontSize: 10, color: ms < 500 ? '#10b981' : ms < 2000 ? '#f97316' : '#ef4444' }),
  errText: { fontSize: 11, color: '#ef4444', padding: 8 } as React.CSSProperties,
  testArea: { marginTop: 12, backgroundColor: '#0a0e14', borderRadius: 8, padding: 12, border: '1px solid #1a2a3a' } as React.CSSProperties,
  testInput: { width: '100%', padding: '8px 10px', backgroundColor: '#0d1117', border: '1px solid #2a3a4a', borderRadius: 6, color: '#e0e0e0', fontSize: 12, fontFamily: 'inherit', outline: 'none', marginBottom: 8, boxSizing: 'border-box' } as React.CSSProperties,
  testBtn: { padding: '6px 14px', borderRadius: 6, border: '1px solid #f97316', backgroundColor: 'rgba(249,115,22,.08)', color: '#f97316', fontSize: 11, cursor: 'pointer', fontFamily: 'inherit', fontWeight: 600 } as React.CSSProperties,
  testResult: { marginTop: 8, fontSize: 11, color: '#e0e0e0', whiteSpace: 'pre-wrap', maxHeight: 200, overflowY: 'auto', lineHeight: 1.5 } as React.CSSProperties,
  testLat: { fontSize: 10, color: '#10b981', marginTop: 4 } as React.CSSProperties,
};

// ═══════════════════════════════════════════════════════════════
// Composants
// ═══════════════════════════════════════════════════════════════

const ModelItem = memo(function ModelItem({ model }: { model: LMModel }) {
  return (
    <div style={S.modelRow}>
      <div style={{ ...S.dot, ...(model.loaded ? S.dotOn : S.dotOff) }} />
      <span style={S.modelName}>{model.id}</span>
      {model.size_gb && <span style={S.modelMeta}>{model.size_gb} GB</span>}
      {model.context_length && <span style={S.modelMeta}>ctx:{model.context_length}</span>}
      {model.gpu_offload && <span style={S.modelMeta}>GPU:{model.gpu_offload}</span>}
      {model.loaded && <span style={S.loadedTag}>LOADED</span>}
    </div>
  );
});

const OllamaModelItem = memo(function OllamaModelItem({ model }: { model: OllamaModel }) {
  const sizeGB = model.size > 0 ? (model.size / 1e9).toFixed(1) : null;
  return (
    <div style={S.modelRow}>
      <div style={{ ...S.dot, ...S.dotOn }} />
      <span style={S.modelName}>{model.name}</span>
      {sizeGB && <span style={S.modelMeta}>{sizeGB} GB</span>}
      <span style={S.modelMeta}>{model.digest}</span>
      {model.isCloud ? <span style={S.cloudTag}>CLOUD</span> : <span style={S.localTag}>LOCAL</span>}
    </div>
  );
});

const NodePanel = memo(function NodePanel({ node, onTest }: { node: LMNode; onTest: (nodeId: string, model: string, prompt: string) => Promise<{ text: string; latency: number }> }) {
  const [prompt, setPrompt] = useState('Reponds OK en 1 mot.');
  const [result, setResult] = useState<{ text: string; latency: number } | null>(null);
  const [testing, setTesting] = useState(false);
  const [showTest, setShowTest] = useState(false);

  const loadedModels = node.models.filter(m => m.loaded);
  const firstLoaded = loadedModels[0]?.id || '';

  const handleTest = async () => {
    if (!firstLoaded || testing) return;
    setTesting(true); setResult(null);
    try { setResult(await onTest(node.id, firstLoaded, prompt)); }
    catch (e: any) { setResult({ text: `Erreur: ${e.message}`, latency: -1 }); }
    setTesting(false);
  };

  const badgeStyle = node.status === 'online' ? S.online : node.status === 'offline' ? S.offline : S.loading;

  return (
    <div className="lm-card" style={S.card}>
      <div style={S.cardHead}>
        <span style={S.nodeName}>{node.id}</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {node.latency > 0 && <span style={S.latBadge(node.latency)}>{node.latency}ms</span>}
          <span style={{ ...S.badge, ...badgeStyle }}>{node.status}</span>
        </div>
      </div>
      <div style={S.nodeDesc}>{node.name}</div>
      {node.error && <div style={S.errText}>{node.error}</div>}

      {node.models.length > 0 ? (
        <>
          <div style={S.secLabel}>Modeles ({loadedModels.length} charges / {node.models.length} total)</div>
          {node.models.map(m => <ModelItem key={m.id} model={m} />)}
        </>
      ) : node.status === 'online' ? (
        <div style={{ fontSize: 11, color: '#6b7280', padding: 8 }}>Aucun modele</div>
      ) : null}

      {node.status === 'online' && firstLoaded && (
        <>
          <button className="lm-test" style={{ ...S.testBtn, marginTop: 12 }} onClick={() => setShowTest(!showTest)}>
            {showTest ? 'Masquer test' : 'Tester inference'}
          </button>
          {showTest && (
            <div style={S.testArea}>
              <input style={S.testInput} value={prompt} onChange={e => setPrompt(e.target.value)}
                placeholder="Prompt de test..." onKeyDown={e => e.key === 'Enter' && handleTest()} />
              <button style={S.testBtn} onClick={handleTest} disabled={testing}>
                {testing ? 'En cours...' : `Envoyer a ${node.id}`}
              </button>
              {result && (
                <>
                  <div style={S.testResult}>{result.text}</div>
                  {result.latency > 0 && <div style={S.testLat}>{result.latency}ms</div>}
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
});

// ═══════════════════════════════════════════════════════════════
// Main Page
// ═══════════════════════════════════════════════════════════════

export default function LMStudioPage() {
  const { nodes, refreshing, refresh, testModel } = useLMStudio();
  const ollama = useOllama();
  const [tab, setTab] = useState<'all' | 'lmstudio' | 'ollama'>('all');

  const onlineCount = useMemo(() => nodes.filter(n => n.status === 'online').length, [nodes]);
  const totalLoaded = useMemo(() => nodes.reduce((sum, n) => sum + n.models.filter(m => m.loaded).length, 0), [nodes]);
  const avgLatency = useMemo(() => nodes.filter(n => n.latency > 0).reduce((sum, n, _, arr) => sum + n.latency / arr.length, 0), [nodes]);

  const ollamaLocal = useMemo(() => ollama.models.filter(m => !m.isCloud), [ollama.models]);
  const ollamaCloud = useMemo(() => ollama.models.filter(m => m.isCloud), [ollama.models]);

  const handleRefresh = useCallback(() => {
    refresh();
    ollama.refresh();
  }, [refresh, ollama.refresh]);

  return (
    <>
      <style>{CSS}</style>
      <div style={S.page}>
        <div style={S.header}>
          <div style={S.title}>AI Cluster</div>
          <button style={S.btn} onClick={handleRefresh}
            onMouseEnter={e => { e.currentTarget.style.borderColor = '#f97316'; e.currentTarget.style.color = '#f97316'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = '#2a3a4a'; e.currentTarget.style.color = '#6b7280'; }}>
            {refreshing ? 'Actualisation...' : 'Actualiser'}
          </button>
        </div>

        <div style={S.stats}>
          <div style={S.stat}>
            <span style={S.statLabel}>LM Studio</span>
            <span style={{ ...S.statVal, color: onlineCount === nodes.length ? '#10b981' : '#f97316' }}>{onlineCount}/{nodes.length}</span>
          </div>
          <div style={S.stat}>
            <span style={S.statLabel}>Ollama</span>
            <span style={{ ...S.statVal, color: ollama.online ? '#10b981' : '#ef4444' }}>{ollama.online ? 'ON' : 'OFF'}</span>
          </div>
          <div style={S.stat}>
            <span style={S.statLabel}>Modeles total</span>
            <span style={{ ...S.statVal, color: '#c084fc' }}>{totalLoaded + ollama.models.length}</span>
          </div>
          <div style={S.stat}>
            <span style={S.statLabel}>Cloud</span>
            <span style={{ ...S.statVal, color: '#c084fc' }}>{ollamaCloud.length}</span>
          </div>
          <div style={S.stat}>
            <span style={S.statLabel}>Latence moy.</span>
            <span style={{ ...S.statVal, color: avgLatency < 500 ? '#10b981' : '#f97316' }}>{avgLatency > 0 ? `${Math.round(avgLatency)}ms` : '---'}</span>
          </div>
        </div>

        {/* Tabs */}
        <div style={S.tabs}>
          {(['all', 'lmstudio', 'ollama'] as const).map(t => (
            <button key={t} className="lm-tab"
              style={{ ...S.tab, ...(tab === t ? S.tabActive : {}) }}
              onClick={() => setTab(t)}>
              {t === 'all' ? 'Tous' : t === 'lmstudio' ? 'LM Studio (M1/M2/M3)' : `Ollama (${ollama.models.length})`}
            </button>
          ))}
        </div>

        {/* LM Studio nodes */}
        {(tab === 'all' || tab === 'lmstudio') && (
          <>
            {tab === 'all' && <div style={{ ...S.secLabel, marginBottom: 12, marginTop: 4 }}>LM STUDIO</div>}
            <div style={S.grid}>
              {nodes.map(node => <NodePanel key={node.id} node={node} onTest={testModel} />)}
            </div>
          </>
        )}

        {/* Ollama section */}
        {(tab === 'all' || tab === 'ollama') && (
          <>
            <div style={{ ...S.secLabel, marginBottom: 12, marginTop: tab === 'all' ? 24 : 4 }}>
              OLLAMA {ollama.online ? '' : '(OFFLINE)'}
              {ollama.latency > 0 && <span style={{ ...S.modelMeta, marginLeft: 8 }}>{ollama.latency}ms</span>}
            </div>

            {ollama.online ? (
              <div style={S.grid}>
                {/* Local models card */}
                <div className="lm-card" style={S.card}>
                  <div style={S.cardHead}>
                    <span style={S.nodeName}>OL1 Local</span>
                    <span style={{ ...S.badge, ...S.online }}>online</span>
                  </div>
                  <div style={S.nodeDesc}>127.0.0.1:11434 — Modeles locaux</div>
                  <div style={S.secLabel}>{ollamaLocal.length} modeles</div>
                  {ollamaLocal.map(m => <OllamaModelItem key={m.name} model={m} />)}
                  {ollamaLocal.length === 0 && <div style={{ fontSize: 11, color: '#6b7280', padding: 8 }}>Aucun modele local</div>}
                </div>

                {/* Cloud models card */}
                <div className="lm-card" style={S.card}>
                  <div style={S.cardHead}>
                    <span style={{ ...S.nodeName, color: '#c084fc' }}>OL1 Cloud</span>
                    <span style={{ ...S.badge, ...S.online }}>online</span>
                  </div>
                  <div style={S.nodeDesc}>Ollama Cloud — Modeles distants</div>
                  <div style={S.secLabel}>{ollamaCloud.length} modeles cloud</div>
                  {ollamaCloud.map(m => <OllamaModelItem key={m.name} model={m} />)}
                  {ollamaCloud.length === 0 && <div style={{ fontSize: 11, color: '#6b7280', padding: 8 }}>Aucun modele cloud</div>}
                </div>
              </div>
            ) : (
              <div className="lm-card" style={S.card}>
                <div style={S.errText}>Ollama hors ligne — verifiez que le service tourne sur 127.0.0.1:11434</div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
