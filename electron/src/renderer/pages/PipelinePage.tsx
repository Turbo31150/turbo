import React, { useState, useEffect, useCallback, useMemo, useRef, memo } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { BACKEND_URL } from '../lib/config';
import { COLORS, FONT } from '../lib/theme';

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

interface Domino {
  id: string;
  name: string;
  category: string;
  description?: string;
  steps_count?: number;
  source: 'hardcoded' | 'db';
  trigger_cmd?: string;
}

interface ExecResult {
  domino_id: string;
  passed: number;
  failed: number;
  skipped: number;
  total_ms: number;
  run_id: string;
}

interface LogEntry {
  step_name: string;
  step_idx: number;
  status: string;
  duration_ms: number;
  node?: string;
  output_preview?: string;
}

interface DevOpsPipeline {
  id: string;
  name: string;
  prompt: string;
  status: string;
  total: number;
  completed: number;
  created: string;
  updated: string;
}

interface PipelineSection {
  idx: number;
  type: string;
  prompt: string;
  response: string;
  provider: string;
  status: string;
  latency_ms: number;
  cached: boolean;
}

interface PipelineDetail extends DevOpsPipeline {
  result: string;
  sections: PipelineSection[];
}

interface CacheStats {
  total_entries: number;
  total_hits: number;
  top_categories: Record<string, number>;
  recent: { prompt: string; provider: string; category: string; hits: number; created: string }[];
}

interface EngineStatus {
  pipelines: { total: number; completed: number; running: number; failed: number };
  sections: { completed: number; total: number };
  cache: { entries: number };
  templates: { count: number };
}

type Tab = 'dominos' | 'devops' | 'cache';

// ═══════════════════════════════════════════════════════════════
// CSS
// ═══════════════════════════════════════════════════════════════

const CSS = `
@keyframes pipeFade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.pipe-card{animation:pipeFade .2s ease;transition:border-color .3s}
.pipe-card:hover{border-color:${COLORS.orangeAlpha(0.3)}!important}
.pipe-input:focus{border-color:${COLORS.orange}!important}
.pipe-page::-webkit-scrollbar{width:5px}
.pipe-page::-webkit-scrollbar-thumb{background:${COLORS.border};border-radius:3px}
@keyframes pipeExec{0%{opacity:1}50%{opacity:.5}100%{opacity:1}}
@keyframes pulseDot{0%,100%{opacity:1}50%{opacity:.4}}
.status-running{animation:pulseDot 1.5s ease infinite}
.pipe-tab{transition:all .15s;cursor:pointer;user-select:none}
.pipe-tab:hover{color:${COLORS.text}!important}
.section-row{transition:background .15s}
.section-row:hover{background:${COLORS.orangeAlpha(0.04)}!important}
`;

// ═══════════════════════════════════════════════════════════════
// Shared styles
// ═══════════════════════════════════════════════════════════════

