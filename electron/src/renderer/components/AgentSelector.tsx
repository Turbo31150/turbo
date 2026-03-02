import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { BACKEND_URL, INTERVALS } from '../lib/config';
import { COLORS, FONT } from '../lib/theme';

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
  trigger: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, color: COLORS.text, fontSize: 11, cursor: 'pointer', fontFamily: FONT, transition: 'border-color .2s', minWidth: 160 } as React.CSSProperties,
  triggerOpen: { borderColor: COLORS.orange },
  dot: { width: 6, height: 6, borderRadius: '50%', flexShrink: 0 } as React.CSSProperties,
  dotOn: { backgroundColor: COLORS.green, boxShadow: `0 0 4px ${COLORS.greenAlpha(0.5)}` },
  dotOff: { backgroundColor: COLORS.red },
  dropdown: { position: 'absolute', top: '100%', left: 0, marginTop: 4, backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 8, minWidth: 260, maxHeight: 350, overflowY: 'auto', zIndex: 200, boxShadow: `0 8px 24px ${COLORS.overlay}` } as React.CSSProperties,
  groupLabel: { fontSize: 9, color: COLORS.textDimmer, textTransform: 'uppercase', letterSpacing: 1.5, padding: '8px 12px 4px', fontWeight: 700 } as React.CSSProperties,
  option: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', cursor: 'pointer', transition: 'background .15s', fontSize: 11, color: COLORS.text } as React.CSSProperties,
  optionHover: { backgroundColor: COLORS.orangeAlpha(0.06) },
  optionSelected: { backgroundColor: COLORS.orangeAlpha(0.1), borderLeft: `2px solid ${COLORS.orange}` },
  scoreBadge: (score: number) => ({
    fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 3, marginLeft: 'auto',
    backgroundColor: score >= 95 ? COLORS.greenAlpha(0.12) : score >= 85 ? COLORS.orangeAlpha(0.12) : COLORS.redAlpha(0.12),
    color: score >= 95 ? COLORS.green : score >= 85 ? COLORS.orange : COLORS.red,
    border: `1px solid ${score >= 95 ? COLORS.greenAlpha(0.25) : score >= 85 ? COLORS.orangeAlpha(0.25) : COLORS.redAlpha(0.25)}`,
  }),
  speedLabel: { fontSize: 9, color: COLORS.textDim } as React.CSSProperties,
  arrow: { fontSize: 8, color: COLORS.textDim, marginLeft: 'auto', transition: 'transform .2s' } as React.CSSProperties,
};

export default function AgentSelector({ value, onChange, compact }: AgentSelectorProps) {
  const [models, setModels] = useState<AgentModel[]>([]);
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);
  const [loadingModels, setLoadingModels] = useState(true);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const focusIdx = useRef(-1);

  const fetchModels = useCallback(async () => {
    setLoadingModels(true);
    try {
      const r = await fetch(BACKEND_URL + '/api/models', { signal: AbortSignal.timeout(5000) });
      if (r.ok) {
        const data = await r.json();
        setModels(data.models || []);
      }
    } catch (err) {
      console.warn('[AgentSelector] fetch models error:', err instanceof Error ? err.message : err);
    }
    setLoadingModels(false);
  }, []);

  useEffect(() => {
    fetchModels();
    const iv = setInterval(fetchModels, INTERVALS.models);
    return () => clearInterval(iv);
  }, [fetchModels]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const allOptions = useMemo(() => {
    const opts: string[] = [''];
    for (const m of models) opts.push(m.id);
    return opts;
  }, [models]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault();
        setOpen(true);
        focusIdx.current = allOptions.indexOf(value || '');
      }
      return;
    }
    switch (e.key) {
      case 'Escape':
        e.preventDefault();
        setOpen(false);
        break;
      case 'ArrowDown':
        e.preventDefault();
        focusIdx.current = Math.min(focusIdx.current + 1, allOptions.length - 1);
        setHovered(allOptions[focusIdx.current] || 'auto');
        break;
      case 'ArrowUp':
        e.preventDefault();
        focusIdx.current = Math.max(focusIdx.current - 1, 0);
        setHovered(allOptions[focusIdx.current] || 'auto');
        break;
      case 'Enter':
        e.preventDefault();
        if (focusIdx.current >= 0 && focusIdx.current < allOptions.length) {
          onChange?.(allOptions[focusIdx.current]);
        }
        setOpen(false);
        break;
    }
  }, [open, allOptions, value, onChange]);

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
    <div ref={wrapperRef} style={S.wrapper} onKeyDown={handleKeyDown}>
      <button
        style={{ ...S.trigger, ...(open ? S.triggerOpen : {}), ...(compact ? { padding: '4px 8px', fontSize: 10 } : {}) }}
        onClick={() => setOpen(!open)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span style={{ ...S.dot, ...(selected?.online ? S.dotOn : S.dotOff) }} />
        <span>{loadingModels ? 'Chargement...' : selected?.name || 'Auto (best)'}</span>
        <span style={{ ...S.arrow, transform: open ? 'rotate(180deg)' : 'none' }}>&#9660;</span>
      </button>

      {open && (
        <div style={S.dropdown} role="listbox" aria-label="Selection agent IA">
          <div role="option" aria-selected={!value} style={{ ...S.option, ...(hovered === 'auto' ? S.optionHover : {}), ...(!value ? S.optionSelected : {}) }}
            onClick={() => { onChange?.(''); setOpen(false); }}
            onMouseEnter={() => setHovered('auto')} onMouseLeave={() => setHovered(null)}>
            <span style={{ ...S.dot, ...S.dotOn }} />
            <span>Auto (routage intelligent)</span>
          </div>

          {Object.entries(grouped).map(([group, items]) => {
            if (items.length === 0) return null;
            const label = group === 'local' ? 'Local' : group === 'cloud' ? 'Cloud Ollama' : 'Proxy (GEMINI / CLAUDE)';
            return (
              <div key={group}>
                <div style={S.groupLabel}>{label}</div>
                {items.map(m => (
                  <div key={m.id} role="option" aria-selected={value === m.id}
                    style={{ ...S.option, ...(hovered === m.id ? S.optionHover : {}), ...(value === m.id ? S.optionSelected : {}) }}
                    onClick={() => { onChange?.(m.id); setOpen(false); }}
                    onMouseEnter={() => setHovered(m.id)} onMouseLeave={() => setHovered(null)}>
                    <span style={{ ...S.dot, ...(m.online ? S.dotOn : S.dotOff) }} />
                    <span>{m.name}</span>
                    <span style={S.speedLabel}>{m.speed}</span>
                    {group === 'proxy' && (
                      <span style={{ fontSize: 8, color: COLORS.amber, padding: '0 4px', border: `1px solid ${COLORS.orangeAlpha(0.3)}`, borderRadius: 3 }}>PROXY</span>
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
