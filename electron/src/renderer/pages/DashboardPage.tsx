import React, { useState, useRef, useEffect, useCallback, useMemo, memo } from 'react';
import { useLMStudio } from '../hooks/useLMStudio';
import { useWebSocket } from '../hooks/useWebSocket';
import AgentSelector from '../components/AgentSelector';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface JMsg {
  id: string;
  role: 'user' | 'bot' | 'sys';
  text: string;
  agent?: string;
  model?: string;
  latency?: number;
  ts: number;
}

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const BACKEND_URL = 'http://127.0.0.1:9742';

const ENGINES = [
  { id: 'auto', icon: '\u2728', name: 'Auto', desc: 'Routage intelligent', agent: 'main' },
  { id: 'lmstudio', icon: '\uD83D\uDDA5', name: 'LM Studio', desc: 'Local (OL1/M2/M3)', agent: 'local' },
  { id: 'claude', icon: '\uD83E\uDDE0', name: 'Claude Code', desc: 'Raisonnement cloud', agent: 'claude' },
  { id: 'raison', icon: '\uD83E\uDDEE', name: 'Raisonnement', desc: 'Logique & Math (M1)', agent: 'raisonnement' },
  { id: 'gemini', icon: '\u2B50', name: 'Gemini', desc: 'Architecture & vision', agent: 'gemini' },
  { id: 'consensus', icon: '\u2696', name: 'Consensus', desc: 'Vote multi-IA', agent: 'consensus' },
];

const TOOLS = [
  { id: 'web', icon: '\uD83D\uDD0D', name: 'Recherche Web', prefix: '/web ' },
  { id: 'code', icon: '\uD83D\uDCBB', name: 'Analyse Code', prefix: '/code ' },
  { id: 'files', icon: '\uD83D\uDCC1', name: 'Fichiers', prefix: '/files ' },
  { id: 'system', icon: '\u2699\uFE0F', name: 'Systeme', prefix: '/sys ' },
  { id: 'trading', icon: '\uD83D\uDCC8', name: 'Trading', prefix: '/trading ' },
  { id: 'browser', icon: '\uD83C\uDF10', name: 'Navigateur', prefix: '/browse ' },
  { id: 'telegram', icon: '\uD83D\uDCE8', name: 'Telegram', prefix: '/tg ' },
  { id: 'n8n', icon: '\u26A1', name: 'n8n Workflows', prefix: '/n8n ' },
];

const CLUSTER_NODES = [
  { id: 'OL1', name: 'OL1 (qwen3)', lat: '0.5s' },
  { id: 'M2', name: 'M2 (deepseek)', lat: '1.3s' },
  { id: 'M3', name: 'M3 (mistral)', lat: '2.5s' },
  { id: 'M1', name: 'M1 (qwen3-30b)', lat: '2-50s' },
  { id: 'Gemini', name: 'Gemini API', lat: 'var' },
  { id: 'Claude', name: 'Claude Bridge', lat: 'var' },
];

const CHIPS = [
  'Scan trading', 'Debug ce bug', 'Cherche sur le web',
  'Etat du cluster', 'Mode gaming', 'Analyse ce code',
  'Resume ce fichier', 'Optimise les performances',
];

// ═══════════════════════════════════════════════════════════════
// CSS ANIMATIONS
// ═══════════════════════════════════════════════════════════════

const CSS = `
@keyframes jPulse{0%,100%{opacity:1}50%{opacity:.3}}
@keyframes jFadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@keyframes jDots{0%,20%{opacity:.15}50%{opacity:1}80%,100%{opacity:.15}}
@keyframes jScan{0%{background-position:-200% 0}100%{background-position:200% 0}}
.j-side::-webkit-scrollbar{width:4px}
.j-side::-webkit-scrollbar-thumb{background:#2a2a3a;border-radius:2px}
.j-msgs::-webkit-scrollbar{width:5px}
.j-msgs::-webkit-scrollbar-thumb{background:#2a2a3a;border-radius:3px}
.j-msgs::-webkit-scrollbar-track{background:transparent}
.j-msg{animation:jFadeIn .3s ease}
.j-chip:hover{border-color:#f97316!important;color:#f97316!important}
.j-eng:hover{background:rgba(249,115,22,.05)!important}
.j-tool:hover{color:#e0e0e0!important}
.j-send:hover:not(:disabled){transform:scale(1.03);box-shadow:0 4px 20px rgba(249,115,22,.4)}
.j-send:active:not(:disabled){transform:scale(.97)}
.j-chips::-webkit-scrollbar{height:3px}
.j-chips::-webkit-scrollbar-thumb{background:#2a2a3a;border-radius:2px}
`;

