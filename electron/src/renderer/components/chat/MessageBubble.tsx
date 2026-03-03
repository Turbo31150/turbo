import React, { useState, memo, useMemo } from 'react';
import AgentBadge from './AgentBadge';
import { ChatMessage, ToolCall } from '../../hooks/useChat';
import { COLORS, FONT, NODE_COLORS } from '../../lib/theme';

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
  wrapper: { display: 'flex', marginBottom: 12, fontFamily: FONT } as React.CSSProperties,
  wrapperUser: { justifyContent: 'flex-end' } as React.CSSProperties,
  wrapperAgent: { justifyContent: 'flex-start' } as React.CSSProperties,
  bubble: { maxWidth: '75%', padding: '10px 14px', borderRadius: 8, fontSize: 13, lineHeight: 1.5, color: COLORS.text, wordBreak: 'break-word' } as React.CSSProperties,
  bubbleUser: { backgroundColor: COLORS.border, borderBottomRightRadius: 2 },
  bubbleAssistant: { backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderBottomLeftRadius: 2 },
  bubbleSystem: { backgroundColor: COLORS.bg, border: `1px solid ${COLORS.border}`, borderRadius: 6, maxWidth: '90%', color: COLORS.orange, fontSize: 12 },
  agentHeader: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 } as React.CSSProperties,
  content: { whiteSpace: 'pre-wrap' } as React.CSSProperties,
  timestamp: { fontSize: 10, color: COLORS.textDim, marginTop: 6, textAlign: 'right' } as React.CSSProperties,
  toolSection: { marginTop: 8, borderTop: `1px solid ${COLORS.border}`, paddingTop: 6 } as React.CSSProperties,
  toolToggle: { display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: COLORS.textDim, cursor: 'pointer', background: 'none', border: 'none', padding: 0, fontFamily: 'inherit' } as React.CSSProperties,
  toolItem: { marginTop: 4, padding: '6px 8px', backgroundColor: COLORS.bg, borderRadius: 4, border: `1px solid ${COLORS.border}` } as React.CSSProperties,
  toolHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 } as React.CSSProperties,
  toolName: { fontSize: 10, color: COLORS.orange, fontWeight: 700 } as React.CSSProperties,
  toolStatus: { fontSize: 9, padding: '1px 5px', borderRadius: 3, fontWeight: 700, textTransform: 'uppercase', letterSpacing: .5 } as React.CSSProperties,
  toolResult: { fontSize: 10, color: COLORS.textDim, whiteSpace: 'pre-wrap', maxHeight: 80, overflow: 'auto', marginTop: 4 } as React.CSSProperties,
  metaBar: { display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, flexWrap: 'wrap' } as React.CSSProperties,
  metaTag: (color: string) => ({
    display: 'inline-flex', alignItems: 'center', fontSize: 9, fontWeight: 700, padding: '1px 7px',
    borderRadius: 10, color, backgroundColor: `${color}18`, border: `1px solid ${color}33`,
    letterSpacing: .4, textTransform: 'uppercase' as const, whiteSpace: 'nowrap' as const,
  }),
  metaElapsed: { fontSize: 9, color: COLORS.textDim, fontStyle: 'italic' } as React.CSSProperties,
  consensusHeader: { fontSize: 12, fontWeight: 700, color: COLORS.pink, marginBottom: 8, padding: '4px 0', borderBottom: `1px solid ${COLORS.pinkAlpha(0.2)}` } as React.CSSProperties,
  consensusBlock: { marginBottom: 8, borderRadius: 6, border: `1px solid ${COLORS.border}`, overflow: 'hidden' } as React.CSSProperties,
  consensusBlockHead: { display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', cursor: 'pointer', backgroundColor: COLORS.bg, fontSize: 11, fontWeight: 600 } as React.CSSProperties,
  consensusBlockBody: { padding: '8px 10px', fontSize: 12, lineHeight: 1.5, color: COLORS.text, whiteSpace: 'pre-wrap', borderTop: `1px solid ${COLORS.border}` } as React.CSSProperties,
  consensusMeta: { fontSize: 9, color: COLORS.textDim, marginLeft: 'auto' } as React.CSSProperties,
  consensusFooter: { fontSize: 10, color: COLORS.amber, marginTop: 6, fontStyle: 'italic' } as React.CSSProperties,
};

