import React, { useState } from 'react';
import AgentBadge from './AgentBadge';
import { ChatMessage, ToolCall } from '../../hooks/useChat';

interface MessageBubbleProps {
  message: ChatMessage;
}

const styles = {
  wrapper: {
    display: 'flex',
    marginBottom: 12,
    fontFamily: 'Consolas, Courier New, monospace',
  },
  wrapperUser: {
    justifyContent: 'flex-end' as const,
  },
  wrapperAgent: {
    justifyContent: 'flex-start' as const,
  },
  bubble: {
    maxWidth: '75%',
    padding: '10px 14px',
    borderRadius: 8,
    fontSize: 13,
    lineHeight: 1.5,
    color: '#e0e0e0',
    wordBreak: 'break-word' as const,
  },
  bubbleUser: {
    backgroundColor: '#1a2a3a',
    borderBottomRightRadius: 2,
  },
  bubbleAssistant: {
    backgroundColor: '#0d1117',
    border: '1px solid #1a2a3a',
    borderBottomLeftRadius: 2,
  },
  bubbleSystem: {
    backgroundColor: '#0a0e14',
    border: '1px solid #2a3a4a',
    borderRadius: 6,
    maxWidth: '90%',
    color: '#ffaa00',
    fontSize: 12,
  },
  agentHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 6,
  },
  content: {
    whiteSpace: 'pre-wrap' as const,
  },
  timestamp: {
    fontSize: 10,
    color: '#4a6a8a',
    marginTop: 6,
    textAlign: 'right' as const,
  },
  toolCallsSection: {
    marginTop: 8,
    borderTop: '1px solid #1a2a3a',
    paddingTop: 6,
  },
  toolCallToggle: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    fontSize: 10,
    color: '#4a6a8a',
    cursor: 'pointer',
    background: 'none',
    border: 'none',
    padding: 0,
    fontFamily: 'Consolas, Courier New, monospace',
  },
  toolCallItem: {
    marginTop: 4,
    padding: '6px 8px',
    backgroundColor: '#0a0e14',
    borderRadius: 4,
    border: '1px solid #1a2a3a',
  },
  toolCallHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 2,
  },
  toolCallName: {
    fontSize: 10,
    color: '#00d4ff',
    fontWeight: 'bold' as const,
  },
  toolCallStatus: {
    fontSize: 9,
    padding: '1px 5px',
    borderRadius: 3,
    fontWeight: 'bold' as const,
    textTransform: 'uppercase' as const,
    letterSpacing: 0.5,
  },
  toolCallResult: {
    fontSize: 10,
    color: '#4a6a8a',
    whiteSpace: 'pre-wrap' as const,
    maxHeight: 80,
    overflow: 'auto' as const,
    marginTop: 4,
  },
};

function getToolStatusStyle(status: ToolCall['status']): React.CSSProperties {
  switch (status) {
    case 'pending':
      return { color: '#4a6a8a', backgroundColor: '#1a2a3a' };
    case 'running':
      return { color: '#ffaa00', backgroundColor: 'rgba(255, 170, 0, 0.15)' };
    case 'complete':
      return { color: '#00ff88', backgroundColor: 'rgba(0, 255, 136, 0.15)' };
    case 'error':
      return { color: '#ff4444', backgroundColor: 'rgba(255, 68, 68, 0.15)' };
    default:
      return { color: '#4a6a8a', backgroundColor: '#1a2a3a' };
  }
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function getBubbleAlignment(role: ChatMessage['role']) {
  if (role === 'user') return styles.wrapperUser;
  return styles.wrapperAgent;
}

function getBubbleStyle(role: ChatMessage['role']) {
  switch (role) {
    case 'user': return styles.bubbleUser;
    case 'assistant': return styles.bubbleAssistant;
    case 'system': return styles.bubbleSystem;
    default: return styles.bubbleAssistant;
  }
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const [toolsExpanded, setToolsExpanded] = useState(false);
  const isUser = message.role === 'user';
  const hasToolCalls = message.toolCalls && message.toolCalls.length > 0;

  return (
    <div style={{ ...styles.wrapper, ...getBubbleAlignment(message.role) }}>
      <div style={{ ...styles.bubble, ...getBubbleStyle(message.role) }}>
        {/* Agent badge for assistant messages */}
        {message.role === 'assistant' && message.agent && (
          <div style={styles.agentHeader}>
            <AgentBadge agent={message.agent} />
          </div>
        )}

        {/* System label */}
        {message.role === 'system' && (
          <div style={{ fontSize: 9, color: '#ffaa00', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>
            SYSTEM
          </div>
        )}

        {/* Content */}
        <div style={styles.content}>{message.content}</div>

        {/* Tool calls */}
        {hasToolCalls && (
          <div style={styles.toolCallsSection}>
            <button
              style={styles.toolCallToggle}
              onClick={() => setToolsExpanded(!toolsExpanded)}
            >
              <span>{toolsExpanded ? '\u25BC' : '\u25B6'}</span>
              <span>{message.toolCalls!.length} tool call{message.toolCalls!.length > 1 ? 's' : ''}</span>
            </button>
            {toolsExpanded &&
              message.toolCalls!.map((tc) => (
                <div key={tc.id} style={styles.toolCallItem}>
                  <div style={styles.toolCallHeader}>
                    <span style={styles.toolCallName}>{tc.name}</span>
                    <span style={{ ...styles.toolCallStatus, ...getToolStatusStyle(tc.status) }}>
                      {tc.status}
                    </span>
                  </div>
                  {tc.result && (
                    <div style={styles.toolCallResult}>{tc.result}</div>
                  )}
                </div>
              ))}
          </div>
        )}

        {/* Timestamp */}
        <div style={styles.timestamp as any}>{formatTime(message.timestamp)}</div>
      </div>
    </div>
  );
}
