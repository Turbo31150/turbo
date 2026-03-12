/**
 * JARVIS Terminal Component — Integrated CLI terminal for JARVIS commands.
 *
 * Features:
 * - Command history (up/down arrows)
 * - Auto-scroll to bottom
 * - Syntax-highlighted output
 * - WebSocket streaming for real-time results
 * - Tab completion for known commands
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { COLORS, FONT } from '../lib/theme';
import { BACKEND_URL as API_BASE } from '../lib/config';

interface TerminalLine {
  id: number;
  type: 'input' | 'output' | 'error' | 'system';
  text: string;
  ts: number;
}

const KNOWN_COMMANDS = [
  'help', 'status', 'cluster', 'gpu', 'thermal', 'models',
  'trade', 'positions', 'signals', 'scan',
  'voice', 'speak', 'listen',
  'audit', 'security', 'benchmark',
  'cache', 'clear', 'exit',
  // Phase 3/4 commands
  'observability', 'drift', 'autotune', 'dashboard',
  'intent', 'metrics', 'breakers',
];

const S = {
  container: {
    display: 'flex', flexDirection: 'column' as const,
    height: '100%', backgroundColor: '#0a0a0f',
    borderRadius: 8, border: `1px solid ${COLORS.border}`,
    fontFamily: '"Cascadia Code", "JetBrains Mono", monospace',
    fontSize: 12, overflow: 'hidden',
  },
  header: {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '8px 12px', backgroundColor: '#0f0f18',
    borderBottom: `1px solid ${COLORS.border}`,
  },
  dot: (color: string) => ({
    width: 10, height: 10, borderRadius: '50%',
    backgroundColor: color,
  }),
  title: {
    fontSize: 11, fontWeight: 600, color: COLORS.textDim,
    letterSpacing: 1, textTransform: 'uppercase' as const,
  },
  output: {
    flex: 1, padding: 12, overflowY: 'auto' as const,
    display: 'flex', flexDirection: 'column' as const, gap: 2,
  },
  line: (type: TerminalLine['type']) => ({
    color: type === 'input' ? COLORS.green
         : type === 'error' ? COLORS.red
         : type === 'system' ? COLORS.purple
         : COLORS.text,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap' as const,
    wordBreak: 'break-word' as const,
  }),
  inputRow: {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '8px 12px', borderTop: `1px solid ${COLORS.border}`,
    backgroundColor: '#0d0d14',
  },
  prompt: {
    color: COLORS.orange, fontWeight: 700, fontSize: 12,
    userSelect: 'none' as const,
  },
  input: {
    flex: 1, backgroundColor: 'transparent', border: 'none',
    color: COLORS.text, fontSize: 12,
    fontFamily: '"Cascadia Code", "JetBrains Mono", monospace',
    outline: 'none',
  },
};

export default function Terminal() {
  const [lines, setLines] = useState<TerminalLine[]>([
    { id: 0, type: 'system', text: '╔══════════════════════════════════════╗', ts: Date.now() },
    { id: 1, type: 'system', text: '║  JARVIS Terminal v10.6               ║', ts: Date.now() },
    { id: 2, type: 'system', text: '║  Type "help" for commands            ║', ts: Date.now() },
    { id: 3, type: 'system', text: '╚══════════════════════════════════════╝', ts: Date.now() },
  ]);
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState(-1);
  const [executing, setExecuting] = useState(false);
  const outputRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const lineIdRef = useRef(4);

  // Auto-scroll to bottom
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [lines]);

  const addLine = useCallback((type: TerminalLine['type'], text: string) => {
    const id = lineIdRef.current++;
    setLines(prev => [...prev.slice(-500), { id, type, text, ts: Date.now() }]);
  }, []);

  const executeCommand = useCallback(async (cmd: string) => {
    if (!cmd.trim()) return;

    addLine('input', `jarvis> ${cmd}`);
    setHistory(prev => [...prev.slice(-50), cmd]);
    setHistoryIdx(-1);
    setExecuting(true);

    try {
      // Handle built-in commands
      if (cmd === 'clear') {
        setLines([]);
        setExecuting(false);
        return;
      }
      if (cmd === 'help') {
        // Fetch dynamic help from backend (includes all Phase 3/4 commands)
        try {
          const response = await fetch(`${API_BASE}/api/terminal`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: 'help' }),
          });
          if (response.ok) {
            const data = await response.json();
            if (data.output) {
              data.output.split('\n').forEach((line: string) => addLine('output', line));
            }
          } else {
            addLine('output', '  Type any builtin name for details');
          }
        } catch {
          addLine('system', 'Available commands:');
          addLine('output', '  status  gpu  models  signals  positions');
          addLine('output', '  security  cache  audit  metrics  breakers');
          addLine('output', '  observability  drift  autotune  dashboard  intent');
          addLine('output', '  clear — Clear terminal');
        }
        setExecuting(false);
        return;
      }

      // Send to Python WebSocket backend
      const response = await fetch(`${API_BASE}/api/terminal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.output) {
          data.output.split('\n').forEach((line: string) => {
            addLine('output', line);
          });
        }
        if (data.error) {
          addLine('error', data.error);
        }
      } else {
        addLine('error', `HTTP ${response.status}: ${response.statusText}`);
      }
    } catch (err) {
      addLine('error', `Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setExecuting(false);
    }
  }, [addLine]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !executing) {
      executeCommand(input);
      setInput('');
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (history.length > 0) {
        const idx = historyIdx < 0 ? history.length - 1 : Math.max(0, historyIdx - 1);
        setHistoryIdx(idx);
        setInput(history[idx]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIdx >= 0) {
        const idx = historyIdx + 1;
        if (idx >= history.length) {
          setHistoryIdx(-1);
          setInput('');
        } else {
          setHistoryIdx(idx);
          setInput(history[idx]);
        }
      }
    } else if (e.key === 'Tab') {
      e.preventDefault();
      const matches = KNOWN_COMMANDS.filter(c => c.startsWith(input.toLowerCase()));
      if (matches.length === 1) {
        setInput(matches[0]);
      } else if (matches.length > 1) {
        addLine('system', matches.join('  '));
      }
    }
  }, [input, history, historyIdx, executing, executeCommand, addLine]);

  return (
    <div style={S.container} onClick={() => inputRef.current?.focus()}>
      <div style={S.header}>
        <div style={S.dot(COLORS.green)} />
        <div style={S.dot(COLORS.orange)} />
        <div style={S.dot(COLORS.red)} />
        <span style={S.title}>JARVIS Terminal</span>
      </div>
      <div ref={outputRef} style={S.output}>
        {lines.map(line => (
          <div key={line.id} style={S.line(line.type)}>{line.text}</div>
        ))}
        {executing && (
          <div style={S.line('system')}>⏳ Processing...</div>
        )}
      </div>
      <div style={S.inputRow}>
        <span style={S.prompt}>jarvis&gt;</span>
        <input
          ref={inputRef}
          style={S.input}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={executing ? 'Executing...' : 'Type a command...'}
          disabled={executing}
          autoFocus
        />
      </div>
    </div>
  );
}
