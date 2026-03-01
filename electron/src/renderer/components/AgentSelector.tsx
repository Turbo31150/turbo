import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';

const BACKEND = 'http://127.0.0.1:9742';

interface AgentModel {
  id: string;
  name: string;
  group: string;
  score: number;
  weight: number;
  speed: string;
  online: boolean;
}

interface AgentSelectorProps {
  value?: string;
  onChange?: (modelId: string) => void;
  compact?: boolean;
}

const S = {
  wrapper: { position: 'relative', display: 'inline-block' } as React.CSSProperties,
  trigger: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', backgroundColor: '#0d1117', border: '1px solid #2a3a4a', borderRadius: 6, color: '#e0e0e0', fontSize: 11, cursor: 'pointer', fontFamily: 'Consolas, Courier New, monospace', transition: 'border-color .2s', minWidth: 160 } as React.CSSProperties,
  triggerOpen: { borderColor: '#f97316' },
  dot: { width: 6, height: 6, borderRadius: '50%', flexShrink: 0 } as React.CSSProperties,
  dotOn: { backgroundColor: '#10b981', boxShadow: '0 0 4px rgba(16,185,129,.5)' },
  dotOff: { backgroundColor: '#ef4444' },
  dropdown: { position: 'absolute', top: '100%', left: 0, marginTop: 4, backgroundColor: '#0d1117', border: '1px solid #2a3a4a', borderRadius: 8, minWidth: 260, maxHeight: 350, overflowY: 'auto', zIndex: 200, boxShadow: '0 8px 24px rgba(0,0,0,.5)' } as React.CSSProperties,
  groupLabel: { fontSize: 9, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1.5, padding: '8px 12px 4px', fontWeight: 700 } as React.CSSProperties,
  option: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', cursor: 'pointer', transition: 'background .15s', fontSize: 11, color: '#e0e0e0' } as React.CSSProperties,
  optionHover: { backgroundColor: 'rgba(249,115,22,.06)' },
  optionSelected: { backgroundColor: 'rgba(249,115,22,.1)', borderLeft: '2px solid #f97316' },
  scoreBadge: (score: number) => ({
    fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 3, marginLeft: 'auto',
    backgroundColor: score >= 95 ? 'rgba(16,185,129,.12)' : score >= 85 ? 'rgba(249,115,22,.12)' : 'rgba(239,68,68,.12)',
    color: score >= 95 ? '#10b981' : score >= 85 ? '#f97316' : '#ef4444',
    border: `1px solid ${score >= 95 ? 'rgba(16,185,129,.25)' : score >= 85 ? 'rgba(249,115,22,.25)' : 'rgba(239,68,68,.25)'}`,
  }),
  speedLabel: { fontSize: 9, color: '#6b7280' } as React.CSSProperties,
  arrow: { fontSize: 8, color: '#6b7280', marginLeft: 'auto', transition: 'transform .2s' } as React.CSSProperties,
};

export default function AgentSelector({ value, onChange, compact }: AgentSelectorProps) {
  const [models, setModels] = useState<AgentModel[]>([]);
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const fetchModels = useCallback(async () => {
    try {
      const r = await fetch(BACKEND + '/api/models', { signal: AbortSignal.timeout(5000) });
      if (r.ok) {
        const data = await r.json();
        setModels(data.models || []);
      }
    } catch { /* offline */ }
  }, []);

  useEffect(() => {
    fetchModels();
    const iv = setInterval(fetchModels, 30000);
    return () => clearInterval(iv);
  }, [fetchModels]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const grouped = useMemo(() => {
    const groups: Record<string, AgentModel[]> = { local: [], cloud: [], proxy: [] };
    for (const m of models) {
      const g = m.group === 'local' ? 'local' : m.group === 'cloud' ? 'cloud' : 'proxy';
      groups[g].push(m);
    }
    return groups;
  }, [models]);

  const selected = models.find(m => m.id === value);

  return (
    <div ref={wrapperRef} style={S.wrapper}>
      <button style={{ ...S.trigger, ...(open ? S.triggerOpen : {}), ...(compact ? { padding: '4px 8px', fontSize: 10 } : {}) }}
        onClick={() => setOpen(!open)}>
        <span style={{ ...S.dot, ...(selected?.online ? S.dotOn : S.dotOff) }} />
        <span>{selected?.name || 'Auto (best)'}</span>
        <span style={{ ...S.arrow, transform: open ? 'rotate(180deg)' : 'none' }}>&#9660;</span>
      </button>

      {open && (
        <div style={S.dropdown}>
          {/* Auto option */}
          <div style={{ ...S.option, ...(hovered === 'auto' ? S.optionHover : {}), ...(!value ? S.optionSelected : {}) }}
            onClick={() => { onChange?.(''); setOpen(false); }}
            onMouseEnter={() => setHovered('auto')} onMouseLeave={() => setHovered(null)}>
            <span style={{ ...S.dot, ...S.dotOn }} />
            <span>Auto (routage intelligent)</span>
          </div>

          {/* Grouped models */}
          {Object.entries(grouped).map(([group, items]) => {
            if (items.length === 0) return null;
            const label = group === 'local' ? 'Local' : group === 'cloud' ? 'Cloud Ollama' : 'Proxy (GEMINI / CLAUDE)';
            return (
              <div key={group}>
                <div style={S.groupLabel}>{label}</div>
                {items.map(m => (
                  <div key={m.id}
                    style={{ ...S.option, ...(hovered === m.id ? S.optionHover : {}), ...(value === m.id ? S.optionSelected : {}) }}
                    onClick={() => { onChange?.(m.id); setOpen(false); }}
                    onMouseEnter={() => setHovered(m.id)} onMouseLeave={() => setHovered(null)}>
                    <span style={{ ...S.dot, ...(m.online ? S.dotOn : S.dotOff) }} />
                    <span>{m.name}</span>
                    <span style={S.speedLabel}>{m.speed}</span>
                    {group === 'proxy' && (
                      <span style={{ fontSize: 8, color: '#f59e0b', padding: '0 4px', border: '1px solid rgba(245,158,11,.3)', borderRadius: 3 }}>PROXY</span>
                    )}
                    <span style={S.scoreBadge(m.score)}>{m.score}</span>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
