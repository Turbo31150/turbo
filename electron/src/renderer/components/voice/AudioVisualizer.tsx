import React from 'react';

interface AudioVisualizerProps {
  level: number;
  recording: boolean;
}

const S = {
  container: { width: '100%', maxWidth: 300, margin: '0 auto', fontFamily: 'Consolas, "Courier New", monospace' } as React.CSSProperties,
  label: { fontSize: 10, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6, textAlign: 'center' } as React.CSSProperties,
  barBg: { width: '100%', height: 6, backgroundColor: '#1a2a3a', borderRadius: 3, overflow: 'hidden', position: 'relative' } as React.CSSProperties,
  bar: { height: '100%', borderRadius: 3, transition: 'width .08s ease-out' } as React.CSSProperties,
  barRec: { backgroundColor: '#10b981', boxShadow: '0 0 8px rgba(16,185,129,.4)' },
  barIdle: { backgroundColor: '#6b7280' },
};

export default function AudioVisualizer({ level, recording }: AudioVisualizerProps) {
  const w = Math.max(0, Math.min(1, level)) * 100;

  return (
    <div style={S.container}>
      <div style={S.label}>Audio Level</div>
      <div style={S.barBg}>
        <div style={{ ...S.bar, ...(recording ? S.barRec : S.barIdle), width: `${w}%` }} />
      </div>
    </div>
  );
}
