import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useChat } from '../hooks/useChat';
import MessageBubble from '../components/chat/MessageBubble';

const loadingKeyframes = `
@keyframes chat-dots {
  0%, 20% { opacity: 0.2; }
  50% { opacity: 1; }
  80%, 100% { opacity: 0.2; }
}
`;

const styles = {
  page: {
    display: 'flex',
    flexDirection: 'column' as const,
    height: '100%',
    fontFamily: 'Consolas, Courier New, monospace',
  },
  messageList: {
    flex: 1,
    overflowY: 'auto' as const,
    padding: '16px 20px',
    display: 'flex',
    flexDirection: 'column' as const,
  },
  emptyState: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#4a6a8a',
    fontSize: 13,
    flexDirection: 'column' as const,
    gap: 8,
  },
  emptyIcon: {
    fontSize: 32,
    color: '#1a2a3a',
  },
  loadingDots: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    padding: '8px 20px',
    color: '#4a6a8a',
    fontSize: 12,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    backgroundColor: '#00d4ff',
  },
  inputArea: {
    padding: '12px 16px',
    borderTop: '1px solid #1a2a3a',
    backgroundColor: '#0d1117',
  },
  inputRow: {
    display: 'flex',
    gap: 8,
    alignItems: 'flex-end',
  },
  textarea: {
    flex: 1,
    backgroundColor: '#0a0e14',
    border: '1px solid #1a2a3a',
    borderRadius: 6,
    color: '#e0e0e0',
    fontFamily: 'Consolas, Courier New, monospace',
    fontSize: 13,
    padding: '10px 14px',
    resize: 'none' as const,
    outline: 'none',
    maxHeight: 200,
    lineHeight: 1.4,
  },
  textareaFocus: {
    borderColor: '#00d4ff',
  },
  sendBtn: {
    padding: '10px 20px',
    backgroundColor: '#00d4ff',
    color: '#0a0e14',
    border: 'none',
    borderRadius: 6,
    fontWeight: 'bold' as const,
    fontFamily: 'Consolas, Courier New, monospace',
    fontSize: 12,
    cursor: 'pointer',
    letterSpacing: 1,
    textTransform: 'uppercase' as const,
    transition: 'opacity 0.2s ease',
    flexShrink: 0,
    height: 40,
  },
  sendBtnDisabled: {
    opacity: 0.4,
    cursor: 'not-allowed' as const,
  },
  clearBtn: {
    padding: '10px 14px',
    backgroundColor: 'transparent',
    color: '#4a6a8a',
    border: '1px solid #1a2a3a',
    borderRadius: 6,
    fontFamily: 'Consolas, Courier New, monospace',
    fontSize: 11,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    flexShrink: 0,
    height: 40,
  },
  dropZone: {
    border: '2px dashed #1a2a3a',
    borderRadius: 6,
    padding: 8,
    marginTop: 8,
    textAlign: 'center' as const,
    fontSize: 11,
    color: '#4a6a8a',
    transition: 'border-color 0.2s ease, background-color 0.2s ease',
  },
  dropZoneActive: {
    borderColor: '#00d4ff',
    backgroundColor: 'rgba(0, 212, 255, 0.05)',
    color: '#00d4ff',
  },
  fileChips: {
    display: 'flex',
    gap: 6,
    flexWrap: 'wrap' as const,
    marginTop: 6,
  },
  fileChip: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    padding: '2px 8px',
    backgroundColor: '#1a2a3a',
    borderRadius: 4,
    fontSize: 10,
    color: '#e0e0e0',
  },
  fileChipRemove: {
    background: 'none',
    border: 'none',
    color: '#ff4444',
    cursor: 'pointer',
    padding: 0,
    fontSize: 12,
    fontFamily: 'Consolas, Courier New, monospace',
  },
  hint: {
    fontSize: 10,
    color: '#4a6a8a',
    marginTop: 4,
    textAlign: 'right' as const,
  },
};

export default function ChatPage() {
  const { messages, loading, sendMessage, clearConversation } = useChat();
  const [input, setInput] = useState('');
  const [focused, setFocused] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const messageEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, loading]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
    }
  }, [input]);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;
    sendMessage(trimmed);
    setInput('');
    setFiles([]);
  }, [input, loading, sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.ctrlKey && e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  };

  const handleDragLeave = () => {
    setDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    setFiles((prev) => [...prev, ...droppedFiles]);
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <>
      <style>{loadingKeyframes}</style>
      <div style={styles.page}>
        {/* Message list */}
        <div style={styles.messageList}>
          {messages.length === 0 ? (
            <div style={styles.emptyState as any}>
              <div style={styles.emptyIcon}>&#x25E8;</div>
              <div>Envoyer une commande pour commencer</div>
            </div>
          ) : (
            messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
          )}

          {/* Loading indicator */}
          {loading && (
            <div style={styles.loadingDots}>
              <div style={{ ...styles.dot, animation: 'chat-dots 1.2s ease-in-out infinite' }} />
              <div style={{ ...styles.dot, animation: 'chat-dots 1.2s ease-in-out 0.2s infinite' }} />
              <div style={{ ...styles.dot, animation: 'chat-dots 1.2s ease-in-out 0.4s infinite' }} />
              <span style={{ marginLeft: 6 }}>Agent en cours de traitement...</span>
            </div>
          )}

          <div ref={messageEndRef} />
        </div>

        {/* Input area */}
        <div style={styles.inputArea}>
          <div style={styles.inputRow}>
            <textarea
              ref={textareaRef}
              style={{
                ...styles.textarea,
                ...(focused ? styles.textareaFocus : {}),
              }}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              placeholder="Envoyer une commande..."
              rows={1}
            />
            <button
              style={{
                ...styles.sendBtn,
                ...((!input.trim() || loading) ? styles.sendBtnDisabled : {}),
              }}
              onClick={handleSend}
              disabled={!input.trim() || loading}
            >
              Envoyer
            </button>
            {messages.length > 0 && (
              <button
                style={styles.clearBtn}
                onClick={clearConversation}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = '#ff4444';
                  e.currentTarget.style.color = '#ff4444';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = '#1a2a3a';
                  e.currentTarget.style.color = '#4a6a8a';
                }}
              >
                Effacer
              </button>
            )}
          </div>

          {/* Drop zone */}
          <div
            style={{
              ...styles.dropZone,
              ...(dragging ? styles.dropZoneActive : {}),
            }}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {dragging ? 'Deposer les fichiers ici...' : 'Glisser-deposer des fichiers'}
          </div>

          {/* File chips */}
          {files.length > 0 && (
            <div style={styles.fileChips}>
              {files.map((file, i) => (
                <div key={i} style={styles.fileChip}>
                  <span>{file.name}</span>
                  <button style={styles.fileChipRemove} onClick={() => removeFile(i)}>
                    &#x2715;
                  </button>
                </div>
              ))}
            </div>
          )}

          <div style={styles.hint as any}>Ctrl+Enter pour envoyer</div>
        </div>
      </div>
    </>
  );
}
