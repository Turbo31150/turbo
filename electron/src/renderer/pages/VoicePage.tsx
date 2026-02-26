import React, { useState, useRef, useEffect } from 'react';
import { useVoice } from '../hooks/useVoice';

const CSS = `
@keyframes orbPulse{0%{box-shadow:0 0 0 0 rgba(249,115,22,.4)}70%{box-shadow:0 0 0 25px rgba(249,115,22,0)}100%{box-shadow:0 0 0 0 rgba(249,115,22,0)}}
@keyframes orbGlow{0%,100%{box-shadow:0 0 20px rgba(249,115,22,.3)}50%{box-shadow:0 0 40px rgba(249,115,22,.6)}}
@keyframes ringExpand{0%{transform:scale(1);opacity:.5}100%{transform:scale(2);opacity:0}}
@keyframes barBounce{0%,100%{transform:scaleY(.3)}50%{transform:scaleY(1)}}
@keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.v-log-entry{animation:fadeIn .3s ease}
`;

const S = {
  page: { display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 24, fontFamily: 'Consolas, "Courier New", monospace', height: '100%', overflow: 'hidden' } as React.CSSProperties,
  title: { fontSize: 18, fontWeight: 700, color: '#e0e0e0', marginBottom: 4 } as React.CSSProperties,
  subtitle: { fontSize: 11, color: '#6b7280', marginBottom: 30 } as React.CSSProperties,
  orbWrap: { position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 30 } as React.CSSProperties,
  orb: { width: 120, height: 120, borderRadius: '50%', border: '3px solid #2a3a4a', backgroundColor: '#0d1117', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', transition: 'all .3s', zIndex: 2, position: 'relative', flexDirection: 'column', gap: 4 } as React.CSSProperties,
  orbActive: { borderColor: '#f97316', animation: 'orbGlow 2s ease infinite' },
  orbIcon: { fontSize: 32 } as React.CSSProperties,
  orbLabel: { fontSize: 10, letterSpacing: 1.5, textTransform: 'uppercase', fontWeight: 700 } as React.CSSProperties,
  ring: { position: 'absolute', width: 120, height: 120, borderRadius: '50%', border: '2px solid #f97316', animation: 'ringExpand 1.5s ease infinite', zIndex: 1 } as React.CSSProperties,
  bars: { display: 'flex', alignItems: 'center', gap: 3, height: 40, marginBottom: 24 } as React.CSSProperties,
  bar: { width: 4, backgroundColor: '#f97316', borderRadius: 2, transition: 'height .1s' } as React.CSSProperties,
  status: { fontSize: 13, color: '#6b7280', marginBottom: 20 } as React.CSSProperties,
  transcription: { width: '100%', maxWidth: 600, backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 8, padding: 16, minHeight: 60, fontSize: 14, color: '#e0e0e0', lineHeight: 1.6, textAlign: 'center', marginBottom: 20 } as React.CSSProperties,
  ttsWrap: { display: 'flex', gap: 8, width: '100%', maxWidth: 600, marginBottom: 20 } as React.CSSProperties,
  ttsInput: { flex: 1, backgroundColor: '#0a0e14', border: '1px solid #2a3a4a', borderRadius: 8, color: '#e0e0e0', fontFamily: 'inherit', fontSize: 13, padding: '10px 14px', outline: 'none' } as React.CSSProperties,
  ttsBtn: { padding: '0 16px', background: 'linear-gradient(135deg,#c084fc,#9333ea)', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 700, fontFamily: 'inherit', fontSize: 12, cursor: 'pointer' } as React.CSSProperties,
  logWrap: { flex: 1, width: '100%', maxWidth: 600, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 } as React.CSSProperties,
  logEntry: { display: 'flex', justifyContent: 'space-between', padding: '6px 12px', borderRadius: 6, backgroundColor: '#0d1117', border: '1px solid #1a2a3a', fontSize: 12 } as React.CSSProperties,
  logText: { color: '#e0e0e0', flex: 1 } as React.CSSProperties,
  logTime: { color: '#6b7280', fontSize: 10, flexShrink: 0 } as React.CSSProperties,
  controls: { display: 'flex', gap: 12, marginBottom: 20 } as React.CSSProperties,
  toggle: { padding: '4px 12px', borderRadius: 6, border: '1px solid #2a3a4a', backgroundColor: 'transparent', color: '#6b7280', fontSize: 10, cursor: 'pointer', fontFamily: 'inherit', transition: 'all .2s', textTransform: 'uppercase', letterSpacing: 1 } as React.CSSProperties,
  toggleOn: { borderColor: '#10b981', color: '#10b981', backgroundColor: 'rgba(16,185,129,.08)' },
};

interface LogEntry { text: string; ts: number; }

export default function VoicePage() {
  const { recording, transcription, audioLevel, startRecording, stopRecording, speak } = useVoice();
  const [ttsInput, setTtsInput] = useState('');
  const [log, setLog] = useState<LogEntry[]>([]);
  const [ttsOn, setTtsOn] = useState(true);
  const [wakeOn, setWakeOn] = useState(false);
  const prevTranscription = useRef('');

  // Log transcriptions
  useEffect(() => {
    if (transcription && transcription !== prevTranscription.current) {
      setLog(p => [{ text: transcription, ts: Date.now() }, ...p].slice(0, 50));
      prevTranscription.current = transcription;
    }
  }, [transcription]);

  const toggleRec = () => {
    if (recording) stopRecording();
    else startRecording();
  };

  const handleTts = () => {
    if (ttsInput.trim()) { speak(ttsInput.trim()); setTtsInput(''); }
  };

  const formatTime = (ts: number) => new Date(ts).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  // Generate bar heights from audio level
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
        <div style={S.subtitle}>Push-to-talk · Whisper STT · Edge TTS</div>

        {/* Controls */}
        <div style={S.controls}>
          <button style={{ ...S.toggle, ...(wakeOn ? S.toggleOn : {}) }} onClick={() => setWakeOn(!wakeOn)}>
            Wake: {wakeOn ? 'ON' : 'OFF'}
          </button>
          <button style={{ ...S.toggle, ...(ttsOn ? S.toggleOn : {}) }} onClick={() => setTtsOn(!ttsOn)}>
            TTS: {ttsOn ? 'ON' : 'OFF'}
          </button>
        </div>

        {/* PTT Orb */}
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

        {/* Audio bars */}
        <div style={S.bars}>
          {bars.map((h, i) => (
            <div key={i} style={{ ...S.bar, height: h, opacity: recording ? 1 : .3 }} />
          ))}
        </div>

        {/* Transcription */}
        <div style={S.transcription}>
          {transcription || <span style={{ color: '#4b5563' }}>En attente de voix...</span>}
        </div>

        {/* TTS input */}
        <div style={S.ttsWrap}>
          <input style={S.ttsInput} value={ttsInput} onChange={e => setTtsInput(e.target.value)}
            placeholder="Texte a prononcer..." onKeyDown={e => e.key === 'Enter' && handleTts()} />
          <button style={S.ttsBtn} onClick={handleTts}>Parler</button>
        </div>

        {/* Log */}
        <div style={S.logWrap}>
          {log.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#4b5563', fontSize: 12, padding: 20 }}>
              Historique de transcription vide
            </div>
          ) : (
            log.map((entry, i) => (
              <div key={i} className="v-log-entry" style={S.logEntry}>
                <span style={S.logText}>{entry.text}</span>
                <span style={S.logTime}>{formatTime(entry.ts)}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