function getToolStatusStyle(status: ToolCall['status']): React.CSSProperties {
  switch (status) {
    case 'pending': return { color: COLORS.textDim, backgroundColor: COLORS.border };
    case 'running': return { color: COLORS.orange, backgroundColor: COLORS.orangeAlpha(0.15) };
    case 'complete': return { color: COLORS.green, backgroundColor: COLORS.greenAlpha(0.15) };
    case 'error': return { color: COLORS.red, backgroundColor: COLORS.redAlpha(0.15) };
    default: return { color: COLORS.textDim, backgroundColor: COLORS.border };
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
        const color = NODE_COLORS[entry.name] || COLORS.textDim;
        const isOpen = expanded[i] ?? (i === 0);
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

const SNIPER_COLORS = { LONG: COLORS.green, SHORT: COLORS.red };

function SniperRenderer({ content }: { content: string }) {
  const parsed = useMemo(() => parseSniperContent(content), [content]);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  if (!parsed) return <div style={S.content}>{content}</div>;

  const toggle = (i: number) => setExpanded(prev => ({ ...prev, [i]: !prev[i] }));

  return (
    <div>
      <div style={SS.header}>{parsed.header.replace(/\*\*/g, '')}</div>
      {parsed.signals.map((sig, i) => {
        const color = SNIPER_COLORS[sig.direction as keyof typeof SNIPER_COLORS] || COLORS.textDim;
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
  header: { fontSize: 12, fontWeight: 700, color: COLORS.amber, marginBottom: 8, padding: '4px 0', borderBottom: `1px solid ${COLORS.orangeAlpha(0.2)}` } as React.CSSProperties,
  block: { marginBottom: 8, borderRadius: 6, border: `1px solid ${COLORS.border}`, overflow: 'hidden' } as React.CSSProperties,
  blockHead: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', cursor: 'pointer', backgroundColor: COLORS.bg, fontSize: 11, fontWeight: 600 } as React.CSSProperties,
  blockBody: { padding: '8px 10px', fontSize: 11, lineHeight: 1.6, color: COLORS.text, borderTop: `1px solid ${COLORS.border}` } as React.CSSProperties,
  score: { fontSize: 10, color: COLORS.amber, fontWeight: 700 } as React.CSSProperties,
  rr: { fontSize: 10, color: COLORS.textDim, marginLeft: 'auto', fontStyle: 'italic' } as React.CSSProperties,
  priceLine: { color: COLORS.text, fontWeight: 600, fontFamily: FONT } as React.CSSProperties,
  detailLine: { color: COLORS.textDim, fontSize: 10 } as React.CSSProperties,
};

export default memo(function MessageBubble({ message }: MessageBubbleProps) {
  const [toolsExpanded, setToolsExpanded] = useState(false);
  const hasToolCalls = message.toolCalls && message.toolCalls.length > 0;
  const nodeColor = message.nodeTag ? (NODE_COLORS[message.nodeTag] || COLORS.textDim) : null;

  return (
    <div style={{ ...S.wrapper, ...(message.role === 'user' ? S.wrapperUser : S.wrapperAgent) }}>
      <div style={{
        ...S.bubble, ...getBubbleStyle(message.role),
        ...(message.isConsensus ? { borderColor: COLORS.pinkAlpha(0.3), borderWidth: 1 } : {}),
      }}>
        {message.role === 'assistant' && (
          <>
            {message.agent && (
              <div style={S.agentHeader}><AgentBadge agent={message.agent} /></div>
            )}
            {(message.nodeTag || message.taskType || message.elapsed != null) && (
              <div style={S.metaBar}>
                {message.nodeTag && nodeColor && (
                  <span style={S.metaTag(nodeColor)}>{message.nodeTag}</span>
                )}
                {message.taskType && message.taskType !== 'simple' && (
                  <span style={S.metaTag(COLORS.textDim)}>{message.taskType}</span>
                )}
                {message.elapsed != null && (
                  <span style={S.metaElapsed}>{message.elapsed}s</span>
                )}
              </div>
            )}
          </>
        )}

        {message.role === 'system' && (
          <div style={{ fontSize: 9, color: COLORS.orange, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>SYSTEM</div>
        )}

        {message.isConsensus ? (
          <ConsensusRenderer content={message.content ?? ''} />
        ) : (message.content ?? '').includes('**SCAN SNIPER**') ? (
          <SniperRenderer content={message.content ?? ''} />
        ) : (
          <div style={S.content}>{message.content ?? ''}</div>
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
