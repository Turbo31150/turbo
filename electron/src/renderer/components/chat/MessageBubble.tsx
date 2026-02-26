import React, { useState } from 'react';
import AgentBadge from './AgentBadge';
import { ChatMessage, ToolCall } from '../../hooks/useChat';

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

export default function MessageBubble({ message }: MessageBubbleProps) {
  const [toolsExpanded, setToolsExpanded] = useState(false);
  const hasToolCalls = message.toolCalls && message.toolCalls.length > 0;

  return (
    <div style={{ ...S.wrapper, ...(message.role === 'user' ? S.wrapperUser : S.wrapperAgent) }}>
      <div style={{ ...S.bubble, ...getBubbleStyle(message.role) }}>
        {message.role === 'assistant' && message.agent && (
          <div style={S.agentHeader}><AgentBadge agent={message.agent} /></div>
        )}

        {message.role === 'system' && (
          <div style={{ fontSize: 9, color: '#f97316', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>SYSTEM</div>
        )}

        <div style={S.content}>{message.content}</div>

        {hasToolCalls && (
          <div style={S.toolSection}>
            <button style={S.toolToggle} onClick={() => setToolsExpanded(!toolsExpanded)}>
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
}
