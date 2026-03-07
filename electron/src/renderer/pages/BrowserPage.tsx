import React, { useState, useEffect, useCallback, useRef } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API = 'http://127.0.0.1:9742/api/browser';

const S = {
  page: { display: 'flex', flexDirection: 'column', padding: 16, fontFamily: FONT, height: '100%', overflow: 'hidden', gap: 12 } as React.CSSProperties,
  title: { fontSize: 18, fontWeight: 700, color: COLORS.text } as React.CSSProperties,
  subtitle: { fontSize: 11, color: COLORS.textDim } as React.CSSProperties,
  topBar: { display: 'flex', gap: 8, alignItems: 'center' } as React.CSSProperties,
  urlInput: { flex: 1, backgroundColor: COLORS.bg, border: `1px solid ${COLORS.border}`, borderRadius: 8, color: COLORS.text, fontFamily: 'inherit', fontSize: 13, padding: '8px 12px', outline: 'none' } as React.CSSProperties,
  btn: { padding: '6px 12px', borderRadius: 6, border: `1px solid ${COLORS.border}`, backgroundColor: 'transparent', color: COLORS.textDim, fontSize: 11, cursor: 'pointer', fontFamily: 'inherit', transition: 'all .2s' } as React.CSSProperties,
  btnPrimary: { backgroundColor: COLORS.orange, color: '#fff', border: 'none', fontWeight: 700 },
  btnActive: { borderColor: COLORS.green, color: COLORS.green },
  row: { display: 'flex', gap: 8, flexWrap: 'wrap' } as React.CSSProperties,
  card: { flex: 1, minWidth: 200, padding: 12, backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 8 } as React.CSSProperties,
  cardTitle: { fontSize: 11, color: COLORS.orange, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 } as React.CSSProperties,
  stat: { fontSize: 24, fontWeight: 700, color: COLORS.text } as React.CSSProperties,
  statLabel: { fontSize: 10, color: COLORS.textDim } as React.CSSProperties,
  list: { flex: 1, overflowY: 'auto', fontSize: 12, color: COLORS.text, lineHeight: 1.8 } as React.CSSProperties,
  listItem: { padding: '4px 8px', borderBottom: `1px solid ${COLORS.border}`, cursor: 'pointer', transition: 'background .2s' } as React.CSSProperties,
  badge: { display: 'inline-block', fontSize: 9, padding: '1px 6px', borderRadius: 4, marginLeft: 6, textTransform: 'uppercase' } as React.CSSProperties,
  searchRow: { display: 'flex', gap: 8, alignItems: 'center' } as React.CSSProperties,
  findInput: { width: 180, backgroundColor: COLORS.bg, border: `1px solid ${COLORS.border}`, borderRadius: 6, color: COLORS.text, fontFamily: 'inherit', fontSize: 12, padding: '6px 10px', outline: 'none' } as React.CSSProperties,
  log: { fontSize: 11, color: COLORS.textDim, maxHeight: 120, overflowY: 'auto', padding: 8, backgroundColor: COLORS.bgCard, borderRadius: 6, border: `1px solid ${COLORS.border}` } as React.CSSProperties,
  tabs: { display: 'flex', gap: 4, overflowX: 'auto', paddingBottom: 4 } as React.CSSProperties,
  tab: { padding: '4px 10px', borderRadius: '6px 6px 0 0', border: `1px solid ${COLORS.border}`, borderBottom: 'none', fontSize: 11, color: COLORS.textDim, cursor: 'pointer', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } as React.CSSProperties,
  tabActive: { borderColor: COLORS.orange, color: COLORS.orange, backgroundColor: COLORS.bgCard },
  statusDot: (on: boolean) => ({
    width: 8, height: 8, borderRadius: '50%',
    backgroundColor: on ? COLORS.green : '#ef4444',
    display: 'inline-block', marginRight: 6,
  }),
};

interface BrowserState {
  open: boolean;
  url: string | null;
  title: string;
  tab_count: number;
  landmarks: number;
  links: number;
  buttons: number;
  forms: number;
  images: number;
}

interface Bookmark {
  title: string;
  domain: string;
  url: string;
  tags: string[];
  visit_count: number;
}

