import React, { useState, useEffect, useCallback, useMemo, useRef, memo } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { BACKEND_URL } from '../lib/config';
import { COLORS, FONT } from '../lib/theme';

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

const CSS = `
@keyframes pipeFade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.pipe-card{animation:pipeFade .2s ease;transition:border-color .3s}
.pipe-card:hover{border-color:${COLORS.orangeAlpha(0.3)}!important}
.pipe-input:focus{border-color:${COLORS.orange}!important}
.pipe-page::-webkit-scrollbar{width:5px}
.pipe-page::-webkit-scrollbar-thumb{background:${COLORS.border};border-radius:3px}
@keyframes pipeExec{0%{opacity:1}50%{opacity:.5}100%{opacity:1}}
`;

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
    backgroundColor: status === 'passed' || status === 'ok' ? COLORS.green : status === 'failed' ? COLORS.red : COLORS.textDim,
  }),
  emptyState: { textAlign: 'center', padding: 40, color: COLORS.textDim, fontSize: 13 } as React.CSSProperties,
  logsPanel: { marginTop: 8, fontSize: 10, color: COLORS.textDim } as React.CSSProperties,
};

const btnStyle = { padding: '6px 14px', borderRadius: 6, border: `1px solid ${COLORS.border}`, backgroundColor: 'transparent', color: COLORS.textDim, fontSize: 11, cursor: 'pointer', fontFamily: 'inherit' } as React.CSSProperties;

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

export default function PipelinePage() {
  const [dominos, setDominos] = useState<Domino[]>([]);
  const [search, setSearch] = useState('');
  const [catFilter, setCatFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState<string | null>(null);
  const { subscribe } = useWebSocket();
  const mountedRef = useRef(true);

  useEffect(() => () => { mountedRef.current = false; }, []);

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

  useEffect(() => { fetchDominos(); }, [fetchDominos]);

  useEffect(() => {
    return subscribe('system', (msg) => {
      if (msg.event === 'domino_complete') {
        setExecuting(null);
      }
    });
  }, [subscribe]);

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

  return (
    <>
      <style>{CSS}</style>
      <div className="pipe-page" style={S.page}>
        <div style={S.header}>
          <div style={S.title}>Pipelines & Dominos</div>
          <button style={btnStyle} onClick={fetchDominos}>Actualiser</button>
        </div>

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
      </div>
    </>
  );
}
