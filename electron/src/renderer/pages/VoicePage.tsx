import React, { useState, useRef, useEffect } from 'react';
import { useVoice } from '../hooks/useVoice';
import AudioVisualizer from '../components/voice/AudioVisualizer';
import TranscriptionLog, { TranscriptionEntry } from '../components/voice/TranscriptionLog';

const pulseKeyframes = `
@keyframes ptt-pulse {
  0% { box-shadow: 0 0 0 0 rgba(255, 68, 68, 0.5); }
  70% { box-shadow: 0 0 0 20px rgba(255, 68, 68, 0); }
  100% { box-shadow: 0 0 0 0 rgba(255, 68, 68, 0); }
}
@keyframes ring-expand {
  0% { transform: scale(1); opacity: 0.6; }
  100% { transform: scale(1.8); opacity: 0; }
}
`;

const styles = {
  page: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    padding: 24,
    fontFamily: 'Consolas, Courier New, monospace',
    height: '100%',
    overflowY: 'auto' as const,
  },
  title: {
    fontSize: 18,
    fontWeight: 'bold' as const,
    color: '#e0e0e0',
    marginBottom: 32,
  },
  pttContainer: {
    position: 'relative' as const,
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    marginBottom: 24,
  },
  pttButton: {
    width: 120,
    height: 120,
    borderRadius: '50%',
    border: '3px solid #1a2a3a',
    backgroundColor: '#1a2a3a',
    color: '#4a6a8a',
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    transition: 'all 0.3s ease',
    position: 'relative' as const,
    zIndex: 2,
    outline: 'none',
  },
  pttButtonRecording: {
    border: '3px solid #ff4444',
    backgroundColor: '#1a0808',
    color: '#ff4444',
    animation: 'ptt-pulse 1.5s ease-in-out infinite',
  },
  pttIcon: {
    marginBottom: 4,
  },
  pttLabel: {
    fontSize: 8,
    letterSpacing: 2,
    textTransform: 'uppercase' as const,
    fontFamily: 'Consolas, Courier New, monospace',
    fontWeight: 'bold' as const,
  },
  ring: {
    position: 'absolute' as const,
    top: 0,
    left: 0,
    width: 120,
    height: 120,
    borderRadius: '50%',
    border: '2px solid #ff4444',
    animation: 'ring-expand 1.5s ease-out infinite',
    zIndex: 1,
  },
  statusText: {
    fontSize: 12,
    marginTop: 12,
    letterSpacing: 2,
    textTransform: 'uppercase' as const,
    fontWeight: 'bold' as const,
  },
  visualizerSection: {
    width: '100%',
    maxWidth: 400,
    marginBottom: 32,
  },
  transcriptionPreview: {
    width: '100%',
    maxWidth: 500,
    marginBottom: 20,
    padding: '10px 16px',
    backgroundColor: '#0d1117',
    border: '1px solid #1a2a3a',
    borderRadius: 6,
    fontSize: 13,
    color: '#e0e0e0',
    minHeight: 40,
    textAlign: 'center' as const,
  },
  ttsSection: {
    width: '100%',
    maxWidth: 500,
    marginBottom: 24,
  },
  ttsHeader: {
    fontSize: 12,
    color: '#4a6a8a',
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
    marginBottom: 8,
  },
  ttsRow: {
    display: 'flex',
    gap: 8,
  },
  ttsInput: {
    flex: 1,
    backgroundColor: '#0a0e14',
    border: '1px solid #1a2a3a',
    borderRadius: 4,
    color: '#e0e0e0',
    fontFamily: 'Consolas, Courier New, monospace',
    fontSize: 12,
    padding: '8px 12px',
    outline: 'none',
  },
  ttsBtn: {
    padding: '8px 16px',
    backgroundColor: 'transparent',
    border: '1px solid #00d4ff',
    color: '#00d4ff',
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 'bold' as const,
    cursor: 'pointer',
    fontFamily: 'Consolas, Courier New, monospace',
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
    transition: 'all 0.2s ease',
  },
  transcriptionSection: {
    width: '100%',
    maxWidth: 600,
    backgroundColor: '#0d1117',
    border: '1px solid #1a2a3a',
    borderRadius: 8,
    padding: 16,
  },
};

const MicSvg = ({ size = 32 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="9" y="2" width="6" height="12" rx="3" />
    <path d="M5 10a7 7 0 0 0 14 0" />
    <line x1="12" y1="19" x2="12" y2="22" />
  </svg>
);

export default function VoicePage() {
  const { recording, transcription, audioLevel, startRecording, stopRecording, speak } = useVoice();
  const [ttsText, setTtsText] = useState('');
  // Maintain a log of transcriptions locally
  const [entries, setEntries] = useState<TranscriptionEntry[]>([]);
  const prevTranscriptionRef = useRef('');

  // When transcription changes and recording stops, add to log
  useEffect(() => {
    if (!recording && transcription && transcription !== prevTranscriptionRef.current) {
      setEntries((prev) => [
        ...prev,
        {
          timestamp: Date.now(),
          text: transcription,
        },
      ]);
      prevTranscriptionRef.current = transcription;
    }
  }, [recording, transcription]);

  const handlePttDown = () => {
    if (!recording) startRecording();
  };

  const handlePttUp = () => {
    if (recording) stopRecording();
  };

  const handleSpeak = () => {
    if (ttsText.trim()) {
      speak(ttsText.trim());
      setTtsText('');
    }
  };

  return (
    <>
      <style>{pulseKeyframes}</style>
      <div style={styles.page}>
        <div style={styles.title}>Voice Control</div>

        {/* PTT Button */}
        <div style={styles.pttContainer}>
          {recording && <div style={styles.ring} />}
          {recording && <div style={{ ...styles.ring, animationDelay: '0.5s' }} />}
          <button
            style={{
              ...styles.pttButton,
              ...(recording ? styles.pttButtonRecording : {}),
            }}
            onMouseDown={handlePttDown}
            onMouseUp={handlePttUp}
            onMouseLeave={handlePttUp}
          >
            <span style={styles.pttIcon}>
              <MicSvg />
            </span>
            <span style={styles.pttLabel}>
              {recording ? 'Release' : 'Push'}
            </span>
          </button>
          <span
            style={{
              ...styles.statusText,
              color: recording ? '#ff4444' : '#4a6a8a',
            }}
          >
            {recording ? 'LISTENING...' : 'PUSH TO TALK'}
          </span>
        </div>

        {/* Audio Level */}
        <div style={styles.visualizerSection}>
          <AudioVisualizer level={audioLevel} recording={recording} />
        </div>

        {/* Live transcription preview */}
        {transcription && (
          <div style={styles.transcriptionPreview as any}>
            {transcription}
          </div>
        )}

        {/* TTS Controls */}
        <div style={styles.ttsSection}>
          <div style={styles.ttsHeader}>Text-to-Speech</div>
          <div style={styles.ttsRow}>
            <input
              style={styles.ttsInput}
              value={ttsText}
              onChange={(e) => setTtsText(e.target.value)}
              placeholder="Saisir le texte a prononcer..."
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSpeak();
              }}
            />
            <button
              style={styles.ttsBtn}
              onClick={handleSpeak}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#00d4ff';
                e.currentTarget.style.color = '#0a0e14';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
                e.currentTarget.style.color = '#00d4ff';
              }}
            >
              Speak
            </button>
          </div>
        </div>

        {/* Transcription Log */}
        <div style={styles.transcriptionSection}>
          <TranscriptionLog entries={entries} />
        </div>
      </div>
    </>
  );
}
