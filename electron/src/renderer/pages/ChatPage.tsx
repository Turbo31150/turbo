import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useChat } from '../hooks/useChat';
import MessageBubble from '../components/chat/MessageBubble';

const CSS = `
@keyframes cDots{0%,20%{opacity:.2}50%{opacity:1}80%,100%{opacity:.2}}
@keyframes cFadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
`;

const S = {
  page: { display: 'flex', flexDirection: 'column', height: '100%', fontFamily: 'Consolas, "Courier New", monospace' } as React.CSSProperties,
  messageList: { flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column' } as React.CSSProperties,
  empty: { flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6b7280', fontSize: 13, flexDirection: 'column', gap: 8 } as React.CSSProperties,
  emptyIcon: { fontSize: 32, color: '#1a2a3a' } as React.CSSProperties,
  loadingDots: { display: 'flex', alignItems: 'center', gap: 4, padding: '8px 20px', color: '#6b7280', fontSize: 12 } as React.CSSProperties,
  dot: { width: 6, height: 6, borderRadius: '50%', backgroundColor: '#f97316' } as React.CSSProperties,
  inputArea: { padding: '12px 16px', borderTop: '1px solid #1a2a3a', backgroundColor: '#0d1117' } as React.CSSProperties,
  inputRow: { display: 'flex', gap: 8, alignItems: 'flex-end' } as React.CSSProperties,
  textarea: { flex: 1, backgroundColor: '#0a0e14', border: '1px solid #1a2a3a', borderRadius: 8, color: '#e0e0e0', fontFamily: 'inherit', fontSize: 13, padding: '10px 14px', resize: 'none', outline: 'none', maxHeight: 200, lineHeight: 1.4, transition: 'border-color .2s' } as React.CSSProperties,
  sendBtn: { padding: '10px 20px', background: 'linear-gradient(135deg, #f97316, #ea580c)', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 700, fontFamily: 'inherit', fontSize: 12, cursor: 'pointer', letterSpacing: 1, textTransform: 'uppercase', transition: 'opacity .2s', flexShrink: 0, height: 40 } as React.CSSProperties,
  clearBtn: { padding: '10px 14px', backgroundColor: 'transparent', color: '#6b7280', border: '1px solid #1a2a3a', borderRadius: 8, fontFamily: 'inherit', fontSize: 11, cursor: 'pointer', transition: 'all .2s', flexShrink: 0, height: 40 } as React.CSSProperties,
  dropZone: { border: '2px dashed #1a2a3a', borderRadius: 8, padding: 8, marginTop: 8, textAlign: 'center', fontSize: 11, color: '#6b7280', transition: 'border-color .2s, background-color .2s' } as React.CSSProperties,
  dropActive: { borderColor: '#f97316', backgroundColor: 'rgba(249,115,22,.05)', color: '#f97316' },
  fileChips: { display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 } as React.CSSProperties,
  fileChip: { display: 'flex', alignItems: 'center', gap: 4, padding: '2px 8px', backgroundColor: '#1a2a3a', borderRadius: 4, fontSize: 10, color: '#e0e0e0' } as React.CSSProperties,
  fileRemove: { background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: 0, fontSize: 12, fontFamily: 'inherit' } as React.CSSProperties,
  hint: { fontSize: 10, color: '#6b7280', marginTop: 4, textAlign: 'right' } as React.CSSProperties,
};

export default function ChatPage() {
  const { messages, loading, sendMessage, clearConversation } = useChat();
  const [input, setInput] = useState('');
  const [focused, setFocused] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const messageEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, loading]);

  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'; }
  }, [input]);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;
    sendMessage(trimmed);
    setInput('');
    setFiles([]);
  }, [input, loading, sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); handleSend(); }
  };

  return (
    <>
      <style>{CSS}</style>
      <div style={S.page}>
        <div style={S.messageList}>
          {messages.length === 0 ? (
            <div style={S.empty}>
              <div style={S.emptyIcon}>{'\u25E8'}</div>
              <div>Envoyer une commande pour commencer</div>
            </div>
          ) : (
            messages.map(msg => <MessageBubble key={msg.id} message={msg} />)
          )}

          {loading && (
            <div style={S.loadingDots}>
              <div style={{ ...S.dot, animation: 'cDots 1.2s ease-in-out infinite' }} />
              <div style={{ ...S.dot, animation: 'cDots 1.2s ease-in-out .2s infinite' }} />
              <div style={{ ...S.dot, animation: 'cDots 1.2s ease-in-out .4s infinite' }} />
              <span style={{ marginLeft: 6 }}>Agent en cours de traitement...</span>
            </div>
          )}
          <div ref={messageEndRef} />
        </div>

        <div style={S.inputArea}>
          <div style={S.inputRow}>
            <textarea
              ref={textareaRef}
              style={{ ...S.textarea, ...(focused ? { borderColor: '#f97316' } : {}) }}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              placeholder="Envoyer une commande..."
              rows={1}
            />
            <button
              style={{ ...S.sendBtn, ...(!input.trim() || loading ? { opacity: .4, cursor: 'not-allowed' } : {}) }}
              onClick={handleSend}
              disabled={!input.trim() || loading}
            >
              Envoyer
            </button>
            {messages.length > 0 && (
              <button style={S.clearBtn} onClick={clearConversation}
                onMouseEnter={e => { e.currentTarget.style.borderColor = '#ef4444'; e.currentTarget.style.color = '#ef4444'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = '#1a2a3a'; e.currentTarget.style.color = '#6b7280'; }}>
                Effacer
              </button>
            )}
          </div>

          <div
            style={{ ...S.dropZone, ...(dragging ? S.dropActive : {}) }}
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => { e.preventDefault(); setDragging(false); setFiles(prev => [...prev, ...Array.from(e.dataTransfer.files)]); }}>
            {dragging ? 'Deposer les fichiers ici...' : 'Glisser-deposer des fichiers'}
          </div>

          {files.length > 0 && (
            <div style={S.fileChips}>
              {files.map((file, i) => (
                <div key={i} style={S.fileChip}>
                  <span>{file.name}</span>
                  <button style={S.fileRemove} onClick={() => setFiles(prev => prev.filter((_, j) => j !== i))}>{'\u2715'}</button>
                </div>
              ))}
            </div>
          )}

          <div style={S.hint}>Ctrl+Enter pour envoyer</div>
        </div>
      </div>
    </>
  );
}
