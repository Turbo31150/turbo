import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { BACKEND_URL } from '../lib/config';

interface Skill {
  name: string;
  description: string;
  category?: string;
  trigger?: string;
}

interface BenchRun {
  id: number;
  run_name: string;
  date: string;
  total_score: number;
  phases: number;
  results?: any;
}

interface McpTool {
  name: string;
  description: string;
  category?: string;
}

const CSS = `
@keyframes tbFade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.tb-card{animation:tbFade .2s ease;transition:border-color .3s}
.tb-card:hover{border-color:rgba(192,132,252,.3)!important}
.tb-tab:hover{color:#e0e0e0!important}
.tb-page::-webkit-scrollbar{width:5px}
.tb-page::-webkit-scrollbar-thumb{background:#2a2a3a;border-radius:3px}
`;

const S = {
  page: { padding: 20, fontFamily: 'Consolas, "Courier New", monospace', height: '100%', overflowY: 'auto' } as React.CSSProperties,
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 } as React.CSSProperties,
  title: { fontSize: 18, fontWeight: 700, color: '#e0e0e0' } as React.CSSProperties,
  tabs: { display: 'flex', gap: 2, marginBottom: 16, borderBottom: '1px solid #1a2a3a' } as React.CSSProperties,
  tab: { padding: '8px 16px', fontSize: 12, fontWeight: 600, color: '#6b7280', cursor: 'pointer', background: 'none', border: 'none', borderBottom: '2px solid transparent', fontFamily: 'inherit', transition: 'all .2s' } as React.CSSProperties,
  tabActive: { color: '#c084fc', borderBottomColor: '#c084fc' },
  search: { width: '100%', maxWidth: 400, padding: '8px 12px', backgroundColor: '#0d1117', border: '1px solid #2a3a4a', borderRadius: 6, color: '#e0e0e0', fontSize: 12, fontFamily: 'inherit', outline: 'none', marginBottom: 16 } as React.CSSProperties,
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12 } as React.CSSProperties,
  card: { backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 10, padding: 14 } as React.CSSProperties,
  cardName: { fontSize: 13, fontWeight: 700, color: '#e0e0e0', marginBottom: 4 } as React.CSSProperties,
  cardDesc: { fontSize: 11, color: '#6b7280', lineHeight: 1.4 } as React.CSSProperties,
  badge: { fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 4, letterSpacing: .5, backgroundColor: 'rgba(192,132,252,.1)', color: '#c084fc', border: '1px solid rgba(192,132,252,.2)' } as React.CSSProperties,
  benchCard: { backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 10, padding: 16 } as React.CSSProperties,
  benchScore: { fontSize: 28, fontWeight: 700, marginBottom: 4 } as React.CSSProperties,
  emptyState: { textAlign: 'center', padding: 40, color: '#6b7280', fontSize: 13 } as React.CSSProperties,
  statRow: { display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 11, borderBottom: '1px solid #0a0e14' } as React.CSSProperties,
};

type Tab = 'skills' | 'benchmarks' | 'mcp';

const FALLBACK_MCP_TOOLS: McpTool[] = [
  { name: 'gemini_query', description: 'Query Gemini API via proxy', category: 'bridge' },
  { name: 'bridge_query', description: 'Multi-node bridge query', category: 'bridge' },
  { name: 'bridge_mesh', description: 'Mesh consensus across agents', category: 'bridge' },
  { name: 'web_search', description: 'Web search via minimax', category: 'search' },
  { name: 'code_analysis', description: 'Code analysis and review', category: 'code' },
  { name: 'file_operations', description: 'File system operations', category: 'files' },
  { name: 'system_info', description: 'System diagnostics', category: 'system' },
  { name: 'trading_scan', description: 'Trading signal scanner', category: 'trading' },
  { name: 'trading_execute', description: 'Execute trading signals', category: 'trading' },
  { name: 'browser_navigate', description: 'Browser automation', category: 'browser' },
  { name: 'telegram_send', description: 'Telegram bot messaging', category: 'communication' },
  { name: 'n8n_trigger', description: 'Trigger n8n workflows', category: 'automation' },
  { name: 'tts_speak', description: 'Text-to-speech via Edge TTS', category: 'voice' },
  { name: 'whisper_transcribe', description: 'Speech-to-text via Whisper', category: 'voice' },
  { name: 'wake_word_control', description: 'Wake word detection control', category: 'voice' },
];

