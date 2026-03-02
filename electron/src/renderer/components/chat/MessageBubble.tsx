import React, { useState, memo, useMemo } from 'react';
import AgentBadge from './AgentBadge';
import { ChatMessage, ToolCall } from '../../hooks/useChat';

// Node tag colors (MAO cluster agents)
const NODE_COLORS: Record<string, string> = {
  'M1': '#38bdf8',
  'M2': '#a78bfa',
  'M3': '#fb923c',
  'OL1': '#34d399',
  'GPT-OSS': '#f43f5e',
  'DEVSTRAL-2': '#8b5cf6',
  'DEVSTRAL': '#8b5cf6',
  'GLM-4': '#facc15',
  'GLM': '#facc15',
  'MINIMAX': '#06b6d4',
  'MINIMAX-M2': '#06b6d4',
  'GEMINI': '#facc15',
  'CLAUDE': '#c084fc',
  'QWEN3': '#38bdf8',
};

interface ConsensusEntry {
  name: string;
  weight: string;
  latency: string;
  content: string;
}

function parseConsensusContent(text: string): { header: string; entries: ConsensusEntry[]; footer: string } | null {
  if (!text.includes('**CONSENSUS MAO**')) return null;
  const sections = text.split('\n---\n');
  if (sections.length < 2) return null;

  const header = sections[0].trim();
  const entries: ConsensusEntry[] = [];
  let footer = '';

  for (let i = 1; i < sections.length; i++) {
    const s = sections[i].trim();
    // Match: **[AGENT_NAME]** (w=X, Ys):\ncontent
    const m = s.match(/^\*\*\[([^\]]+)\]\*\*\s*\(w=([^,]+),\s*([^)]+)\):\n([\s\S]*)$/);
    if (m) {
      entries.push({ name: m[1], weight: m[2], latency: m[3], content: m[4].trim() });
    } else if (s.startsWith('_') && s.endsWith('_')) {
      footer = s.slice(1, -1);
    }
  }
  return entries.length > 0 ? { header, entries, footer } : null;
}

interface MessageBubbleProps {
  message: ChatMessage;
}

const S = {
  wrapper: { display: 'flex', marginBottom: 12, fontFamily: 'Consolas, "Courier New", monospace' } as React.CSSProperties,
  wrapperUser: { justifyContent: 'flex-end' } as React.CSSProperties,
  wrapperAgent: { justifyContent: 'flex-start' } as React.CSSProperties,
  bubble: { maxWidth: '75%', padding: '10px 14px', borderRadius: 8, fontSize: 13, lineHeight: 1.5, color: '#e0e0e0', wordBreak: 'break-word' } as React.CSSProperties,
  bubbleUser: { backgroundColor: '#1a2a3a', borderBottomRightRadius: 2 },
  bubbleAssistant: { backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderBottomLeftRadius: 2 },
  bubbleSystem: { backgroundColor: '#0a0e14', border: '1px solid #2a3a4a', borderRadius: 6, maxWidth: '90%', color: '#f97316', fontSize: 12 },
  agentHeader: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 } as React.CSSProperties,
  content: { whiteSpace: 'pre-wrap' } as React.CSSProperties,
  timestamp: { fontSize: 10, color: '#6b7280', marginTop: 6, textAlign: 'right' } as React.CSSProperties,
  toolSection: { marginTop: 8, borderTop: '1px solid #1a2a3a', paddingTop: 6 } as React.CSSProperties,
  toolToggle: { display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: '#6b7280', cursor: 'pointer', background: 'none', border: 'none', padding: 0, fontFamily: 'inherit' } as React.CSSProperties,
  toolItem: { marginTop: 4, padding: '6px 8px', backgroundColor: '#0a0e14', borderRadius: 4, border: '1px solid #1a2a3a' } as React.CSSProperties,
  toolHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 } as React.CSSProperties,
  toolName: { fontSize: 10, color: '#f97316', fontWeight: 700 } as React.CSSProperties,
  toolStatus: { fontSize: 9, padding: '1px 5px', borderRadius: 3, fontWeight: 700, textTransform: 'uppercase', letterSpacing: .5 } as React.CSSProperties,
  toolResult: { fontSize: 10, color: '#6b7280', whiteSpace: 'pre-wrap', maxHeight: 80, overflow: 'auto', marginTop: 4 } as React.CSSProperties,
  metaBar: { display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, flexWrap: 'wrap' } as React.CSSProperties,
  metaTag: (color: string) => ({
    display: 'inline-flex', alignItems: 'center', fontSize: 9, fontWeight: 700, padding: '1px 7px',
    borderRadius: 10, color, backgroundColor: `${color}18`, border: `1px solid ${color}33`,
    letterSpacing: .4, textTransform: 'uppercase' as const, whiteSpace: 'nowrap' as const,
  }),
  metaElapsed: { fontSize: 9, color: '#6b7280', fontStyle: 'italic' } as React.CSSProperties,
  consensusHeader: { fontSize: 12, fontWeight: 700, color: '#ec4899', marginBottom: 8, padding: '4px 0', borderBottom: '1px solid rgba(236,72,153,.2)' } as React.CSSProperties,
  consensusBlock: { marginBottom: 8, borderRadius: 6, border: '1px solid #1a2a3a', overflow: 'hidden' } as React.CSSProperties,
  consensusBlockHead: { display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', cursor: 'pointer', backgroundColor: '#0a0e14', fontSize: 11, fontWeight: 600 } as React.CSSProperties,
  consensusBlockBody: { padding: '8px 10px', fontSize: 12, lineHeight: 1.5, color: '#d1d5db', whiteSpace: 'pre-wrap', borderTop: '1px solid #1a2a3a' } as React.CSSProperties,
  consensusMeta: { fontSize: 9, color: '#6b7280', marginLeft: 'auto' } as React.CSSProperties,
  consensusFooter: { fontSize: 10, color: '#f59e0b', marginTop: 6, fontStyle: 'italic' } as React.CSSProperties,
};