// ═══════════════════════════════════════════════════════════════
// SAFE TEXT RENDERER (no innerHTML — XSS-safe)
// ═══════════════════════════════════════════════════════════════

const TextBlock = memo(function TextBlock({ text }: { text: string }) {
  // Split on code blocks first
  const parts = text.split(/(```[\s\S]*?```)/g);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {parts.map((part, i) => {
        if (part.startsWith('```') && part.endsWith('```')) {
          const langMatch = part.match(/^```(\w+)\n/);
          const lang = langMatch?.[1] || '';
          const code = part.slice(3, -3).replace(/^\w*\n/, '');
          return (
            <div key={i} style={{ margin: '6px 0' }}>
              {lang && <div style={{ fontSize: 9, color: '#6b7280', letterSpacing: 1, textTransform: 'uppercase', marginBottom: 2, paddingLeft: 4 }}>{lang}</div>}
              <pre style={{ background: '#080c12', padding: '10px 12px', borderRadius: 6, overflowX: 'auto', border: '1px solid #1a2a3a', fontSize: 12, lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0 }}>
                <code style={{ color: '#d4d4d4' }}>{code.trim()}</code>
              </pre>
            </div>
          );
        }
        // Inline formatting — skip empty fragments
        if (!part.trim()) return null;
        return <InlineText key={i} text={part} />;
      })}
    </div>
  );
});

function InlineText({ text }: { text: string }) {
  // Split on double newlines for paragraphs, single newlines within
  const paragraphs = text.split(/\n{2,}/);
  return (
    <>
      {paragraphs.map((para, pi) => {
        const lines = para.split('\n');
        return (
          <div key={pi} style={pi > 0 ? { marginTop: 6 } : undefined}>
            {lines.map((line, li) => (
              <React.Fragment key={li}>
                {li > 0 && <br />}
                <InlineLine line={line} />
              </React.Fragment>
            ))}
          </div>
        );
      })}
    </>
  );
}

function InlineLine({ line }: { line: string }) {
  // Handle horizontal rule
  if (/^[-*_]{3,}\s*$/.test(line)) return <hr style={{ border: 'none', borderTop: '1px solid #1a2a3a', margin: '8px 0' }} />;
  // Handle headings
  if (line.startsWith('### ')) return <div style={{ fontSize: 13, fontWeight: 700, color: '#f97316', margin: '8px 0 3px' }}><InlineFormatted text={line.slice(4)} /></div>;
  if (line.startsWith('## ')) return <div style={{ fontSize: 14, fontWeight: 700, color: '#c084fc', margin: '10px 0 3px' }}><InlineFormatted text={line.slice(3)} /></div>;
  if (line.startsWith('# ')) return <div style={{ fontSize: 15, fontWeight: 700, color: '#e0e0e0', margin: '10px 0 4px' }}><InlineFormatted text={line.slice(2)} /></div>;
  // Handle blockquote
  if (line.startsWith('> ')) return <div style={{ borderLeft: '2px solid #f97316', paddingLeft: 10, color: '#9ca3af', fontStyle: 'italic' }}><InlineFormatted text={line.slice(2)} /></div>;
  // Handle list items
  if (/^[-*] /.test(line)) return <div style={{ paddingLeft: 12, display: 'flex', gap: 6 }}><span style={{ color: '#f97316', flexShrink: 0 }}>{'\u2022'}</span><span><InlineFormatted text={line.slice(2)} /></span></div>;
  if (/^\d+\. /.test(line)) {
    const num = line.match(/^(\d+)\. /)?.[1] || '';
    const rest = line.replace(/^\d+\. /, '');
    return <div style={{ paddingLeft: 12, display: 'flex', gap: 6 }}><span style={{ color: '#6b7280', flexShrink: 0 }}>{num}.</span><span><InlineFormatted text={rest} /></span></div>;
  }
  // Empty line
  if (!line.trim()) return null;
  return <span><InlineFormatted text={line} /></span>;
}

function InlineFormatted({ text }: { text: string }) {
  // Split on inline code, bold, italic
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return (
    <>
      {tokens.map((tok, i) => {
        if (tok.startsWith('`') && tok.endsWith('`'))
          return <code key={i} style={{ background: '#1a2a3a', padding: '1px 5px', borderRadius: 3, fontSize: 12 }}>{tok.slice(1, -1)}</code>;
        if (tok.startsWith('**') && tok.endsWith('**'))
          return <strong key={i} style={{ color: '#e8e8e8' }}>{tok.slice(2, -2)}</strong>;
        if (tok.startsWith('*') && tok.endsWith('*'))
          return <em key={i}>{tok.slice(1, -1)}</em>;
        return <React.Fragment key={i}>{tok}</React.Fragment>;
      })}
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
// STYLES
// ═══════════════════════════════════════════════════════════════

const ST = {
  root: { display: 'flex', height: '100%', fontFamily: 'Consolas, "Courier New", monospace', backgroundColor: '#0a0e14', color: '#e0e0e0', overflow: 'hidden' } as React.CSSProperties,
  side: { width: 240, backgroundColor: '#0d1117', borderRight: '1px solid #1a2a3a', display: 'flex', flexDirection: 'column', flexShrink: 0 } as React.CSSProperties,
  sideScroll: { flex: 1, overflowY: 'auto', padding: '4px 0' } as React.CSSProperties,
  secHead: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px 6px', cursor: 'pointer', userSelect: 'none' } as React.CSSProperties,
  secLabel: { fontSize: 10, letterSpacing: 1.5, textTransform: 'uppercase', color: '#6b7280', fontWeight: 700 } as React.CSSProperties,
  secBadge: { fontSize: 9, backgroundColor: '#f97316', color: '#000', borderRadius: 10, padding: '1px 7px', fontWeight: 700 } as React.CSSProperties,
  engBtn: { display: 'flex', alignItems: 'center', gap: 10, padding: '7px 14px', width: '100%', border: 'none', background: 'transparent', cursor: 'pointer', color: '#c0c0c0', fontFamily: 'inherit', fontSize: 12, textAlign: 'left', transition: 'all .15s', borderLeft: '3px solid transparent' } as React.CSSProperties,
  engActive: { borderLeftColor: '#f97316', backgroundColor: 'rgba(249,115,22,.08)', color: '#f97316' } as React.CSSProperties,
  engIcon: { fontSize: 16, width: 24, textAlign: 'center', flexShrink: 0 } as React.CSSProperties,
  engInfo: { flex: 1, display: 'flex', flexDirection: 'column', gap: 1, minWidth: 0 } as React.CSSProperties,
  engName: { fontSize: 12, fontWeight: 600 } as React.CSSProperties,
  engDesc: { fontSize: 9, color: '#6b7280', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } as React.CSSProperties,
  dot: { width: 7, height: 7, borderRadius: '50%', flexShrink: 0 } as React.CSSProperties,
  dotOn: { backgroundColor: '#10b981', boxShadow: '0 0 6px rgba(16,185,129,.5)' },
  dotOff: { backgroundColor: '#4b5563' },
  toolBtn: { display: 'flex', alignItems: 'center', gap: 8, padding: '5px 14px', width: '100%', border: 'none', background: 'transparent', cursor: 'pointer', color: '#9ca3af', fontFamily: 'inherit', fontSize: 11, textAlign: 'left', transition: 'color .15s' } as React.CSSProperties,
  cNode: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 14px' } as React.CSSProperties,
  cName: { fontSize: 11, color: '#c0c0c0', display: 'flex', alignItems: 'center', gap: 8 } as React.CSSProperties,
  cLat: { fontSize: 10, color: '#6b7280' } as React.CSSProperties,
  main: { flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 } as React.CSSProperties,
  bar: { display: 'flex', alignItems: 'center', padding: '8px 16px', borderBottom: '1px solid #1a2a3a', fontSize: 10, color: '#6b7280', letterSpacing: .5, textTransform: 'uppercase', background: 'linear-gradient(90deg,transparent,rgba(249,115,22,.03),transparent)', backgroundSize: '200% 100%', animation: 'jScan 8s linear infinite' } as React.CSSProperties,
  barText: { flex: 1 } as React.CSSProperties,
  learn: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 10px', borderRadius: 12, backgroundColor: 'rgba(192,132,252,.1)', border: '1px solid rgba(192,132,252,.25)', fontSize: 10, color: '#c084fc', fontWeight: 700, letterSpacing: 1 } as React.CSSProperties,
  learnDot: { width: 6, height: 6, borderRadius: '50%', backgroundColor: '#c084fc', animation: 'jPulse 2s ease infinite' } as React.CSSProperties,
  hBadge: { display: 'inline-flex', alignItems: 'center', gap: 5, marginLeft: 10, padding: '3px 10px', borderRadius: 12, fontSize: 10, fontWeight: 700, letterSpacing: 1 } as React.CSSProperties,
  hOk: { backgroundColor: 'rgba(16,185,129,.1)', border: '1px solid rgba(16,185,129,.25)', color: '#10b981' },
  hErr: { backgroundColor: 'rgba(239,68,68,.1)', border: '1px solid rgba(239,68,68,.25)', color: '#ef4444' },
  msgs: { flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 } as React.CSSProperties,
  empty: { flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 } as React.CSSProperties,
  emptyLogo: { fontSize: 42, fontWeight: 800, letterSpacing: 6, background: 'linear-gradient(135deg,#f97316,#c084fc)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' } as React.CSSProperties,
  emptyHint: { fontSize: 12, color: '#6b7280' } as React.CSSProperties,
  userMsg: { alignSelf: 'flex-end', maxWidth: '65%', backgroundColor: 'rgba(249,115,22,.08)', border: '1px solid rgba(249,115,22,.15)', borderRadius: '14px 14px 4px 14px', padding: '10px 16px', fontSize: 13, lineHeight: 1.6, wordBreak: 'break-word' } as React.CSSProperties,
  botMsg: { alignSelf: 'flex-start', maxWidth: '85%', backgroundColor: '#111820', border: '1px solid #1a2a3a', borderRadius: '14px 14px 14px 4px', padding: '12px 16px', fontSize: 13, lineHeight: 1.7, wordBreak: 'break-word' } as React.CSSProperties,
  sysMsg: { alignSelf: 'center', maxWidth: '80%', border: '1px dashed rgba(239,68,68,.3)', borderRadius: 8, padding: '6px 14px', fontSize: 11, color: '#ef4444', textAlign: 'center' } as React.CSSProperties,
  meta: { display: 'inline-flex', gap: 6, marginTop: 8, padding: '3px 0', fontSize: 10, borderTop: '1px solid rgba(255,255,255,.04)' } as React.CSSProperties,
  metaTag: { padding: '1px 8px', borderRadius: 10, fontSize: 9, fontWeight: 600, letterSpacing: .5 } as React.CSSProperties,
  inputWrap: { borderTop: '1px solid #1a2a3a', padding: '10px 16px', backgroundColor: '#0d1117' } as React.CSSProperties,
  chips: { display: 'flex', gap: 6, marginBottom: 8, overflowX: 'auto', paddingBottom: 2 } as React.CSSProperties,
  chip: { padding: '4px 12px', borderRadius: 16, border: '1px solid #2a3a4a', background: 'transparent', color: '#6b7280', fontSize: 10, cursor: 'pointer', fontFamily: 'inherit', textTransform: 'uppercase', letterSpacing: .5, whiteSpace: 'nowrap', transition: 'all .2s', flexShrink: 0 } as React.CSSProperties,
  inputRow: { display: 'flex', gap: 8, alignItems: 'flex-end' } as React.CSSProperties,
  ta: { flex: 1, backgroundColor: '#0a0e14', border: '1px solid #2a3a4a', borderRadius: 8, color: '#e0e0e0', fontFamily: 'inherit', fontSize: 13, padding: '10px 14px', resize: 'none', outline: 'none', maxHeight: 120, lineHeight: 1.5 } as React.CSSProperties,
  send: { padding: '0 20px', background: 'linear-gradient(135deg,#f97316,#ea580c)', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 700, fontFamily: 'inherit', fontSize: 14, cursor: 'pointer', flexShrink: 0, height: 42, transition: 'all .15s' } as React.CSSProperties,
  sendOff: { opacity: .35, cursor: 'not-allowed', background: '#2a3a4a', color: '#6b7280' },
  bottom: { display: 'flex', alignItems: 'center', gap: 12, marginTop: 6, fontSize: 10, color: '#4b5563' } as React.CSSProperties,
  loadRow: { display: 'flex', alignItems: 'center', gap: 5, padding: '4px 0', fontSize: 11, color: '#6b7280' } as React.CSSProperties,
  loadDot: { width: 6, height: 6, borderRadius: '50%', backgroundColor: '#f97316' } as React.CSSProperties,
};

// ═══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════

export default function DashboardPage() {
  const [msgs, setMsgs] = useState<JMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [engine, setEngine] = useState('auto');
  const [input, setInput] = useState('');
  const [backendOk, setBackendOk] = useState(false);
  const [autolearn, setAutolearn] = useState<any>(null);
  const [openSec, setOpenSec] = useState({ engines: true, tools: true, cluster: true });
  const [voiceStatus, setVoiceStatus] = useState<{ wakeWord: boolean; lastTranscript?: string; latency?: number }>({ wakeWord: false });
  const [selectedModel, setSelectedModel] = useState('');
  const msgEnd = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const { nodes: lmNodes } = useLMStudio();
  const { connected, request, subscribe } = useWebSocket();

  // Backend health via WS 9742
  useEffect(() => {
    setBackendOk(connected);
  }, [connected]);

  // Health check REST fallback (for when WS is connecting)
  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const r = await fetch(BACKEND_URL + '/health', { signal: AbortSignal.timeout(3000) });
        if (alive && r.ok) setBackendOk(true);
      } catch { /* WS state is primary */ }
    };
    if (!connected) check();
    const iv = setInterval(() => { if (!connected) check(); }, 15000);
    return () => { alive = false; clearInterval(iv); };
  }, [connected]);

  // Autolearn poll (try Canvas proxy, fallback gracefully)
  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const r = await fetch('http://127.0.0.1:18800/autolearn/status', { signal: AbortSignal.timeout(3000) });
        if (r.ok && alive) setAutolearn(await r.json());
      } catch { if (alive) setAutolearn(null); }
    };
    poll();
    const iv = setInterval(poll, 30000);
    return () => { alive = false; clearInterval(iv); };
  }, []);

  // Subscribe to voice events for dashboard widget
  useEffect(() => {
    const unsub = subscribe('voice', (msg) => {
      if (msg.event === 'transcription_result') {
        setVoiceStatus(prev => ({
          ...prev,
          lastTranscript: msg.payload?.text,
          latency: msg.payload?.latency,
        }));
      }
      if (msg.event === 'wake_detected') {
        setVoiceStatus(prev => ({ ...prev, wakeWord: true }));
        setTimeout(() => setVoiceStatus(prev => ({ ...prev, wakeWord: false })), 3000);
      }
    });
    return unsub;
  }, [subscribe]);

  useEffect(() => { msgEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs.length, loading]);

  useEffect(() => {
    const el = taRef.current;
    if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 120) + 'px'; }
  }, [input]);

  const nodeOnline = useCallback((id: string): boolean => {
    const n = lmNodes.find(n => n.id === id);
    return n ? n.status === 'online' : false;
  }, [lmNodes]);

  const send = useCallback(async (text: string) => {
    const t = text.trim();
    if (!t || loading) return;
    setMsgs(p => [...p, { id: 'u_' + Date.now(), role: 'user', text: t, ts: Date.now() }]);
    setInput('');
    setLoading(true);
    try {
      const eng = ENGINES.find(e => e.id === engine);
      if (connected) {
        // Primary: WebSocket via backend 9742
        const resp = await request('chat', 'send_message', { text: t, agent: eng?.agent || 'main' });
        const d = resp.payload || {};
        const agentMsg = d.agent_message || {};
        const respText = agentMsg.content || d.text || d.response || '';
        setMsgs(p => [...p, {
          id: 'b_' + Date.now(), role: 'bot',
          text: respText || '(pas de reponse)',
          agent: agentMsg.agent || d.agent || '',
          model: d.model || agentMsg.task_type || '',
          latency: agentMsg.elapsed ? Math.round(agentMsg.elapsed * 1000) : undefined,
          ts: Date.now(),
        }]);
      } else {
        // Fallback: direct REST to backend
        const r = await fetch(BACKEND_URL + '/health', { signal: AbortSignal.timeout(3000) });
        if (!r.ok) throw new Error('Backend hors ligne');
        setMsgs(p => [...p, { id: 'e_' + Date.now(), role: 'sys', text: 'WebSocket deconnecte — reconnexion en cours...', ts: Date.now() }]);
      }
    } catch (e: any) {
      setMsgs(p => [...p, { id: 'e_' + Date.now(), role: 'sys', text: 'Erreur: ' + e.message, ts: Date.now() }]);
    }
    setLoading(false);
  }, [engine, loading, connected, request]);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input); }
  };

  const toggle = (k: keyof typeof openSec) => setOpenSec(p => ({ ...p, [k]: !p[k] }));
  const onlineCount = useMemo(() => lmNodes.filter(n => n.status === 'online').length, [lmNodes]);
  const totalModels = useMemo(() => lmNodes.reduce((s, n) => s + n.models.filter(m => m.loaded).length, 0), [lmNodes]);

  return (
    <>
      <style>{CSS}</style>
      <div style={ST.root}>
        {/* ═══ SIDEBAR ═══ */}
        <div style={ST.side}>
          <div className="j-side" style={ST.sideScroll}>
            {/* Moteur IA */}
            <div>
              <div style={ST.secHead} onClick={() => toggle('engines')}>
                <span style={ST.secLabel}>Moteur IA</span>
                <span style={ST.secBadge}>{ENGINES.length}</span>
              </div>
              {openSec.engines && ENGINES.map(eng => (
                <button key={eng.id} className="j-eng"
                  style={{ ...ST.engBtn, ...(engine === eng.id ? ST.engActive : {}) }}
                  onClick={() => setEngine(eng.id)}>
                  <span style={ST.engIcon}>{eng.icon}</span>
                  <div style={ST.engInfo}>
                    <span style={ST.engName}>{eng.name}</span>
                    <span style={ST.engDesc}>{eng.desc}</span>
                  </div>
                  <span style={{ ...ST.dot, ...(backendOk ? ST.dotOn : ST.dotOff) }} />
                </button>
              ))}
            </div>

            {/* Outils MCP */}
            <div>
              <div style={ST.secHead} onClick={() => toggle('tools')}>
                <span style={ST.secLabel}>Outils MCP</span>
                <span style={ST.secBadge}>{TOOLS.length}</span>
              </div>
              {openSec.tools && TOOLS.map(tool => (
                <button key={tool.id} className="j-tool" style={ST.toolBtn}
                  onClick={() => { setInput(tool.prefix); taRef.current?.focus(); }}>
                  <span style={{ fontSize: 14, width: 24, textAlign: 'center' } as React.CSSProperties}>{tool.icon}</span>
                  <span>{tool.name}</span>
                </button>
              ))}
            </div>

            {/* Cluster */}
            <div>
              <div style={ST.secHead} onClick={() => toggle('cluster')}>
                <span style={ST.secLabel}>Cluster</span>
                <span style={ST.secBadge}>{CLUSTER_NODES.length}</span>
              </div>
              {openSec.cluster && CLUSTER_NODES.map(cn => {
                const on = nodeOnline(cn.id) || (cn.id === 'OL1' && backendOk);
                return (
                  <div key={cn.id} style={ST.cNode}>
                    <span style={ST.cName}>
                      <span style={{ ...ST.dot, ...(on ? ST.dotOn : ST.dotOff) }} />
                      {cn.name}
                    </span>
                    <span style={ST.cLat}>{cn.lat}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* ═══ MAIN ═══ */}
        <div style={ST.main}>
          <div style={ST.bar}>
            <span style={ST.barText}>
              JARVIS v2 {backendOk ? 'en ligne' : 'hors ligne'} — {onlineCount} noeuds · {totalModels} modeles · {TOOLS.length} outils MCP
              {autolearn?.running ? ' · autolearn' : ''}
            </span>
            {autolearn?.running && (
              <span style={ST.learn}><span style={ST.learnDot} /> LEARN</span>
            )}
            {voiceStatus.wakeWord && (
              <span style={{ ...ST.hBadge, backgroundColor: 'rgba(192,132,252,.1)', border: '1px solid rgba(192,132,252,.25)', color: '#c084fc' }}>
                WAKE
              </span>
            )}
            {voiceStatus.lastTranscript && (
              <span style={{ fontSize: 10, color: '#6b7280', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }} title={voiceStatus.lastTranscript}>
                {voiceStatus.lastTranscript.slice(0, 30)}{voiceStatus.lastTranscript.length > 30 ? '...' : ''}
              </span>
            )}
            <span style={{ ...ST.hBadge, ...(backendOk ? ST.hOk : ST.hErr) }}>
              {backendOk ? 'OK' : 'OFF'}
            </span>
          </div>

          <div className="j-msgs" style={ST.msgs}>
            {msgs.length === 0 && !loading ? (
              <div style={ST.empty}>
                <div style={ST.emptyLogo}>JARVIS</div>
                <div style={ST.emptyHint}>
                  {backendOk ? 'Parle a JARVIS pour commencer...' : 'Backend hors ligne — lance python_ws/server.py (port 9742)'}
                </div>
              </div>
            ) : (
              msgs.map(m => (
                <div key={m.id} className="j-msg"
                  style={m.role === 'user' ? ST.userMsg : m.role === 'bot' ? ST.botMsg : ST.sysMsg}>
                  <TextBlock text={m.text} />
                  {m.role === 'bot' && (m.agent || m.model || m.latency) && (
                    <div style={ST.meta}>
                      {m.agent && <span style={{ ...ST.metaTag, backgroundColor: 'rgba(192,132,252,.1)', border: '1px solid rgba(192,132,252,.2)', color: '#c084fc' }}>{m.agent}</span>}
                      {m.model && <span style={{ ...ST.metaTag, backgroundColor: 'rgba(249,115,22,.1)', border: '1px solid rgba(249,115,22,.2)', color: '#f97316' }}>{m.model}</span>}
                      {m.latency != null && m.latency > 0 && <span style={{ ...ST.metaTag, backgroundColor: 'rgba(16,185,129,.1)', border: '1px solid rgba(16,185,129,.2)', color: '#10b981' }}>{m.latency}ms</span>}
                    </div>
                  )}
                </div>
              ))
            )}
            {loading && (
              <div style={ST.loadRow}>
                {[0, .2, .4].map(d => (
                  <span key={d} style={{ ...ST.loadDot, animation: `jDots 1.2s ease-in-out ${d}s infinite` }} />
                ))}
                <span style={{ marginLeft: 4 }}>JARVIS reflechit...</span>
              </div>
            )}
            <div ref={msgEnd} />
          </div>

          <div style={ST.inputWrap}>
            {msgs.length === 0 && (
              <div className="j-chips" style={ST.chips}>
                {CHIPS.map(c => (
                  <button key={c} className="j-chip" style={ST.chip} onClick={() => send(c)}>{c}</button>
                ))}
              </div>
            )}
            <div style={ST.inputRow}>
              <textarea ref={taRef} className="j-input" style={ST.ta}
                value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={handleKey} placeholder="Parle a JARVIS..." rows={1} />
              <button className="j-send"
                style={{ ...ST.send, ...((!input.trim() || loading || !backendOk) ? ST.sendOff : {}) }}
                onClick={() => send(input)} disabled={!input.trim() || loading || !backendOk}>
                {'\u2191'}
              </button>
            </div>
            <div style={ST.bottom}>
              <span>Enter envoyer · Shift+Enter nouvelle ligne</span>
              <span style={{ flex: 1 }} />
              <AgentSelector value={selectedModel} onChange={setSelectedModel} compact />
              <span style={{ color: engine === 'auto' ? '#f97316' : '#6b7280', marginLeft: 8 }}>
                {ENGINES.find(e => e.id === engine)?.name || 'Auto'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