const S = {
  page: { padding: 20, fontFamily: FONT, height: '100%', overflowY: 'auto' } as React.CSSProperties,
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 } as React.CSSProperties,
  title: { fontSize: 18, fontWeight: 700, color: COLORS.text } as React.CSSProperties,
  stats: { display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' } as React.CSSProperties,
  stat: { backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 8, padding: '12px 18px', display: 'flex', flexDirection: 'column', gap: 4, minWidth: 120 } as React.CSSProperties,
  statLabel: { fontSize: 10, color: COLORS.textDim, textTransform: 'uppercase', letterSpacing: 1.5 } as React.CSSProperties,
  statVal: { fontSize: 22, fontWeight: 700 } as React.CSSProperties,
  toolbar: { display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' } as React.CSSProperties,
  search: { flex: 1, padding: '8px 12px', backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, color: COLORS.text, fontSize: 12, fontFamily: 'inherit', outline: 'none' } as React.CSSProperties,
  filterBtn: { padding: '6px 12px', borderRadius: 6, border: `1px solid ${COLORS.border}`, backgroundColor: 'transparent', color: COLORS.textDim, fontSize: 10, cursor: 'pointer', fontFamily: 'inherit', transition: 'all .2s', textTransform: 'uppercase', letterSpacing: .5 } as React.CSSProperties,
  filterActive: { borderColor: COLORS.purple, color: COLORS.purple, backgroundColor: COLORS.purpleAlpha(0.08) },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 14 } as React.CSSProperties,
  card: { backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 10, padding: 16 } as React.CSSProperties,
  cardHead: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 } as React.CSSProperties,
  cardName: { fontSize: 13, fontWeight: 700, color: COLORS.text } as React.CSSProperties,
  badge: { fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 4, letterSpacing: .5 } as React.CSSProperties,
  catBadge: { backgroundColor: COLORS.purpleAlpha(0.1), color: COLORS.purple, border: `1px solid ${COLORS.purpleAlpha(0.2)}` },
  srcBadge: (src: string) => ({
    backgroundColor: src === 'hardcoded' ? COLORS.orangeAlpha(0.1) : COLORS.greenAlpha(0.1),
    color: src === 'hardcoded' ? COLORS.orange : COLORS.green,
    border: `1px solid ${src === 'hardcoded' ? COLORS.orangeAlpha(0.2) : COLORS.greenAlpha(0.2)}`,
  }),
  cardDesc: { fontSize: 11, color: COLORS.textDim, marginBottom: 10, lineHeight: 1.4 } as React.CSSProperties,
  execBtn: { padding: '6px 14px', borderRadius: 6, border: `1px solid ${COLORS.orange}`, backgroundColor: COLORS.orangeAlpha(0.08), color: COLORS.orange, fontSize: 11, cursor: 'pointer', fontFamily: 'inherit', fontWeight: 600, width: '100%' } as React.CSSProperties,
  execRunning: { animation: 'pipeExec 1.5s ease infinite', borderColor: COLORS.purple, color: COLORS.purple },
  resultBox: { marginTop: 10, padding: 10, backgroundColor: COLORS.bg, borderRadius: 6, border: `1px solid ${COLORS.border}` } as React.CSSProperties,
  resultRow: { display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, padding: '3px 0' } as React.CSSProperties,
  stepDot: (status: string) => ({
    width: 6, height: 6, borderRadius: '50%',
    backgroundColor: status === 'passed' || status === 'ok' || status === 'completed' || status === 'cached'
      ? COLORS.green : status === 'failed' ? COLORS.red : COLORS.textDim,
  }),
  emptyState: { textAlign: 'center', padding: 40, color: COLORS.textDim, fontSize: 13 } as React.CSSProperties,
  logsPanel: { marginTop: 8, fontSize: 10, color: COLORS.textDim } as React.CSSProperties,
};

const btnStyle = { padding: '6px 14px', borderRadius: 6, border: `1px solid ${COLORS.border}`, backgroundColor: 'transparent', color: COLORS.textDim, fontSize: 11, cursor: 'pointer', fontFamily: 'inherit' } as React.CSSProperties;

const statusColor = (s: string) =>
  s === 'completed' || s === 'cached' ? COLORS.green
  : s === 'running' ? COLORS.orange
  : s === 'failed' ? COLORS.red
  : COLORS.textDim;

// ═══════════════════════════════════════════════════════════════
// Domino Card (existing)
// ═══════════════════════════════════════════════════════════════

