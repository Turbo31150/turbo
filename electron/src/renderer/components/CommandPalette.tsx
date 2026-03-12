import React, { useState, useEffect, useRef, useCallback } from 'react';
import type { Page } from '../lib/types';

interface CommandItem {
  id: string;
  label: string;
  category: string;
  action: () => void;
  shortcut?: string;
}

interface Props {
  onNavigate: (page: Page) => void;
  onClose: () => void;
}

const PAGES: { id: Page; label: string; shortcut?: string }[] = [
  { id: 'dashboard', label: 'Dashboard', shortcut: '1' },
  { id: 'chat', label: 'Chat', shortcut: '2' },
  { id: 'trading', label: 'Trading', shortcut: '3' },
  { id: 'voice', label: 'Voice', shortcut: '4' },
  { id: 'lmstudio', label: 'LM Studio', shortcut: '5' },
  { id: 'pipelines', label: 'Pipelines', shortcut: '6' },
  { id: 'dictionary', label: 'Dictionary', shortcut: '7' },
  { id: 'toolbox', label: 'Toolbox', shortcut: '8' },
  { id: 'logs', label: 'Logs', shortcut: '9' },
  { id: 'settings', label: 'Settings', shortcut: '0' },
];

export default function CommandPalette({ onNavigate, onClose }: Props) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const items: CommandItem[] = PAGES
    .filter(p => p.label.toLowerCase().includes(query.toLowerCase()) || !query)
    .map(p => ({
      id: p.id,
      label: p.label,
      category: 'Navigation',
      action: () => { onNavigate(p.id); onClose(); },
      shortcut: p.shortcut,
    }));

  // Add theme toggle
  const themeItem: CommandItem = {
    id: 'toggle-theme',
    label: 'Toggle Dark/Light Theme',
    category: 'Settings',
    action: () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      // applyTheme is called from the parent — we just dispatch event
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('jarvis-theme', next);
      onClose();
    },
  };

  if ('theme'.includes(query.toLowerCase()) || 'dark'.includes(query.toLowerCase()) ||
      'light'.includes(query.toLowerCase()) || !query) {
    items.push(themeItem);
  }

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(i => Math.min(i + 1, items.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && items[selectedIndex]) {
      items[selectedIndex].action();
    }
  }, [items, selectedIndex, onClose]);

  return (
    <div className="command-palette-overlay" onClick={onClose}>
      <div className="command-palette" onClick={e => e.stopPropagation()}>
        <input
          ref={inputRef}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a command or page name..."
        />
        <div className="command-palette-results">
          {items.map((item, i) => (
            <div
              key={item.id}
              className="command-palette-item"
              data-selected={i === selectedIndex}
              onClick={item.action}
              onMouseEnter={() => setSelectedIndex(i)}
            >
              <span style={{ opacity: 0.5, fontSize: 11 }}>{item.category}</span>
              <span>{item.label}</span>
              {item.shortcut && <span className="shortcut">Alt+{item.shortcut}</span>}
            </div>
          ))}
          {items.length === 0 && (
            <div style={{ padding: 16, textAlign: 'center', opacity: 0.5 }}>
              No results for "{query}"
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
