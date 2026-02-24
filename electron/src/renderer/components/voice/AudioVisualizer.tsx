import React from 'react';

interface AudioVisualizerProps {
  level: number; // 0 to 1
  recording: boolean;
}

const styles = {
  container: {
    width: '100%',
    maxWidth: 300,
    margin: '0 auto',
    fontFamily: 'Consolas, Courier New, monospace',
  },
  label: {
    fontSize: 10,
    color: '#4a6a8a',
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
    marginBottom: 6,
    textAlign: 'center' as const,
  },
  barContainer: {
    width: '100%',
    height: 6,
    backgroundColor: '#1a2a3a',
    borderRadius: 3,
    overflow: 'hidden' as const,
    position: 'relative' as const,
  },
  bar: {
    height: '100%',
    borderRadius: 3,
    transition: 'width 0.08s ease-out',
  },
  barRecording: {
    backgroundColor: '#00ff88',
    boxShadow: '0 0 8px rgba(0, 255, 136, 0.4)',
  },
  barIdle: {
    backgroundColor: '#4a6a8a',
  },
};

export default function AudioVisualizer({ level, recording }: AudioVisualizerProps) {
  const clampedLevel = Math.max(0, Math.min(1, level));
  const widthPercent = clampedLevel * 100;

  return (
    <div style={styles.container}>
      <div style={styles.label as any}>Audio Level</div>
      <div style={styles.barContainer}>
        <div
          style={{
            ...styles.bar,
            ...(recording ? styles.barRecording : styles.barIdle),
            width: `${widthPercent}%`,
          }}
        />
      </div>
    </div>
  );
}