interface TabInfo {
  index: number;
  url: string;
  title: string;
}

const api = async (path: string, opts?: RequestInit) => {
  try {
    const r = await fetch(`${API}${path}`, { ...opts, headers: { 'Content-Type': 'application/json', ...opts?.headers } });
    return r.ok ? await r.json() : { error: `HTTP ${r.status}` };
  } catch (e: any) { return { error: e.message }; }
};

export default function BrowserPage() {
  const [state, setState] = useState<BrowserState>({ open: false, url: null, title: '', tab_count: 0, landmarks: 0, links: 0, buttons: 0, forms: 0, images: 0 });
  const [url, setUrl] = useState('');
  const [findText, setFindText] = useState('');
  const [findCount, setFindCount] = useState<number | null>(null);
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [tabs, setTabs] = useState<TabInfo[]>([]);
  const [landmarks, setLandmarks] = useState<any[]>([]);
  const [links, setLinks] = useState<any[]>([]);
  const [log, setLog] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState(0);
  const [view, setView] = useState<'structure' | 'bookmarks' | 'links' | 'landmarks'>('structure');
  const logRef = useRef<HTMLDivElement>(null);

  const addLog = useCallback((msg: string) => {
    setLog(prev => [...prev.slice(-50), `[${new Date().toLocaleTimeString()}] ${msg}`]);
  }, []);

  const refresh = useCallback(async () => {
    const s = await api('/status');
    if (!s.error) {
      setState(prev => ({ ...prev, open: s.open, url: s.url, tab_count: s.tab_count }));
      if (s.open) {
        const info = await api('/page-info');
        if (!info.error) setState(prev => ({ ...prev, url: info.url, title: info.title, tab_count: info.tab_count }));
        const str = await api('/structure');
        if (!str.error) setState(prev => ({ ...prev, links: str.links || 0, buttons: str.buttons || 0, forms: str.forms || 0, images: str.images || 0 }));
        const t = await api('/tabs');
        if (t.tabs) setTabs(t.tabs);
      }
    }
    const bm = await api('/bookmarks?limit=20');
    if (bm.bookmarks) setBookmarks(bm.bookmarks);
    const stats = await api('/stats');
    if (!stats.error) setState(prev => ({ ...prev, landmarks: stats.landmarks || 0 }));
  }, []);

  useEffect(() => { refresh(); const iv = setInterval(refresh, 5000); return () => clearInterval(iv); }, [refresh]);
  useEffect(() => { logRef.current?.scrollTo(0, logRef.current.scrollHeight); }, [log]);

  const doLaunch = async () => {
    addLog('Launching browser...');
    const r = await api('/launch', { method: 'POST', body: JSON.stringify({ url: url || undefined, persistent: true }) });
    addLog(r.error ? `Error: ${r.error}` : `Launched: ${r.status}`);
    refresh();
  };

  const doNavigate = async () => {
    if (!url) return;
    addLog(`Navigating to ${url}...`);
    const r = await api('/navigate', { method: 'POST', body: JSON.stringify({ url, analyze: true }) });
    addLog(r.error ? `Error: ${r.error}` : `Opened: ${r.title || r.url}`);
    setUrl(r.url || url);
    refresh();
  };

  const doAction = async (path: string, body?: any, label?: string) => {
    addLog(label || path);
    const r = await api(path, body ? { method: 'POST', body: JSON.stringify(body) } : undefined);
    addLog(r.error ? `Error: ${r.error}` : JSON.stringify(r).slice(0, 120));
    refresh();
    return r;
  };

  const doFind = async () => {
    if (!findText) { await api('/find', { method: 'POST', body: JSON.stringify({ clear: true }) }); setFindCount(null); return; }
    const r = await api('/find', { method: 'POST', body: JSON.stringify({ text: findText }) });
    setFindCount(r.count ?? 0);
    addLog(`Find "${findText}": ${r.count || 0} matches`);
  };

  const loadLandmarks = async () => {
    const r = await api('/landmarks');
    if (r.landmarks) { setLandmarks(r.landmarks); setView('landmarks'); }
  };

  const loadLinks = async () => {
    const r = await api('/links?max_links=30');
    if (r.links) { setLinks(r.links); setView('links'); }
  };

  const doScrollTo = async (text: string) => {
    await doAction('/scroll', { to_landmark: text }, `Scroll to: ${text}`);
  };

  const doClickLink = async (number: number) => {
    await doAction('/click', { number }, `Click link #${number}`);
  };

  return (
    <div style={S.page}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={S.title}>Browser Control</div>
          <div style={S.subtitle}>Playwright Voice Navigation — {state.open ? 'CONNECTED' : 'OFFLINE'}</div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={S.statusDot(state.open)} />
          <span style={{ fontSize: 11, color: state.open ? COLORS.green : '#ef4444' }}>{state.open ? 'OPEN' : 'CLOSED'}</span>
        </div>
      </div>

      {/* URL Bar */}
      <div style={S.topBar}>
        <button style={S.btn} onClick={() => doAction('/back', {}, 'Back')}>&#8592;</button>
        <button style={S.btn} onClick={() => doAction('/forward', {}, 'Forward')}>&#8594;</button>
        <button style={S.btn} onClick={() => doAction('/reload', undefined, 'Reload')}>&#8635;</button>
        <input style={S.urlInput} value={url} onChange={e => setUrl(e.target.value)}
          placeholder={state.url || 'Enter URL...'} onKeyDown={e => e.key === 'Enter' && (state.open ? doNavigate() : doLaunch())} />
        <button style={{ ...S.btn, ...S.btnPrimary }} onClick={state.open ? doNavigate : doLaunch}>
          {state.open ? 'GO' : 'LAUNCH'}
        </button>
      </div>

      {/* Tabs */}
      {tabs.length > 0 && (
        <div style={S.tabs}>
          {tabs.map(t => (
            <div key={t.index} style={{ ...S.tab, ...(t.index === activeTab ? S.tabActive : {}) }}
              onClick={async () => { setActiveTab(t.index); await doAction('/tab/switch', { index: t.index }, `Tab ${t.index}`); }}>
              {t.title || t.url.slice(0, 30)}
            </div>
          ))}
          <button style={{ ...S.btn, fontSize: 14, padding: '2px 8px' }}
            onClick={() => doAction('/tab/new', {}, 'New tab')}>+</button>
        </div>
      )}

      {/* Action Bar */}
      <div style={S.row}>
        <div style={S.searchRow}>
          <input style={S.findInput} value={findText} onChange={e => setFindText(e.target.value)}
            placeholder="Find on page..." onKeyDown={e => e.key === 'Enter' && doFind()} />
          <button style={S.btn} onClick={doFind}>Find</button>
          {findCount !== null && <span style={{ fontSize: 11, color: COLORS.orange }}>{findCount} found</span>}
        </div>
        <button style={S.btn} onClick={() => doAction('/scroll', { to_top: true }, 'Top')}>Top</button>
        <button style={S.btn} onClick={() => doAction('/scroll', { direction: 'up' }, 'Scroll up')}>Up</button>
        <button style={S.btn} onClick={() => doAction('/scroll', { direction: 'down' }, 'Scroll down')}>Down</button>
        <button style={S.btn} onClick={() => doAction('/scroll', { to_bottom: true }, 'Bottom')}>Bottom</button>
        <button style={S.btn} onClick={() => doAction('/screenshot', undefined, 'Screenshot')}>Screen</button>
        <button style={S.btn} onClick={() => doAction('/bookmark', {}, 'Bookmark')}>Bookmark</button>
        <button style={S.btn} onClick={() => doAction('/summarize', undefined, 'Summarize')}>Resume</button>
      </div>

      {/* Content Area */}
      <div style={{ display: 'flex', gap: 12, flex: 1, overflow: 'hidden' }}>
        {/* Left Panel: Stats + Controls */}
        <div style={{ ...S.card, minWidth: 200, maxWidth: 220, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={S.cardTitle}>Page Info</div>
          <div><span style={S.stat}>{state.links}</span> <span style={S.statLabel}>links</span></div>
          <div><span style={S.stat}>{state.buttons}</span> <span style={S.statLabel}>buttons</span></div>
          <div><span style={S.stat}>{state.forms}</span> <span style={S.statLabel}>forms</span></div>
          <div><span style={S.stat}>{state.images}</span> <span style={S.statLabel}>images</span></div>
          <div style={{ borderTop: `1px solid ${COLORS.border}`, paddingTop: 8 }}>
            <div style={S.cardTitle}>Quick Nav</div>
            <button style={{ ...S.btn, width: '100%', marginBottom: 4, textAlign: 'left' }} onClick={loadLandmarks}>Landmarks ({state.landmarks})</button>
            <button style={{ ...S.btn, width: '100%', marginBottom: 4, textAlign: 'left' }} onClick={loadLinks}>Links</button>
            <button style={{ ...S.btn, width: '100%', marginBottom: 4, textAlign: 'left' }} onClick={() => setView('bookmarks')}>Bookmarks ({bookmarks.length})</button>
          </div>
          <div style={{ borderTop: `1px solid ${COLORS.border}`, paddingTop: 8 }}>
            <div style={S.cardTitle}>Browser</div>
            <button style={{ ...S.btn, width: '100%', marginBottom: 4 }}
              onClick={() => doAction('/close', {}, 'Close browser')}>Close</button>
          </div>
        </div>

        {/* Right Panel: Dynamic content */}
        <div style={{ ...S.card, flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div style={S.cardTitle}>
            {view === 'structure' && 'Page Structure'}
            {view === 'bookmarks' && 'Bookmarks'}
            {view === 'links' && `Links (${links.length})`}
            {view === 'landmarks' && `Landmarks (${landmarks.length})`}
          </div>
          <div style={S.list}>
            {view === 'bookmarks' && bookmarks.map((b, i) => (
              <div key={i} style={S.listItem} onClick={() => { setUrl(b.url); doAction('/navigate', { url: b.url, analyze: true }, `Goto: ${b.title}`); }}>
                <strong>{b.title || b.domain}</strong>
                <span style={{ fontSize: 10, color: COLORS.textDim, marginLeft: 8 }}>{b.domain}</span>
                {b.tags?.map((t: string) => (
                  <span key={t} style={{ ...S.badge, backgroundColor: COLORS.orangeAlpha(0.1), color: COLORS.orange }}>{t}</span>
                ))}
                <span style={{ fontSize: 10, color: COLORS.textDimmer, float: 'right' }}>{b.visit_count}x</span>
              </div>
            ))}
            {view === 'links' && links.map((l, i) => (
              <div key={i} style={S.listItem} onClick={() => doClickLink(i + 1)}>
                <span style={{ color: COLORS.orange, marginRight: 6, fontSize: 10 }}>#{i + 1}</span>
                {l.text}
                <span style={{ fontSize: 10, color: COLORS.textDimmer, marginLeft: 8 }}>{(l.href || '').slice(0, 50)}</span>
              </div>
            ))}
            {view === 'landmarks' && landmarks.map((lm, i) => (
              <div key={i} style={S.listItem} onClick={() => doScrollTo(lm.text)}>
                <span style={{ ...S.badge, backgroundColor: lm.type === 'heading' ? COLORS.orangeAlpha(0.15) : lm.type === 'button' ? COLORS.greenAlpha(0.15) : 'rgba(99,102,241,.15)', color: lm.type === 'heading' ? COLORS.orange : lm.type === 'button' ? COLORS.green : '#6366f1' }}>
                  {lm.type}
                </span>
                {lm.text?.slice(0, 80)}
              </div>
            ))}
            {view === 'structure' && (
              <div style={{ padding: 8 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: COLORS.text, marginBottom: 8 }}>
                  {state.title || 'No page loaded'}
                </div>
                <div style={{ fontSize: 12, color: COLORS.textDim, marginBottom: 12 }}>
                  {state.url || 'Launch browser to start'}
                </div>
                <div style={{ fontSize: 11, color: COLORS.textDim }}>
                  Use the URL bar to navigate, or say voice commands like:<br />
                  "ouvre google.fr" / "cherche Python sur la page" / "lis les liens" / "va au titre Introduction"
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Log */}
      <div ref={logRef} style={S.log}>
        {log.length === 0 ? <span style={{ color: COLORS.textDimmer }}>Ready</span> : log.map((l, i) => <div key={i}>{l}</div>)}
      </div>
    </div>
  );
}