const DominoCard = memo(function DominoCard({ domino, onExecute, onDone, executing }: { domino: Domino; onExecute: (d: Domino) => void; onDone: () => void; executing: string | null }) {
  const [result, setResult] = useState<ExecResult | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  const isRunning = executing === domino.id;
  const isBlocked = executing !== null && !isRunning;

  useEffect(() => () => { mountedRef.current = false; abortRef.current?.abort(); }, []);

  const handleExec = async () => {
    setResult(null);
    setLogs([]);
    setError(null);
    onExecute(domino);
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const timeoutId = setTimeout(() => controller.abort(), 120000);
    try {
      const r = await fetch(BACKEND_URL + '/api/dominos/execute', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(domino.source === 'db' ? { trigger: domino.trigger_cmd || domino.name } : { domino_id: domino.id }),
        signal: controller.signal,
      });
      if (!mountedRef.current) return;
      if (r.ok) {
        const data = await r.json();
        const d = data.domino || data;
        setResult({ domino_id: d.domino_id || domino.id, passed: d.passed || 0, failed: d.failed || 0, skipped: d.skipped || 0, total_ms: d.total_ms || 0, run_id: d.run_id || '' });
        if (d.run_id) {
          const lr = await fetch(BACKEND_URL + `/api/dominos/logs?run_id=${d.run_id}`, { signal: controller.signal });
          if (mountedRef.current && lr.ok) { setLogs((await lr.json()).logs || []); }
        }
      } else {
        setError(`Erreur ${r.status}: ${r.statusText}`);
      }
    } catch (e) {
      if (!mountedRef.current) return;
      if (e instanceof DOMException && e.name === 'AbortError') { setError('Annule'); }
      else { setError(e instanceof Error ? (e.name === 'TimeoutError' ? 'Timeout (120s)' : e.message) : 'Erreur inconnue'); }
    } finally {
      clearTimeout(timeoutId);
      if (mountedRef.current) onDone();
    }
  };

  return (
    <div className="pipe-card" style={S.card}>
      <div style={S.cardHead}>
        <span style={S.cardName}>{domino.name || domino.id}</span>
        <div style={{ display: 'flex', gap: 6 }}>
          <span style={{ ...S.badge, ...S.catBadge }}>{domino.category}</span>
          <span style={{ ...S.badge, ...S.srcBadge(domino.source) }}>{domino.source}</span>
        </div>
      </div>
      {domino.description && <div style={S.cardDesc}>{domino.description}</div>}
      {domino.steps_count && <div style={{ fontSize: 10, color: COLORS.textDim, marginBottom: 8 }}>{domino.steps_count} etapes</div>}

      <button style={{ ...S.execBtn, ...(isRunning ? S.execRunning : {}), ...(isBlocked ? { opacity: 0.4, cursor: 'not-allowed' } : {}) }} onClick={handleExec} disabled={isRunning || isBlocked}>
        {isRunning ? 'Execution...' : isBlocked ? 'En attente...' : 'Executer'}
      </button>

      {error && (
        <div style={{ marginTop: 8, padding: '6px 10px', borderRadius: 6, fontSize: 11, color: COLORS.red, backgroundColor: COLORS.redAlpha(0.08), border: `1px solid ${COLORS.redAlpha(0.2)}` }}>
          {error}
        </div>
      )}

      {result && (
        <div style={S.resultBox}>
          <div style={{ display: 'flex', gap: 12, fontSize: 11, marginBottom: logs.length ? 8 : 0 }}>
            <span style={{ color: COLORS.green }}>{result.passed} OK</span>
            {result.failed > 0 && <span style={{ color: COLORS.red }}>{result.failed} FAIL</span>}
            {result.skipped > 0 && <span style={{ color: COLORS.textDim }}>{result.skipped} skip</span>}
            <span style={{ color: COLORS.textDim }}>{result.total_ms}ms</span>
          </div>
          {logs.length > 0 && (
            <div style={S.logsPanel}>
              {logs.map((log, i) => (
                <div key={`${log.step_name}_${i}`} style={S.resultRow}>
                  <div style={S.stepDot(log.status)} />
                  <span style={{ color: COLORS.text, fontWeight: 500 }}>{log.step_name}</span>
                  <span>{log.duration_ms}ms</span>
                  {log.node && <span style={{ color: COLORS.purple }}>{log.node}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
});

// ═══════════════════════════════════════════════════════════════
// DevOps Pipeline Card (NEW)
// ═══════════════════════════════════════════════════════════════

const DevOpsCard = memo(function DevOpsCard({ pipeline, onSelect, onResume, onDelete }: {
  pipeline: DevOpsPipeline;
  onSelect: (id: string) => void;
  onResume: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const pct = pipeline.total > 0 ? Math.round((pipeline.completed / pipeline.total) * 100) : 0;
  const isRunning = pipeline.status === 'running';

  return (
    <div className="pipe-card" style={{
      ...S.card,
      borderLeft: `3px solid ${statusColor(pipeline.status)}`,
      cursor: 'pointer',
    }} onClick={() => onSelect(pipeline.id)}>
      <div style={S.cardHead}>
        <span style={S.cardName}>{pipeline.name}</span>
        <span style={{
          ...S.badge,
          backgroundColor: `${statusColor(pipeline.status)}15`,
          color: statusColor(pipeline.status),
          border: `1px solid ${statusColor(pipeline.status)}40`,
        }} className={isRunning ? 'status-running' : ''}>
          {pipeline.status}
        </span>
      </div>

      {pipeline.prompt && (
        <div style={S.cardDesc}>{pipeline.prompt}</div>
      )}

      {/* Progress bar */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: COLORS.textDim, marginBottom: 4 }}>
          <span>{pipeline.completed}/{pipeline.total} sections</span>
          <span>{pct}%</span>
        </div>
        <div style={{ height: 4, backgroundColor: COLORS.border, borderRadius: 2, overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 2, transition: 'width .3s',
            width: `${pct}%`,
            backgroundColor: statusColor(pipeline.status),
          }} />
        </div>
      </div>

      {/* Timestamps */}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: COLORS.textDim }}>
        <span>{pipeline.created ? new Date(pipeline.created).toLocaleString('fr-FR') : ''}</span>
        <div style={{ display: 'flex', gap: 6 }}>
          {(pipeline.status === 'failed' || pipeline.status === 'pending') && (
            <button style={{ ...S.badge, backgroundColor: COLORS.orangeAlpha(0.1), color: COLORS.orange, border: `1px solid ${COLORS.orangeAlpha(0.3)}`, cursor: 'pointer' }}
              onClick={(e) => { e.stopPropagation(); onResume(pipeline.id); }}>
              RESUME
            </button>
          )}
          <button style={{ ...S.badge, backgroundColor: COLORS.redAlpha(0.05), color: COLORS.red, border: `1px solid ${COLORS.redAlpha(0.2)}`, cursor: 'pointer' }}
            onClick={(e) => { e.stopPropagation(); onDelete(pipeline.id); }}>
            DEL
          </button>
        </div>
      </div>
    </div>
  );
});

// ═══════════════════════════════════════════════════════════════
// Pipeline Detail Panel
// ═══════════════════════════════════════════════════════════════

function PipelineDetailPanel({ detail, onClose }: { detail: PipelineDetail; onClose: () => void }) {
  return (
    <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: 480, backgroundColor: COLORS.bgCard, borderLeft: `1px solid ${COLORS.border}`, zIndex: 100, display: 'flex', flexDirection: 'column', boxShadow: '-4px 0 20px rgba(0,0,0,.3)' }}>
      {/* Header */}
      <div style={{ padding: '16px 20px', borderBottom: `1px solid ${COLORS.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: COLORS.text }}>{detail.name}</div>
          <div style={{ fontSize: 10, color: COLORS.textDim, marginTop: 2 }}>
            {detail.completed}/{detail.total} sections &mdash;{' '}
            <span style={{ color: statusColor(detail.status) }}>{detail.status}</span>
          </div>
        </div>
        <button onClick={onClose} style={{ ...btnStyle, padding: '4px 10px', fontSize: 14 }}>&times;</button>
      </div>

      {/* Sections list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 20px' }}>
        {detail.sections.map((sec) => (
          <div key={sec.idx} className="section-row" style={{ padding: '10px 12px', marginBottom: 8, borderRadius: 8, border: `1px solid ${COLORS.border}`, backgroundColor: COLORS.bg }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <div style={S.stepDot(sec.status)} />
              <span style={{ fontSize: 11, fontWeight: 600, color: COLORS.text, textTransform: 'uppercase' }}>{sec.type}</span>
              <span style={{ fontSize: 9, color: COLORS.purple, marginLeft: 'auto' }}>{sec.provider}</span>
              {sec.cached && <span style={{ ...S.badge, backgroundColor: COLORS.greenAlpha(0.1), color: COLORS.green, border: `1px solid ${COLORS.greenAlpha(0.2)}` }}>CACHE</span>}
              <span style={{ fontSize: 9, color: COLORS.textDim }}>{sec.latency_ms}ms</span>
            </div>
            <div style={{ fontSize: 10, color: COLORS.textDim, marginBottom: 4 }}>{sec.prompt}</div>
            {sec.response && (
              <div style={{ fontSize: 10, color: COLORS.text, backgroundColor: COLORS.bgCard, padding: 8, borderRadius: 4, maxHeight: 120, overflowY: 'auto', whiteSpace: 'pre-wrap', fontFamily: 'monospace', lineHeight: 1.4, border: `1px solid ${COLORS.border}` }}>
                {sec.response.slice(0, 1000)}
              </div>
            )}
          </div>
        ))}

        {/* Final result */}
        {detail.result && (
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 8 }}>RESULTAT FINAL</div>
            <div style={{ fontSize: 11, color: COLORS.text, backgroundColor: COLORS.bg, padding: 12, borderRadius: 8, border: `1px solid ${COLORS.border}`, whiteSpace: 'pre-wrap', fontFamily: 'monospace', lineHeight: 1.5, maxHeight: 300, overflowY: 'auto' }}>
              {detail.result.slice(0, 3000)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// Main Page
// ═══════════════════════════════════════════════════════════════

export default function PipelinePage() {
  const [tab, setTab] = useState<Tab>('devops');
  const mountedRef = useRef(true);

  // ── Dominos state ──
  const [dominos, setDominos] = useState<Domino[]>([]);
  const [search, setSearch] = useState('');
  const [catFilter, setCatFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState<string | null>(null);
  const { subscribe } = useWebSocket();

  // ── DevOps state ──
  const [devopsPipelines, setDevopsPipelines] = useState<DevOpsPipeline[]>([]);
  const [devopsLoading, setDevopsLoading] = useState(true);
  const [engineStatus, setEngineStatus] = useState<EngineStatus | null>(null);
  const [selectedPipeline, setSelectedPipeline] = useState<PipelineDetail | null>(null);
  const [newPrompt, setNewPrompt] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // ── Cache state ──
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);

  useEffect(() => () => { mountedRef.current = false; }, []);

  // ── Fetch Dominos ──
  const fetchDominos = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(BACKEND_URL + '/api/dominos', { signal: AbortSignal.timeout(10000) });
      if (!mountedRef.current) return;
      if (r.ok) {
        const data = await r.json();
        const list: Domino[] = [];
        for (const d of (data.dominos || data.pipelines || [])) {
          list.push({
            id: d.id || d.domino_id || d.name || '',
            name: d.name || d.id || d.domino_id || '',
            category: d.category || 'general',
            description: d.description || '',
            steps_count: d.steps_count || d.total_steps,
            source: d.source || 'hardcoded',
            trigger_cmd: d.trigger_cmd || d.trigger,
          });
        }
        const cr = await fetch(BACKEND_URL + '/api/dominos/chains?limit=200', { signal: AbortSignal.timeout(5000) });
        if (mountedRef.current && cr.ok) {
          const cd = await cr.json();
          for (const c of (cd.chains || [])) {
            list.push({
              id: `chain_${c.id}`,
              name: c.trigger_cmd || c.description || `Chain #${c.id}`,
              category: 'chain',
              description: c.description || `${c.trigger_cmd} -> ${c.next_cmd}`,
              source: 'db',
              trigger_cmd: c.trigger_cmd,
            });
          }
        }
        if (mountedRef.current) setDominos(list);
      }
    } catch (err) { console.warn('[Pipeline] fetchDominos error:', err instanceof Error ? err.message : err); }
    if (mountedRef.current) setLoading(false);
  }, []);

  // ── Fetch DevOps Pipelines ──
  const fetchDevops = useCallback(async () => {
    setDevopsLoading(true);
    try {
      const [pRes, sRes] = await Promise.all([
        fetch(BACKEND_URL + '/api/devops/pipelines', { signal: AbortSignal.timeout(8000) }),
        fetch(BACKEND_URL + '/api/devops/status', { signal: AbortSignal.timeout(5000) }),
      ]);
      if (!mountedRef.current) return;
      if (pRes.ok) {
        const data = await pRes.json();
        setDevopsPipelines(data.pipelines || []);
      }
      if (sRes.ok) {
        setEngineStatus(await sRes.json());
      }
    } catch (err) { console.warn('[DevOps] fetch error:', err); }
    if (mountedRef.current) setDevopsLoading(false);
  }, []);

  // ── Fetch Cache ──
  const fetchCache = useCallback(async () => {
    try {
      const r = await fetch(BACKEND_URL + '/api/devops/cache', { signal: AbortSignal.timeout(5000) });
      if (mountedRef.current && r.ok) setCacheStats(await r.json());
    } catch (err) { console.warn('[Cache] fetch error:', err); }
  }, []);

  // ── Load on tab change ──
  useEffect(() => {
    if (tab === 'dominos') fetchDominos();
    else if (tab === 'devops') fetchDevops();
    else if (tab === 'cache') fetchCache();
  }, [tab, fetchDominos, fetchDevops, fetchCache]);

  // ── Auto-refresh devops every 10s when active ──
  useEffect(() => {
    if (tab !== 'devops') return;
    const iv = setInterval(fetchDevops, 10000);
    return () => clearInterval(iv);
  }, [tab, fetchDevops]);

  useEffect(() => {
    return subscribe('system', (msg) => {
      if (msg.event === 'domino_complete') setExecuting(null);
    });
  }, [subscribe]);

  // ── DevOps actions ──
  const handleRunPipeline = async () => {
    if (!newPrompt.trim() || submitting) return;
    setSubmitting(true);
    try {
      const r = await fetch(BACKEND_URL + '/api/devops/pipelines/run', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: newPrompt }),
      });
      if (r.ok) {
        setNewPrompt('');
        setTimeout(fetchDevops, 2000);
      }
    } catch (e) { console.warn('Run pipeline error:', e); }
    setSubmitting(false);
  };

  const handleSelectPipeline = async (id: string) => {
    try {
      const r = await fetch(BACKEND_URL + `/api/devops/pipelines/${id}`, { signal: AbortSignal.timeout(8000) });
      if (r.ok) setSelectedPipeline(await r.json());
    } catch (e) { console.warn('Select pipeline error:', e); }
  };

  const handleResume = async (id: string) => {
    try {
      await fetch(BACKEND_URL + `/api/devops/pipelines/${id}/resume`, { method: 'POST' });
      setTimeout(fetchDevops, 3000);
    } catch (e) { console.warn('Resume error:', e); }
  };

  const handleDelete = async (id: string) => {
    try {
      await fetch(BACKEND_URL + `/api/devops/pipelines/${id}`, { method: 'DELETE' });
      fetchDevops();
    } catch (e) { console.warn('Delete error:', e); }
  };

  // ── Dominos filters ──
  const categories = useMemo(() => {
    const cats = new Set<string>();
    dominos.forEach(d => cats.add(d.category));
    return Array.from(cats).sort();
  }, [dominos]);

  const filtered = useMemo(() => {
    let list = dominos;
    if (catFilter) list = list.filter(d => d.category === catFilter);
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(d => d.name.toLowerCase().includes(q) || (d.description || '').toLowerCase().includes(q) || d.category.toLowerCase().includes(q));
    }
    return list;
  }, [dominos, catFilter, search]);

  // ═══════════════════════════════════════════════════════════════
  // Render
  // ═══════════════════════════════════════════════════════════════

  const tabStyle = (t: Tab): React.CSSProperties => ({
    padding: '8px 18px', fontSize: 12, fontWeight: tab === t ? 700 : 400, fontFamily: 'inherit',
    color: tab === t ? COLORS.orange : COLORS.textDim,
    borderBottom: `2px solid ${tab === t ? COLORS.orange : 'transparent'}`,
    background: 'none', border: 'none', borderBottomWidth: 2, borderBottomStyle: 'solid',
    borderBottomColor: tab === t ? COLORS.orange : 'transparent',
  });

  return (
    <>
      <style>{CSS}</style>
      <div className="pipe-page" style={S.page}>
        {/* Header + Tabs */}
        <div style={S.header}>
          <div style={S.title}>Pipelines & Dominos</div>
          <button style={btnStyle} onClick={() => {
            if (tab === 'dominos') fetchDominos();
            else if (tab === 'devops') fetchDevops();
            else fetchCache();
          }}>Actualiser</button>
        </div>

        <div style={{ display: 'flex', gap: 0, borderBottom: `1px solid ${COLORS.border}`, marginBottom: 16 }}>
          <button className="pipe-tab" style={tabStyle('devops')} onClick={() => setTab('devops')}>DevOps Pipelines</button>
          <button className="pipe-tab" style={tabStyle('dominos')} onClick={() => setTab('dominos')}>Dominos</button>
          <button className="pipe-tab" style={tabStyle('cache')} onClick={() => setTab('cache')}>Cache SQL</button>
        </div>

        {/* ══════════ TAB: DevOps Pipelines ══════════ */}
        {tab === 'devops' && (
          <>
            {/* Stats */}
            {engineStatus && (
              <div style={S.stats}>
                <div style={S.stat}>
                  <span style={S.statLabel}>Pipelines</span>
                  <span style={{ ...S.statVal, color: COLORS.orange }}>{engineStatus.pipelines.total}</span>
                </div>
                <div style={S.stat}>
                  <span style={S.statLabel}>Completed</span>
                  <span style={{ ...S.statVal, color: COLORS.green }}>{engineStatus.pipelines.completed}</span>
                </div>
                <div style={S.stat}>
                  <span style={S.statLabel}>Running</span>
                  <span style={{ ...S.statVal, color: COLORS.orange }}>{engineStatus.pipelines.running}</span>
                </div>
                <div style={S.stat}>
                  <span style={S.statLabel}>Sections OK</span>
                  <span style={{ ...S.statVal, color: COLORS.purple }}>{engineStatus.sections.completed}/{engineStatus.sections.total}</span>
                </div>
                <div style={S.stat}>
                  <span style={S.statLabel}>Cache</span>
                  <span style={{ ...S.statVal, color: COLORS.textDim }}>{engineStatus.cache.entries}</span>
                </div>
                <div style={S.stat}>
                  <span style={S.statLabel}>Templates</span>
                  <span style={{ ...S.statVal, color: COLORS.textDim }}>{engineStatus.templates.count}</span>
                </div>
              </div>
            )}

            {/* New pipeline form */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              <input className="pipe-input" style={{ ...S.search, flex: 1 }}
                placeholder="Nouvelle tache pipeline (ex: Cree un middleware auth JWT)..."
                value={newPrompt}
                onChange={e => setNewPrompt(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleRunPipeline()} />
              <button style={{ ...S.execBtn, width: 'auto', padding: '8px 20px', opacity: submitting ? 0.5 : 1 }}
                onClick={handleRunPipeline} disabled={submitting || !newPrompt.trim()}>
                {submitting ? 'Envoi...' : 'Lancer Pipeline'}
              </button>
            </div>

            {/* Pipeline list */}
            {devopsLoading ? (
              <div style={S.emptyState}>Chargement pipelines DevOps...</div>
            ) : devopsPipelines.length === 0 ? (
              <div style={S.emptyState}>Aucun pipeline DevOps. Lancez-en un ci-dessus.</div>
            ) : (
              <div style={S.grid}>
                {devopsPipelines.map(p => (
                  <DevOpsCard key={p.id} pipeline={p}
                    onSelect={handleSelectPipeline}
                    onResume={handleResume}
                    onDelete={handleDelete} />
                ))}
              </div>
            )}

            {/* Detail side panel */}
            {selectedPipeline && (
              <PipelineDetailPanel detail={selectedPipeline} onClose={() => setSelectedPipeline(null)} />
            )}
          </>
        )}

        {/* ══════════ TAB: Dominos (existing) ══════════ */}
        {tab === 'dominos' && (
          <>
            <div style={S.stats}>
              <div style={S.stat}>
                <span style={S.statLabel}>Total</span>
                <span style={{ ...S.statVal, color: COLORS.orange }}>{dominos.length}</span>
              </div>
              <div style={S.stat}>
                <span style={S.statLabel}>Hardcoded</span>
                <span style={{ ...S.statVal, color: COLORS.purple }}>{dominos.filter(d => d.source === 'hardcoded').length}</span>
              </div>
              <div style={S.stat}>
                <span style={S.statLabel}>DB Chains</span>
                <span style={{ ...S.statVal, color: COLORS.green }}>{dominos.filter(d => d.source === 'db').length}</span>
              </div>
              <div style={S.stat}>
                <span style={S.statLabel}>Categories</span>
                <span style={{ ...S.statVal, color: COLORS.textDim }}>{categories.length}</span>
              </div>
            </div>

            <div style={S.toolbar}>
              <input className="pipe-input" style={S.search} placeholder="Rechercher dominos, pipelines..."
                value={search} onChange={e => setSearch(e.target.value)} />
              <button style={{ ...S.filterBtn, ...(catFilter === '' ? S.filterActive : {}) }} onClick={() => setCatFilter('')}>Tous</button>
              {categories.slice(0, 6).map(cat => (
                <button key={cat} style={{ ...S.filterBtn, ...(catFilter === cat ? S.filterActive : {}) }}
                  onClick={() => setCatFilter(catFilter === cat ? '' : cat)}>{cat}</button>
              ))}
            </div>

            {loading ? (
              <div style={S.emptyState}>Chargement des pipelines...</div>
            ) : filtered.length === 0 ? (
              <div style={S.emptyState}>Aucun pipeline trouve{search ? ` pour "${search}"` : ''}</div>
            ) : (
              <>
                <div style={{ fontSize: 10, color: COLORS.textDim, marginBottom: 10 }}>{filtered.length} pipelines</div>
                <div style={S.grid}>
                  {filtered.map(d => (
                    <DominoCard key={d.id} domino={d} onExecute={(dm) => setExecuting(dm.id)} onDone={() => setExecuting(null)} executing={executing} />
                  ))}
                </div>
              </>
            )}
          </>
        )}

        {/* ══════════ TAB: Cache SQL ══════════ */}
        {tab === 'cache' && (
          <>
            {cacheStats ? (
              <>
                <div style={S.stats}>
                  <div style={S.stat}>
                    <span style={S.statLabel}>Entrees cache</span>
                    <span style={{ ...S.statVal, color: COLORS.orange }}>{cacheStats.total_entries}</span>
                  </div>
                  <div style={S.stat}>
                    <span style={S.statLabel}>Total hits</span>
                    <span style={{ ...S.statVal, color: COLORS.green }}>{cacheStats.total_hits}</span>
                  </div>
                </div>

                {/* Top categories */}
                {Object.keys(cacheStats.top_categories).length > 0 && (
                  <div style={{ marginBottom: 20 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: COLORS.text, marginBottom: 10 }}>Categories</div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {Object.entries(cacheStats.top_categories).map(([cat, count]) => (
                        <div key={cat} style={{ ...S.badge, ...S.catBadge, padding: '4px 12px', fontSize: 11 }}>
                          {cat}: {count}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recent cache entries */}
                <div style={{ fontSize: 12, fontWeight: 600, color: COLORS.text, marginBottom: 10 }}>Entrees recentes</div>
                {cacheStats.recent.map((entry, i) => (
                  <div key={i} style={{ padding: '8px 12px', marginBottom: 6, borderRadius: 6, border: `1px solid ${COLORS.border}`, backgroundColor: COLORS.bgCard, display: 'flex', alignItems: 'center', gap: 10, fontSize: 11 }}>
                    <span style={{ color: COLORS.text, flex: 1 }}>{entry.prompt}</span>
                    <span style={{ color: COLORS.purple, fontSize: 9 }}>{entry.provider}</span>
                    <span style={{ ...S.badge, ...S.catBadge }}>{entry.category}</span>
                    <span style={{ color: COLORS.green, fontSize: 9 }}>{entry.hits} hits</span>
                  </div>
                ))}
              </>
            ) : (
              <div style={S.emptyState}>Chargement du cache...</div>
            )}
          </>
        )}
      </div>
    </>
  );
}
