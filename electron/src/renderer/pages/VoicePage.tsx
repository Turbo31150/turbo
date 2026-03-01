import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useVoice } from '../hooks/useVoice';
import { useWebSocket } from '../hooks/useWebSocket';

const CSS = `
@keyframes orbPulse{0%{box-shadow:0 0 0 0 rgba(249,115,22,.4)}70%{box-shadow:0 0 0 25px rgba(249,115,22,0)}100%{box-shadow:0 0 0 0 rgba(249,115,22,0)}}
@keyframes orbGlow{0%,100%{box-shadow:0 0 20px rgba(249,115,22,.3)}50%{box-shadow:0 0 40px rgba(249,115,22,.6)}}
@keyframes ringExpand{0%{transform:scale(1);opacity:.5}100%{transform:scale(2);opacity:0}}
@keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulseDot{0%,80%,100%{opacity:.3}40%{opacity:1}}
.v-entry{animation:fadeIn .3s ease}
`;

const S = {
  page: { display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 24, fontFamily: 'Consolas, "Courier New", monospace', height: '100%', overflow: 'hidden' } as React.CSSProperties,
  title: { fontSize: 18, fontWeight: 700, color: '#e0e0e0', marginBottom: 4 } as React.CSSProperties,
  subtitle: { fontSize: 11, color: '#6b7280', marginBottom: 20 } as React.CSSProperties,
  topRow: { display: 'flex', alignItems: 'center', gap: 24, marginBottom: 20, width: '100%', maxWidth: 650, justifyContent: 'center' } as React.CSSProperties,
  orbWrap: { position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' } as React.CSSProperties,
  orb: { width: 100, height: 100, borderRadius: '50%', border: '3px solid #2a3a4a', backgroundColor: '#0d1117', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', transition: 'all .3s', zIndex: 2, position: 'relative', flexDirection: 'column', gap: 4 } as React.CSSProperties,
  orbActive: { borderColor: '#f97316', animation: 'orbGlow 2s ease infinite' },
  orbIcon: { fontSize: 28 } as React.CSSProperties,
  orbLabel: { fontSize: 9, letterSpacing: 1.5, textTransform: 'uppercase', fontWeight: 700 } as React.CSSProperties,
  ring: { position: 'absolute', width: 100, height: 100, borderRadius: '50%', border: '2px solid #f97316', animation: 'ringExpand 1.5s ease infinite', zIndex: 1 } as React.CSSProperties,
  bars: { display: 'flex', alignItems: 'center', gap: 3, height: 36 } as React.CSSProperties,
  bar: { width: 4, backgroundColor: '#f97316', borderRadius: 2, transition: 'height .1s' } as React.CSSProperties,
  controls: { display: 'flex', gap: 8 } as React.CSSProperties,
  toggle: { padding: '4px 10px', borderRadius: 6, border: '1px solid #2a3a4a', backgroundColor: 'transparent', color: '#6b7280', fontSize: 10, cursor: 'pointer', fontFamily: 'inherit', transition: 'all .2s', textTransform: 'uppercase', letterSpacing: 1 } as React.CSSProperties,
  toggleOn: { borderColor: '#10b981', color: '#10b981', backgroundColor: 'rgba(16,185,129,.08)' },
  inputWrap: { display: 'flex', gap: 8, width: '100%', maxWidth: 650, marginBottom: 12 } as React.CSSProperties,
  textInput: { flex: 1, backgroundColor: '#0a0e14', border: '1px solid #2a3a4a', borderRadius: 8, color: '#e0e0e0', fontFamily: 'inherit', fontSize: 13, padding: '10px 14px', outline: 'none' } as React.CSSProperties,
  sendBtn: { padding: '0 16px', background: 'linear-gradient(135deg,#f97316,#ea580c)', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 700, fontFamily: 'inherit', fontSize: 12, cursor: 'pointer', letterSpacing: 1 } as React.CSSProperties,
  convWrap: { flex: 1, width: '100%', maxWidth: 650, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8, paddingBottom: 8 } as React.CSSProperties,
  msgUser: { alignSelf: 'flex-end', maxWidth: '80%', padding: '8px 14px', borderRadius: '12px 12px 2px 12px', backgroundColor: '#1a2a3a', border: '1px solid #2a3a4a', fontSize: 13, color: '#e0e0e0', lineHeight: 1.5 } as React.CSSProperties,
  msgAssistant: { alignSelf: 'flex-start', maxWidth: '80%', padding: '8px 14px', borderRadius: '12px 12px 12px 2px', backgroundColor: '#0d1117', border: '1px solid #f97316', fontSize: 13, color: '#e0e0e0', lineHeight: 1.5 } as React.CSSProperties,
  msgSystem: { alignSelf: 'center', padding: '4px 12px', borderRadius: 6, backgroundColor: '#1a1a2e', fontSize: 11, color: '#6b7280' } as React.CSSProperties,
  agentTag: { display: 'inline-block', fontSize: 9, color: '#f97316', backgroundColor: 'rgba(249,115,22,.1)', padding: '1px 6px', borderRadius: 4, marginBottom: 4, letterSpacing: .5, textTransform: 'uppercase' } as React.CSSProperties,
  time: { fontSize: 9, color: '#4b5563', marginTop: 4, textAlign: 'right' } as React.CSSProperties,
  thinking: { alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: '12px 12px 12px 2px', backgroundColor: '#0d1117', border: '1px solid #2a3a4a', fontSize: 12, color: '#6b7280' } as React.CSSProperties,
  dot: { width: 6, height: 6, borderRadius: '50%', backgroundColor: '#f97316' } as React.CSSProperties,
  statusBar: { display: 'flex', justifyContent: 'space-between', width: '100%', maxWidth: 650, fontSize: 10, color: '#4b5563', marginBottom: 8 } as React.CSSProperties,
};

interface ConvEntry {
  role: 'user' | 'assistant' | 'system';
  text: string;
  ts: number;
  agent?: string;
}

const AGENT_TAGS = ['[M1] ', '[OL1] ', '[M2] ', '[M3] ', '[GEMINI] ', '[GPT-OSS] ', '[DEVSTRAL-2] ', '[GLM-4] ', '[MINIMAX-M2] ', '[QWEN3] '];

function stripAgentTag(text: string): { clean: string; agent: string } {
  for (const tag of AGENT_TAGS) {
    if (text.startsWith(tag)) {
      return { clean: text.slice(tag.length), agent: tag.slice(1, -2) };
    }
  }
  return { clean: text, agent: '' };
}

export default function VoicePage() {
  const { recording, transcription, audioLevel, startRecording, stopRecording, speak } = useVoice();
  const { connected, request } = useWebSocket();
  const [textInput, setTextInput] = useState('');
  const [conversation, setConversation] = useState<ConvEntry[]>([]);
  const [ttsOn, setTtsOn] = useState(true);
  const [thinking, setThinking] = useState(false);
  const [transcriptions, setTranscriptions] = useState<{ text: string; ts: number }[]>([]);
  const prevTranscription = useRef('');
  const convEndRef = useRef<HTMLDivElement>(null);
  const ttsOnRef = useRef(ttsOn);
  ttsOnRef.current = ttsOn;

  // Auto-scroll
  useEffect(() => {
    convEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation.length, thinking]);

  // Send text to chat IA, get response, TTS it
  const sendToIA = useCallback(async (text: string) => {
    if (!text.trim() || !connected) return;

    setConversation(prev => [...prev, { role: 'user', text, ts: Date.now() }]);
    setThinking(true);

    try {
      const resp = await request('chat', 'send_message', { content: text });
      const payload = resp?.payload || {};
      const agentMsg = payload.agent_message || {};
      const rawText = agentMsg.content || payload.text || payload.response || '';

      if (rawText) {
        const { clean, agent } = stripAgentTag(rawText);
        const agentLabel = agent || agentMsg.agent || payload.task_type || '';

        setConversation(prev => [...prev, {
          role: 'assistant', text: clean, ts: Date.now(), agent: agentLabel,
        }]);

        // TTS the response
        if (ttsOnRef.current && clean.length < 500) {
          speak(clean);
        }
      } else {
        setConversation(prev => [...prev, {
          role: 'system', text: 'Aucune reponse IA', ts: Date.now(),
        }]);
      }
    } catch {
      setConversation(prev => [...prev, {
        role: 'system', text: 'Erreur connexion IA', ts: Date.now(),
      }]);
    } finally {
      setThinking(false);
    }
  }, [connected, request, speak]);

  // Keep ref up to date for useEffect
  const sendToIARef = useRef(sendToIA);
  sendToIARef.current = sendToIA;

  // When PTT transcription arrives → log + send to IA
  useEffect(() => {
    if (transcription && transcription !== prevTranscription.current) {
      prevTranscription.current = transcription;
      setTranscriptions(prev => [{ text: transcription, ts: Date.now() }, ...prev].slice(0, 20));
      sendToIARef.current(transcription);
    }
  }, [transcription]);

  const handleTextSend = () => {
    const text = textInput.trim();
    if (!text || thinking) return;
    setTextInput('');
    sendToIA(text);
  };

  const toggleRec = () => {
    if (recording) stopRecording();
    else startRecording();
  };

  const formatTime = (ts: number) =>
    new Date(ts).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  // Audio level bars
  const barCount = 7;
  const bars = Array.from({ length: barCount }, (_, i) => {
    const center = Math.abs(i - Math.floor(barCount / 2));
    const base = recording ? audioLevel * (1 - center * 0.15) : 0;
    return Math.max(4, base * 36 + Math.random() * (recording ? 6 : 0));
  });

  return (
    <>
      <style>{CSS}</style>
      <div style={S.page}>
        <div style={S.title}>Commande Vocale</div>
        <div style={S.subtitle}>Parler &rarr; Whisper &rarr; IA &rarr; TTS</div>

        {/* Top row: orb + bars + controls */}
        <div style={S.topRow}>
          <div style={S.orbWrap}>
            {recording && <div style={S.ring} />}
            {recording && <div style={{ ...S.ring, animationDelay: '.5s' }} />}
            <div
              style={{ ...S.orb, ...(recording ? S.orbActive : {}), ...(recording ? { animation: 'orbPulse 1.5s ease infinite' } : {}) }}
              onClick={toggleRec}
            >
              <span style={S.orbIcon}>{recording ? '\uD83D\uDD34' : '\uD83C\uDF99'}</span>
              <span style={{ ...S.orbLabel, color: recording ? '#f97316' : '#6b7280' }}>
                {recording ? 'Ecoute...' : 'Push to Talk'}
              </span>
            </div>
          </div>

          <div style={S.bars}>
            {bars.map((h, i) => (
              <div key={i} style={{ ...S.bar, height: h, opacity: recording ? 1 : .3 }} />
            ))}
          </div>

          <div style={S.controls}>
            <button style={{ ...S.toggle, ...(ttsOn ? S.toggleOn : {}) }} onClick={() => setTtsOn(!ttsOn)}>
              TTS: {ttsOn ? 'ON' : 'OFF'}
            </button>
          </div>
        </div>

        {/* Status bar */}
        <div style={S.statusBar}>
          <span>WS: {connected ? '\u2705 connecte' : '\u274C deconnecte'}</span>
          <span>{conversation.length} messages | {transcriptions.length} transcriptions</span>
          <span>Audio: {Math.round(audioLevel * 100)}%</span>
          <span>TTS: {ttsOn ? 'Edge fr-FR' : 'OFF'}</span>
        </div>

        {/* Last transcription */}
        {transcriptions.length > 0 && (
          <div style={{ width: '100%', maxWidth: 650, marginBottom: 8, padding: '6px 12px', borderRadius: 6, backgroundColor: 'rgba(192,132,252,.06)', border: '1px solid rgba(192,132,252,.15)', fontSize: 11, color: '#c084fc', display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1, opacity: 0.7 }}>WHISPER</span>
            <span style={{ flex: 1 }}>{transcriptions[0].text}</span>
            <span style={{ fontSize: 9, color: '#4b5563' }}>
              {new Date(transcriptions[0].ts).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          </div>
        )}

        {/* Conversation log */}
        <div style={S.convWrap}>
          {conversation.length === 0 && !thinking ? (
            <div style={{ textAlign: 'center', color: '#4b5563', fontSize: 12, padding: 40 }}>
              Appuie sur l'orbe pour parler, ou ecris ci-dessous
            </div>
          ) : (
            conversation.map((entry, i) => (
              <div key={i} className="v-entry" style={
                entry.role === 'user' ? S.msgUser :
                entry.role === 'assistant' ? S.msgAssistant : S.msgSystem
              }>
                {entry.role === 'assistant' && entry.agent && (
                  <div style={S.agentTag}>{entry.agent}</div>
                )}
                <div>{entry.text}</div>
                <div style={S.time as React.CSSProperties}>{formatTime(entry.ts)}</div>
              </div>
            ))
          )}

          {thinking && (
            <div style={S.thinking}>
              <div style={{ ...S.dot, animation: 'pulseDot 1.2s ease-in-out infinite' }} />
              <div style={{ ...S.dot, animation: 'pulseDot 1.2s ease-in-out .2s infinite' }} />
              <div style={{ ...S.dot, animation: 'pulseDot 1.2s ease-in-out .4s infinite' }} />
              <span style={{ marginLeft: 4 }}>IA reflechit...</span>
            </div>
          )}
          <div ref={convEndRef} />
        </div>

        {/* Text input → send to IA */}
        <div style={S.inputWrap}>
          <input
            style={S.textInput}
            value={textInput}
            onChange={e => setTextInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleTextSend()}
            placeholder="Ecrire un message (Enter pour envoyer)..."
            disabled={thinking}
          />
          <button
            style={{ ...S.sendBtn, ...(thinking || !textInput.trim() ? { opacity: .4, cursor: 'not-allowed' } : {}) }}
            onClick={handleTextSend}
            disabled={thinking || !textInput.trim()}
          >
            Envoyer
          </button>
        </div>
      </div>
    </>
  );
}
