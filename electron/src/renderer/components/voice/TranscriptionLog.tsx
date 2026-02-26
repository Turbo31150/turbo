import React, { useEffect, useRef } from 'react';

export interface TranscriptionEntry {
  timestamp: number;
  text: string;
  corrected?: string;
}

interface TranscriptionLogProps {
  entries: TranscriptionEntry[];
}

const S = {
  container: { width: '100%', maxHeight: 340, overflowY: 'auto', fontFamily: 'Consolas, "Courier New", monospace', padding: '8px 0' } as React.CSSProperties,
  header: { fontSize: 12, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10, paddingLeft: 4 } as React.CSSProperties,
  entry: { display: 'flex', flexDirection: 'column', gap: 2, padding: '8px 12px', borderBottom: '1px solid #0d1117' } as React.CSSProperties,
  entryHeader: { display: 'flex', alignItems: 'center', gap: 8 } as React.CSSProperties,
  timestamp: { fontSize: 10, color: '#6b7280', flexShrink: 0 } as React.CSSProperties,
  text: { fontSize: 12, color: '#e0e0e0', lineHeight: 1.4 } as React.CSSProperties,
  corrected: { fontSize: 11, color: '#f97316', lineHeight: 1.4, paddingLeft: 12 } as React.CSSProperties,
  correctedLabel: { fontSize: 9, color: '#6b7280', marginRight: 4 } as React.CSSProperties,
  empty: { textAlign: 'center', color: '#6b7280', fontSize: 12, padding: 24 } as React.CSSProperties,
};

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export default function TranscriptionLog({ entries }: TranscriptionLogProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries.length]);

  return (
    <div>
      <div style={S.header}>Transcriptions</div>
      <div style={S.container}>
        {entries.length === 0 ? (
          <div style={S.empty}>Aucune transcription</div>
        ) : (
          entries.map((entry, i) => (
            <div key={i} style={S.entry}>
              <div style={S.entryHeader}>
                <span style={S.timestamp}>{formatTime(entry.timestamp)}</span>
                <span style={S.text}>{entry.text}</span>
              </div>
              {entry.corrected && entry.corrected !== entry.text && (
                <div style={S.corrected}>
                  <span style={S.correctedLabel}>[corrige]</span>
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
