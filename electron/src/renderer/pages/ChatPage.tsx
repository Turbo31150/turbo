import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useChat } from '../hooks/useChat';
import MessageBubble from '../components/chat/MessageBubble';
import AgentSelector from '../components/AgentSelector';
import { handleFileDrop } from '../lib/file-upload';
import { COLORS, FONT } from '../lib/theme';

const CSS = `
@keyframes cDots{0%,20%{opacity:.2}50%{opacity:1}80%,100%{opacity:.2}}
@keyframes cFadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
@keyframes cPulse{0%,100%{opacity:.6}50%{opacity:1}}
`;

const S = {
  page: { display: 'flex', flexDirection: 'column', height: '100%', fontFamily: FONT } as React.CSSProperties,
  messageList: { flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column' } as React.CSSProperties,
  empty: { flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: COLORS.textDim, fontSize: 13, flexDirection: 'column', gap: 8 } as React.CSSProperties,
  emptyIcon: { fontSize: 32, color: COLORS.border } as React.CSSProperties,
  loadingDots: { display: 'flex', alignItems: 'center', gap: 4, padding: '8px 20px', color: COLORS.textDim, fontSize: 12 } as React.CSSProperties,
  dot: { width: 6, height: 6, borderRadius: '50%', backgroundColor: COLORS.orange } as React.CSSProperties,
  inputArea: { padding: '12px 16px', borderTop: `1px solid ${COLORS.border}`, backgroundColor: COLORS.bgCard } as React.CSSProperties,
  inputRow: { display: 'flex', gap: 8, alignItems: 'flex-end' } as React.CSSProperties,
  textarea: { flex: 1, backgroundColor: COLORS.bgInput, border: `1px solid ${COLORS.border}`, borderRadius: 8, color: COLORS.text, fontFamily: 'inherit', fontSize: 13, padding: '10px 14px', resize: 'none', outline: 'none', maxHeight: 200, lineHeight: 1.4, transition: 'border-color .2s' } as React.CSSProperties,
  sendBtn: { padding: '10px 20px', background: `linear-gradient(135deg, ${COLORS.orange}, ${COLORS.orangeDark})`, color: '#fff', border: 'none', borderRadius: 8, fontWeight: 700, fontFamily: 'inherit', fontSize: 12, cursor: 'pointer', letterSpacing: 1, textTransform: 'uppercase', transition: 'opacity .2s', flexShrink: 0, height: 40 } as React.CSSProperties,
  clearBtn: { padding: '10px 14px', backgroundColor: 'transparent', color: COLORS.textDim, border: `1px solid ${COLORS.border}`, borderRadius: 8, fontFamily: 'inherit', fontSize: 11, cursor: 'pointer', transition: 'all .2s', flexShrink: 0, height: 40 } as React.CSSProperties,
  dropZone: { border: `2px dashed ${COLORS.border}`, borderRadius: 8, padding: 8, marginTop: 8, textAlign: 'center', fontSize: 11, color: COLORS.textDim, transition: 'border-color .2s, background-color .2s' } as React.CSSProperties,
  dropActive: { borderColor: COLORS.orange, backgroundColor: COLORS.orangeAlpha(0.05), color: COLORS.orange },
  fileChips: { display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 } as React.CSSProperties,
  fileChip: { display: 'flex', alignItems: 'center', gap: 4, padding: '2px 8px', backgroundColor: COLORS.border, borderRadius: 4, fontSize: 10, color: COLORS.text } as React.CSSProperties,
  fileRemove: { background: 'none', border: 'none', color: COLORS.red, cursor: 'pointer', padding: 0, fontSize: 12, fontFamily: 'inherit' } as React.CSSProperties,
  hint: { fontSize: 10, color: COLORS.textDim, marginTop: 4, textAlign: 'right' } as React.CSSProperties,
  consensusBtn: { padding: '10px 16px', background: `linear-gradient(135deg, ${COLORS.pink}, ${COLORS.pinkDark})`, color: '#fff', border: 'none', borderRadius: 8, fontWeight: 700, fontFamily: 'inherit', fontSize: 11, cursor: 'pointer', letterSpacing: .5, textTransform: 'uppercase', transition: 'opacity .2s', flexShrink: 0, height: 40 } as React.CSSProperties,
  consensusProgress: { display: 'flex', alignItems: 'center', gap: 6, padding: '4px 12px', fontSize: 11, color: COLORS.pink, animation: 'cPulse 1.5s ease-in-out infinite' } as React.CSSProperties,
};

export default function ChatPage() {
  const { messages, loading, sendMessage, clearConversation, exportConversation } = useChat();
  const [input, setInput] = useState('');
  const [focused, setFocused] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [selectedAgent, setSelectedAgent] = useState('');
  const messageEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isConsensusInput = input.trimStart().toLowerCase().startsWith('/consensus');

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
    sendMessage(trimmed, { files: files.length > 0 ? files : undefined, agent: selectedAgent || undefined });
    setInput('');
    setFiles([]);
  }, [input, loading, sendMessage, files, selectedAgent]);

  const handleConsensus = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;
    const text = trimmed.toLowerCase().startsWith('/consensus ') ? trimmed : `/consensus ${trimmed}`;
    sendMessage(text, { agent: selectedAgent || undefined });
    setInput('');
    setFiles([]);
  }, [input, loading, sendMessage, selectedAgent]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); handleSend(); }
  };

  // Detect if last message was a consensus request (for progress indicator)
  const lastUserMsg = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') return messages[i];
    }
    return undefined;
  }, [messages]);
  const isConsensusLoading = loading && lastUserMsg?.content.toLowerCase().startsWith('/consensus');

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
            isConsensusLoading ? (
              <div role="status" aria-label="Consensus en cours" style={S.consensusProgress}>
                <div style={{ ...S.dot, backgroundColor: COLORS.pink, animation: 'cDots 1.2s ease-in-out infinite' }} />
                <div style={{ ...S.dot, backgroundColor: COLORS.pink, animation: 'cDots 1.2s ease-in-out .2s infinite' }} />
                <div style={{ ...S.dot, backgroundColor: COLORS.pink, animation: 'cDots 1.2s ease-in-out .4s infinite' }} />
                <span style={{ marginLeft: 4 }}>Consensus MAO — 7 agents en parallele...</span>
              </div>
            ) : (
              <div role="status" aria-label="Traitement en cours" style={S.loadingDots}>
                <div style={{ ...S.dot, animation: 'cDots 1.2s ease-in-out infinite' }} />
                <div style={{ ...S.dot, animation: 'cDots 1.2s ease-in-out .2s infinite' }} />
                <div style={{ ...S.dot, animation: 'cDots 1.2s ease-in-out .4s infinite' }} />
                <span style={{ marginLeft: 6 }}>Agent en cours de traitement...</span>
              </div>
            )
          )}
          <div ref={messageEndRef} />
        </div>

        <div style={S.inputArea}>
          <div style={S.inputRow}>
            <textarea
              ref={textareaRef}
              style={{
                ...S.textarea,
                ...(focused ? { borderColor: isConsensusInput ? COLORS.pink : COLORS.orange } : {}),
                ...(isConsensusInput ? { borderColor: COLORS.pink, boxShadow: `0 0 0 1px ${COLORS.pinkAlpha(0.2)}` } : {}),
              }}
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
            <button
              style={{ ...S.consensusBtn, ...(!input.trim() || loading ? { opacity: .4, cursor: 'not-allowed' } : {}) }}
              onClick={handleConsensus}
              disabled={!input.trim() || loading}
              title="Envoyer en mode consensus (7 agents MAO)"
            >
              Consensus
            </button>
            {messages.length > 0 && (
              <>
                <button style={{ ...S.clearBtn, color: COLORS.blue, borderColor: COLORS.border }}
                  onClick={exportConversation}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = COLORS.blue; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = COLORS.border; }}>
                  Export
                </button>
                <button style={S.clearBtn} onClick={clearConversation}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = COLORS.red; e.currentTarget.style.color = COLORS.red; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = COLORS.border; e.currentTarget.style.color = COLORS.textDim; }}>
                  Effacer
                </button>
              </>
            )}
          </div>

          <div
            style={{ ...S.dropZone, ...(dragging ? S.dropActive : {}) }}
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={async e => {
              e.preventDefault(); setDragging(false);
              const accepted = await handleFileDrop(e.dataTransfer.files);
              if (accepted.length > 0) {
                const acceptedKeys = new Set(accepted.map(f => `${f.name}:${f.size}`));
                const newFiles = Array.from(e.dataTransfer.files).filter(f => acceptedKeys.has(`${f.name}:${f.size}`));
                setFiles(prev => [...prev, ...newFiles]);
              }
            }}>
            {dragging ? 'Deposer les fichiers ici...' : 'Glisser-deposer des fichiers'}
          </div>

          {files.length > 0 && (
            <div style={S.fileChips}>
              {files.map((file, i) => (
                <div key={`${file.name}_${file.size}_${i}`} style={S.fileChip}>
                  <span>{file.name}</span>
                  <button style={S.fileRemove} onClick={() => setFiles(prev => prev.filter((_, j) => j !== i))} aria-label={`Retirer ${file.name}`}>{'\u2715'}</button>
                </div>
              ))}
            </div>
          )}

          <div style={{ ...S.hint, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <AgentSelector compact value={selectedAgent} onChange={setSelectedAgent} />
            <span style={{ display: 'flex', gap: 12 }}>
              {input.length > 0 && <span style={{ color: input.length > 3000 ? COLORS.red : input.length > 2000 ? COLORS.orange : COLORS.textDimmer }}>~{Math.ceil(input.length / 4)} tokens</span>}
              {messages.length > 0 && <span style={{ color: COLORS.textDimmer }}>{messages.length} msgs</span>}
              <span>Ctrl+Enter pour envoyer</span>
            </span>
          </div>
        </div>
      </div>
    </>
  );
}