function getToolStatusStyle(status: ToolCall['status']): React.CSSProperties {
  switch (status) {
    case 'pending': return { color: '#6b7280', backgroundColor: '#1a2a3a' };
    case 'running': return { color: '#f97316', backgroundColor: 'rgba(249,115,22,.15)' };
    case 'complete': return { color: '#10b981', backgroundColor: 'rgba(16,185,129,.15)' };
    case 'error': return { color: '#ef4444', backgroundColor: 'rgba(239,68,68,.15)' };
    default: return { color: '#6b7280', backgroundColor: '#1a2a3a' };
  }
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function getBubbleStyle(role: ChatMessage['role']) {
  switch (role) {
    case 'user': return S.bubbleUser;
    case 'assistant': return S.bubbleAssistant;
    case 'system': return S.bubbleSystem;
    default: return S.bubbleAssistant;
  }
}

function ConsensusRenderer({ content }: { content: string }) {
  const parsed = useMemo(() => parseConsensusContent(content), [content]);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  if (!parsed) return <div style={S.content}>{content}</div>;

  const toggle = (i: number) => setExpanded(prev => ({ ...prev, [i]: !prev[i] }));

  return (
    <div>
      <div style={S.consensusHeader}>{parsed.header.replace(/\*\*/g, '')}</div>
      {parsed.entries.map((entry, i) => {
        const color = NODE_COLORS[entry.name] || '#6b7280';
        const isOpen = expanded[i] ?? (i === 0); // first entry open by default
        return (
          <div key={i} style={S.consensusBlock}>
            <div style={S.consensusBlockHead} onClick={() => toggle(i)}>
              <span>{isOpen ? '\u25BC' : '\u25B6'}</span>
              <span style={S.metaTag(color)}>{entry.name}</span>
              <span style={S.consensusMeta}>w={entry.weight} &middot; {entry.latency}</span>
            </div>
            {isOpen && <div style={S.consensusBlockBody}>{entry.content}</div>}
          </div>
        );
      })}
      {parsed.footer && <div style={S.consensusFooter}>{parsed.footer}</div>}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// SNIPER RENDERER — Scan Sniper structured signal cards
// ═══════════════════════════════════════════════════════════════════════════

interface SniperSignal {
  symbol: string;
  direction: string;
  score: string;
  rr: string;
  lines: string[];
}

function parseSniperContent(text: string): { header: string; signals: SniperSignal[] } | null {
  if (!text.includes('**SCAN SNIPER**')) return null;
  const sections = text.split('\n---\n');
  if (sections.length < 2) return null;

  const header = sections[0].trim();
  const signals: SniperSignal[] = [];

  for (let i = 1; i < sections.length; i++) {
    const s = sections[i].trim();
    const lines = s.split('\n');
    // First line: SIGNAL:SYMBOL:DIRECTION:SCORE:R:R
    const m = lines[0]?.match(/^SIGNAL:([^:]+):([^:]+):(\d+):(.+)$/);
    if (m) {
      signals.push({
        symbol: m[1],
        direction: m[2],
        score: m[3],
        rr: m[4],
        lines: lines.slice(1),
      });
    }
  }
  return signals.length > 0 ? { header, signals } : null;
}

const SNIPER_COLORS = { LONG: '#10b981', SHORT: '#ef4444' };

function SniperRenderer({ content }: { content: string }) {
  const parsed = useMemo(() => parseSniperContent(content), [content]);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  if (!parsed) return <div style={S.content}>{content}</div>;

  const toggle = (i: number) => setExpanded(prev => ({ ...prev, [i]: !prev[i] }));

  return (
    <div>
      <div style={SS.header}>{parsed.header.replace(/\*\*/g, '')}</div>
      {parsed.signals.map((sig, i) => {
        const color = SNIPER_COLORS[sig.direction as keyof typeof SNIPER_COLORS] || '#6b7280';
        const isOpen = expanded[i] ?? (i === 0);
        const arrow = sig.direction === 'LONG' ? '\u2B06' : '\u2B07';
        return (
          <div key={i} style={{ ...SS.block, borderColor: `${color}44` }}>
            <div style={SS.blockHead} onClick={() => toggle(i)}>
              <span>{isOpen ? '\u25BC' : '\u25B6'}</span>
              <span style={{ color, fontWeight: 700, fontSize: 12 }}>{arrow} {sig.symbol}</span>
              <span style={S.metaTag(color)}>{sig.direction}</span>
              <span style={SS.score}>{sig.score}/100</span>
              <span style={SS.rr}>R:R {sig.rr}</span>
            </div>
            {isOpen && (
              <div style={SS.blockBody}>
                {sig.lines.map((line, j) => (
                  <div key={j} style={line.startsWith('Entry') || line.startsWith('TP') || line.startsWith('SL') ? SS.priceLine : SS.detailLine}>
                    {line}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

const SS = {
  header: { fontSize: 12, fontWeight: 700, color: '#f59e0b', marginBottom: 8, padding: '4px 0', borderBottom: '1px solid rgba(245,158,11,.2)' } as React.CSSProperties,
  block: { marginBottom: 8, borderRadius: 6, border: '1px solid #1a2a3a', overflow: 'hidden' } as React.CSSProperties,
  blockHead: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', cursor: 'pointer', backgroundColor: '#0a0e14', fontSize: 11, fontWeight: 600 } as React.CSSProperties,
  blockBody: { padding: '8px 10px', fontSize: 11, lineHeight: 1.6, color: '#d1d5db', borderTop: '1px solid #1a2a3a' } as React.CSSProperties,
  score: { fontSize: 10, color: '#f59e0b', fontWeight: 700 } as React.CSSProperties,
  rr: { fontSize: 10, color: '#6b7280', marginLeft: 'auto', fontStyle: 'italic' } as React.CSSProperties,
  priceLine: { color: '#e0e0e0', fontWeight: 600, fontFamily: 'Consolas, "Courier New", monospace' } as React.CSSProperties,
  detailLine: { color: '#9ca3af', fontSize: 10 } as React.CSSProperties,
};

export default memo(function MessageBubble({ message }: MessageBubbleProps) {
  const [toolsExpanded, setToolsExpanded] = useState(false);
  const hasToolCalls = message.toolCalls && message.toolCalls.length > 0;
  const nodeColor = message.nodeTag ? (NODE_COLORS[message.nodeTag] || '#6b7280') : null;

  return (
    <div style={{ ...S.wrapper, ...(message.role === 'user' ? S.wrapperUser : S.wrapperAgent) }}>
      <div style={{
        ...S.bubble, ...getBubbleStyle(message.role),
        ...(message.isConsensus ? { borderColor: 'rgba(236,72,153,.3)', borderWidth: 1 } : {}),
      }}>
        {message.role === 'assistant' && (
          <>
            {message.agent && (
              <div style={S.agentHeader}><AgentBadge agent={message.agent} /></div>
            )}
            {/* Metadata bar: nodeTag + taskType + elapsed */}
            {(message.nodeTag || message.taskType || message.elapsed != null) && (
              <div style={S.metaBar}>
                {message.nodeTag && nodeColor && (
                  <span style={S.metaTag(nodeColor)}>{message.nodeTag}</span>
                )}
                {message.taskType && message.taskType !== 'simple' && (
                  <span style={S.metaTag('#6b7280')}>{message.taskType}</span>
                )}
                {message.elapsed != null && (
                  <span style={S.metaElapsed}>{message.elapsed}s</span>
                )}
              </div>
            )}
          </>
        )}

        {message.role === 'system' && (
          <div style={{ fontSize: 9, color: '#f97316', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>SYSTEM</div>
        )}

        {message.isConsensus ? (
          <ConsensusRenderer content={message.content} />
        ) : message.content.includes('**SCAN SNIPER**') ? (
          <SniperRenderer content={message.content} />
        ) : (
          <div style={S.content}>{message.content}</div>
        )}

        {hasToolCalls && (
          <div style={S.toolSection}>
            <button style={S.toolToggle} onClick={() => setToolsExpanded(!toolsExpanded)} aria-expanded={toolsExpanded}>
              <span>{toolsExpanded ? '\u25BC' : '\u25B6'}</span>
              <span>{message.toolCalls!.length} tool call{message.toolCalls!.length > 1 ? 's' : ''}</span>
            </button>
            {toolsExpanded && message.toolCalls!.map(tc => (
              <div key={tc.id} style={S.toolItem}>
                <div style={S.toolHeader}>
                  <span style={S.toolName}>{tc.name}</span>
                  <span style={{ ...S.toolStatus, ...getToolStatusStyle(tc.status) }}>{tc.status}</span>
                </div>
                {tc.result && <div style={S.toolResult}>{tc.result}</div>}
              </div>
            ))}
          </div>
        )}

        <div style={S.timestamp}>{formatTime(message.timestamp)}</div>
      </div>
    </div>
  );
});