export default function ToolboxPage() {
  const [tab, setTab] = useState<Tab>('skills');
  const [skills, setSkills] = useState<Skill[]>([]);
  const [benchmarks, setBenchmarks] = useState<BenchRun[]>([]);
  const [mcpTools, setMcpTools] = useState<McpTool[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const { connected, request } = useWebSocket();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch skills from etoile.db via SQL endpoint
      const skillsResp = await fetch(BACKEND_URL + '/sql/query', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: "SELECT name, description, category, trigger_phrase as trigger FROM pipeline_dictionary ORDER BY category, name", db: "etoile" }),
        signal: AbortSignal.timeout(5000),
      });
      if (skillsResp.ok) {
        const data = await skillsResp.json();
        setSkills((data.rows || data.results || []).map((r: any) => ({
          name: r.name || r[0] || '',
          description: r.description || r[1] || '',
          category: r.category || r[2] || '',
          trigger: r.trigger || r[3] || '',
        })));
      }
    } catch { /* SQL endpoint may not exist yet */ }

    try {
      // Fetch benchmarks
      const benchResp = await fetch(BACKEND_URL + '/sql/query', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: "SELECT id, run_name, date, total_score, phases FROM benchmark_runs ORDER BY id DESC LIMIT 10", db: "etoile" }),
        signal: AbortSignal.timeout(5000),
      });
      if (benchResp.ok) {
        const data = await benchResp.json();
        setBenchmarks((data.rows || data.results || []).map((r: any) => ({
          id: r.id || r[0] || 0,
          run_name: r.run_name || r[1] || '',
          date: r.date || r[2] || '',
          total_score: r.total_score || r[3] || 0,
          phases: r.phases || r[4] || 0,
        })));
      }
    } catch { /* */ }

    // Fetch MCP tools dynamically, fallback to static list
    if (connected) {
      try {
        const resp = await request('system', 'get_tools');
        const tools = resp.payload?.tools;
        if (Array.isArray(tools) && tools.length > 0) {
          setMcpTools(tools.map((t: any) => ({ name: t.name || '', description: t.description || '', category: t.category || '' })));
        } else {
          setMcpTools(FALLBACK_MCP_TOOLS);
        }
      } catch {
        setMcpTools(FALLBACK_MCP_TOOLS);
      }
    } else {
      setMcpTools(FALLBACK_MCP_TOOLS);
    }
    setLoading(false);
  }, [connected, request]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filteredSkills = useMemo(() => {
    if (!search) return skills;
    const q = search.toLowerCase();
    return skills.filter(s => s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q) || (s.category || '').toLowerCase().includes(q));
  }, [skills, search]);

  const filteredTools = useMemo(() => {
    if (!search) return mcpTools;
    const q = search.toLowerCase();
    return mcpTools.filter(t => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q));
  }, [mcpTools, search]);

  return (
    <>
      <style>{CSS}</style>
      <div className="tb-page" style={S.page}>
        <div style={S.header}>
          <div style={S.title}>Toolbox</div>
        </div>

        <div style={S.tabs}>
          {([
            { id: 'skills' as Tab, label: `Skills (${skills.length})` },
            { id: 'benchmarks' as Tab, label: `Benchmarks (${benchmarks.length})` },
            { id: 'mcp' as Tab, label: `MCP Tools (${mcpTools.length})` },
          ]).map(t => (
            <button key={t.id} className="tb-tab"
              style={{ ...S.tab, ...(tab === t.id ? S.tabActive : {}) }}
              onClick={() => { setTab(t.id); setSearch(''); }}>{t.label}</button>
          ))}
        </div>

        {(tab === 'skills' || tab === 'mcp') && (
          <input style={S.search} placeholder={`Rechercher ${tab === 'skills' ? 'skills' : 'outils MCP'}...`}
            value={search} onChange={e => setSearch(e.target.value)} />
        )}

        {loading ? (
          <div style={S.emptyState}>Chargement...</div>
        ) : (
          <>
            {/* Skills tab */}
            {tab === 'skills' && (
              filteredSkills.length === 0 ? (
                <div style={S.emptyState}>
                  {skills.length === 0 ? 'Aucun skill charge depuis etoile.db' : `Aucun resultat pour "${search}"`}
                </div>
              ) : (
                <div style={S.grid}>
                  {filteredSkills.map((skill, i) => (
                    <div key={i} className="tb-card" style={S.card}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        <span style={S.cardName}>{skill.name}</span>
                        {skill.category && <span style={S.badge}>{skill.category}</span>}
                      </div>
                      <div style={S.cardDesc}>{skill.description || 'Pas de description'}</div>
                      {skill.trigger && <div style={{ fontSize: 10, color: '#f97316', marginTop: 6 }}>Trigger: "{skill.trigger}"</div>}
                    </div>
                  ))}
                </div>
              )
            )}

            {/* Benchmarks tab */}
            {tab === 'benchmarks' && (
              benchmarks.length === 0 ? (
                <div style={S.emptyState}>Aucun benchmark dans etoile.db</div>
              ) : (
                <div style={S.grid}>
                  {benchmarks.map(bench => (
                    <div key={bench.id} className="tb-card" style={S.benchCard}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                        <span style={S.cardName}>{bench.run_name || `Run #${bench.id}`}</span>
                        <span style={{ fontSize: 10, color: '#6b7280' }}>{bench.date}</span>
                      </div>
                      <div style={{ ...S.benchScore, color: bench.total_score >= 90 ? '#10b981' : bench.total_score >= 70 ? '#f97316' : '#ef4444' }}>
                        {bench.total_score}/100
                      </div>
                      <div style={S.statRow}>
                        <span style={{ color: '#6b7280' }}>Phases</span>
                        <span style={{ color: '#e0e0e0' }}>{bench.phases}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )
            )}

            {/* MCP Tools tab */}
            {tab === 'mcp' && (
              <div style={S.grid}>
                {filteredTools.map((tool, i) => (
                  <div key={i} className="tb-card" style={S.card}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={S.cardName}>{tool.name}</span>
                      {tool.category && <span style={S.badge}>{tool.category}</span>}
                    </div>
                    <div style={S.cardDesc}>{tool.description}</div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
