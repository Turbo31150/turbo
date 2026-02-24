import React, { useEffect, useRef } from 'react';

export interface TranscriptionEntry {
  timestamp: number;
  text: string;
  corrected?: string;
}

interface TranscriptionLogProps {
  entries: TranscriptionEntry[];
}

const styles = {
  container: {
    width: '100%',
    maxHeight: 340,
    overflowY: 'auto' as const,
    fontFamily: 'Consolas, Courier New, monospace',
    padding: '8px 0',
  },
  header: {
    fontSize: 12,
    color: '#4a6a8a',
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
    marginBottom: 10,
    paddingLeft: 4,
  },
  entry: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 2,
    padding: '8px 12px',
    borderBottom: '1px solid #0d1117',
  },
  entryHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  timestamp: {
    fontSize: 10,
    color: '#4a6a8a',
    flexShrink: 0,
  },
  text: {
    fontSize: 12,
    color: '#e0e0e0',
    lineHeight: 1.4,
  },
  corrected: {
    fontSize: 11,
    color: '#00d4ff',
    lineHeight: 1.4,
    paddingLeft: 12,
  },
  correctedLabel: {
    fontSize: 9,
    color: '#4a6a8a',
    marginRight: 4,
  },
  empty: {
    textAlign: 'center' as const,
    color: '#4a6a8a',
    fontSize: 12,
    padding: 24,
  },
};

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export default function TranscriptionLog({ entries }: TranscriptionLogProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries.length]);

  return (
    <div>
      <div style={styles.header}>Transcriptions</div>
      <div style={styles.container}>
        {entries.length === 0 ? (
          <div style={styles.empty as any}>Aucune transcription</div>
        ) : (
          entries.map((entry, i) => (
            <div key={i} style={styles.entry}>
              <div style={styles.entryHeader}>
                <span style={styles.timestamp}>{formatTime(entry.timestamp)}</span>
                <span style={styles.text}>{entry.text}</span>
              </div>
              {entry.corrected && entry.corrected !== entry.text && (
                <div style={styles.corrected}>
                  <span style={styles.correctedLabel}>[corrige]</span>
                  {entry.corrected}
                </div>
              )}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
