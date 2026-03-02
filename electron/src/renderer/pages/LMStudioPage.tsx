import React, { useState, useEffect, useRef, memo, useMemo, useCallback } from 'react';
import { useLMStudio, LMNode, LMModel } from '../hooks/useLMStudio';
import { OLLAMA_URL, INTERVALS } from '../lib/config';
import { COLORS, FONT, latencyColor } from '../lib/theme';

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
      const r = await fetch(`${OLLAMA_URL}/api/tags`, { signal: AbortSignal.timeout(5000) });
      setLatency(Math.round(performance.now() - t0));
      if (!r.ok) { setOnline(false); return; }
      const data = await r.json();
      const list = (data.models || []).map((m: { name?: string; model?: string; size?: number; digest?: string; modified_at?: string }) => ({
        name: m.name || m.model || '',
        size: m.size || 0,
        digest: (m.digest || '').slice(0, 12),
        modified_at: m.modified_at || '',
        isCloud: (m.name || '').includes(':cloud') || (m.name || '').includes('cloud'),
      }));
      setModels(list);
      setOnline(true);
    } catch (err) {
      console.warn('[LMStudio] Ollama fetch error:', err instanceof Error ? err.message : err);
      setOnline(false);
      setModels([]);
      setLatency(-1);
    }
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, INTERVALS.lmStudio);
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
.lm-card:hover{border-color:${COLORS.orangeAlpha(0.3)}!important}
.lm-test:hover{opacity:.85}
.lm-tab:hover{color:${COLORS.text}!important}
`;

const S = {
  page: { padding: 20, fontFamily: FONT, height: '100%', overflowY: 'auto' } as React.CSSProperties,
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 } as React.CSSProperties,
  title: { fontSize: 18, fontWeight: 700, color: COLORS.text } as React.CSSProperties,
  btn: { padding: '6px 14px', borderRadius: 6, border: `1px solid ${COLORS.border}`, backgroundColor: 'transparent', color: COLORS.textDim, fontSize: 11, cursor: 'pointer', fontFamily: 'inherit', transition: 'all .2s' } as React.CSSProperties,
  tabs: { display: 'flex', gap: 2, marginBottom: 16, borderBottom: `1px solid ${COLORS.border}`, paddingBottom: 0 } as React.CSSProperties,
  tab: { padding: '8px 16px', fontSize: 12, fontWeight: 600, color: COLORS.textDim, cursor: 'pointer', background: 'none', border: 'none', borderBottom: '2px solid transparent', fontFamily: 'inherit', transition: 'all .2s' } as React.CSSProperties,
  tabActive: { color: COLORS.orange, borderBottomColor: COLORS.orange },
  stats: { display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' } as React.CSSProperties,
  stat: { backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 8, padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: 4, minWidth: 140 } as React.CSSProperties,
  statLabel: { fontSize: 10, color: COLORS.textDim, textTransform: 'uppercase', letterSpacing: 1.5 } as React.CSSProperties,
  statVal: { fontSize: 24, fontWeight: 700 } as React.CSSProperties,
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 16 } as React.CSSProperties,
  card: { backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 10, padding: 16 } as React.CSSProperties,
  cardHead: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 } as React.CSSProperties,
  nodeName: { fontSize: 16, fontWeight: 700, color: COLORS.orange } as React.CSSProperties,
  badge: { fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 6, textTransform: 'uppercase', letterSpacing: 1 } as React.CSSProperties,
  online: { backgroundColor: COLORS.greenAlpha(0.12), color: COLORS.green, border: `1px solid ${COLORS.greenAlpha(0.25)}` },
  offline: { backgroundColor: COLORS.redAlpha(0.12), color: COLORS.red, border: `1px solid ${COLORS.redAlpha(0.25)}` },
  loading: { backgroundColor: COLORS.orangeAlpha(0.12), color: COLORS.orange, border: `1px solid ${COLORS.orangeAlpha(0.25)}` },
  nodeDesc: { fontSize: 10, color: COLORS.textDim, marginBottom: 10 } as React.CSSProperties,
  secLabel: { fontSize: 10, color: COLORS.textDim, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 } as React.CSSProperties,
  modelRow: { display: 'flex', alignItems: 'center', gap: 8, padding: '7px 0', borderBottom: `1px solid ${COLORS.bg}` } as React.CSSProperties,
  dot: { width: 8, height: 8, borderRadius: '50%', flexShrink: 0 } as React.CSSProperties,
  dotOn: { backgroundColor: COLORS.green, boxShadow: `0 0 6px ${COLORS.greenAlpha(0.5)}` },
  dotOff: { backgroundColor: COLORS.textDimmer },
  modelName: { flex: 1, fontSize: 12, color: COLORS.text, fontWeight: 500 } as React.CSSProperties,
  modelMeta: { fontSize: 10, color: COLORS.textDim } as React.CSSProperties,
  loadedTag: { fontSize: 9, color: COLORS.green, fontWeight: 700, letterSpacing: 1 } as React.CSSProperties,
  cloudTag: { fontSize: 9, color: COLORS.purple, fontWeight: 700, letterSpacing: 1 } as React.CSSProperties,
  localTag: { fontSize: 9, color: COLORS.orange, fontWeight: 700, letterSpacing: 1 } as React.CSSProperties,
  latBadge: (ms: number) => ({ fontSize: 10, color: latencyColor(ms) }),
  errText: { fontSize: 11, color: COLORS.red, padding: 8 } as React.CSSProperties,
  testArea: { marginTop: 12, backgroundColor: COLORS.bg, borderRadius: 8, padding: 12, border: `1px solid ${COLORS.border}` } as React.CSSProperties,
  testInput: { width: '100%', padding: '8px 10px', backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, color: COLORS.text, fontSize: 12, fontFamily: 'inherit', outline: 'none', marginBottom: 8, boxSizing: 'border-box' } as React.CSSProperties,
  testBtn: { padding: '6px 14px', borderRadius: 6, border: `1px solid ${COLORS.orange}`, backgroundColor: COLORS.orangeAlpha(0.08), color: COLORS.orange, fontSize: 11, cursor: 'pointer', fontFamily: 'inherit', fontWeight: 600 } as React.CSSProperties,
  testResult: { marginTop: 8, fontSize: 11, color: COLORS.text, whiteSpace: 'pre-wrap', maxHeight: 200, overflowY: 'auto', lineHeight: 1.5 } as React.CSSProperties,
  testLat: { fontSize: 10, color: COLORS.green, marginTop: 4 } as React.CSSProperties,
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
  const mountedRef = useRef(true);

  useEffect(() => () => { mountedRef.current = false; }, []);

  const loadedModels = node.models.filter(m => m.loaded);
  const firstLoaded = loadedModels[0]?.id || '';

  const handleTest = async () => {
    if (!firstLoaded || testing) return;
    setTesting(true); setResult(null);
    try {
      const res = await onTest(node.id, firstLoaded, prompt);
      if (mountedRef.current) setResult(res);
    } catch (e) {
      if (mountedRef.current) setResult({ text: `Erreur: ${e instanceof Error ? e.message : e}`, latency: -1 });
    }
    if (mountedRef.current) setTesting(false);
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
        <div style={{ fontSize: 11, color: COLORS.textDim, padding: 8 }}>Aucun modele</div>
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
            onMouseEnter={e => { e.currentTarget.style.borderColor = COLORS.orange; e.currentTarget.style.color = COLORS.orange; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = COLORS.border; e.currentTarget.style.color = COLORS.textDim; }}>
            {refreshing ? 'Actualisation...' : 'Actualiser'}
          </button>
        </div>

        <div style={S.stats}>
          <div style={S.stat}>
            <span style={S.statLabel}>LM Studio</span>
            <span style={{ ...S.statVal, color: onlineCount === nodes.length ? COLORS.green : COLORS.orange }}>{onlineCount}/{nodes.length}</span>
          </div>
          <div style={S.stat}>
            <span style={S.statLabel}>Ollama</span>
            <span style={{ ...S.statVal, color: ollama.online ? COLORS.green : COLORS.red }}>{ollama.online ? 'ON' : 'OFF'}</span>
          </div>
          <div style={S.stat}>
            <span style={S.statLabel}>Modeles total</span>
            <span style={{ ...S.statVal, color: COLORS.purple }}>{totalLoaded + ollama.models.length}</span>
          </div>
          <div style={S.stat}>
            <span style={S.statLabel}>Cloud</span>
            <span style={{ ...S.statVal, color: COLORS.purple }}>{ollamaCloud.length}</span>
          </div>
          <div style={S.stat}>
            <span style={S.statLabel}>Latence moy.</span>
            <span style={{ ...S.statVal, color: latencyColor(avgLatency) }}>{avgLatency > 0 ? `${Math.round(avgLatency)}ms` : '---'}</span>
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
                <div className="lm-card" style={S.card}>
                  <div style={S.cardHead}>
                    <span style={S.nodeName}>OL1 Local</span>
                    <span style={{ ...S.badge, ...S.online }}>online</span>
                  </div>
                  <div style={S.nodeDesc}>{OLLAMA_URL.replace('http://', '')} — Modeles locaux</div>
                  <div style={S.secLabel}>{ollamaLocal.length} modeles</div>
                  {ollamaLocal.map(m => <OllamaModelItem key={m.name} model={m} />)}
                  {ollamaLocal.length === 0 && <div style={{ fontSize: 11, color: COLORS.textDim, padding: 8 }}>Aucun modele local</div>}
                </div>

                <div className="lm-card" style={S.card}>
                  <div style={S.cardHead}>
                    <span style={{ ...S.nodeName, color: COLORS.purple }}>OL1 Cloud</span>
                    <span style={{ ...S.badge, ...S.online }}>online</span>
                  </div>
                  <div style={S.nodeDesc}>Ollama Cloud — Modeles distants</div>
                  <div style={S.secLabel}>{ollamaCloud.length} modeles cloud</div>
                  {ollamaCloud.map(m => <OllamaModelItem key={m.name} model={m} />)}
                  {ollamaCloud.length === 0 && <div style={{ fontSize: 11, color: COLORS.textDim, padding: 8 }}>Aucun modele cloud</div>}
                </div>
              </div>
            ) : (
              <div className="lm-card" style={S.card}>
                <div style={S.errText}>Ollama hors ligne — verifiez que le service tourne sur {OLLAMA_URL.replace('http://', '')}</div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
