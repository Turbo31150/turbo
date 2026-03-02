import React, { useState, useEffect, useCallback, useMemo, memo, useRef } from 'react';
import { BACKEND_URL } from '../lib/config';
import { COLORS, FONT } from '../lib/theme';

interface DictEntry {
  id: number;
  pipeline_id?: string;
  trigger_phrase: string;
  steps?: string;
  category: string;
  action_type: string;
  agents_involved?: string;
  avg_duration_ms?: number;
  usage_count?: number;
  source: 'command' | 'pipeline' | 'db';
}

interface DictStats {
  commands: number;
  pipelines: number;
  db_entries: number;
  chains: number;
  corrections: number;
  categories: Record<string, number>;
}

const CSS = `
@keyframes dictFade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.dict-row{animation:dictFade .2s ease;transition:background .15s}
.dict-row:hover{background:${COLORS.orangeAlpha(0.04)}!important}
.dict-input:focus{border-color:${COLORS.orange}!important}
.dict-page::-webkit-scrollbar{width:5px}
.dict-page::-webkit-scrollbar-thumb{background:${COLORS.border};border-radius:3px}
`;

const S = {
  page: { padding: 20, fontFamily: FONT, height: '100%', overflowY: 'auto' } as React.CSSProperties,
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 } as React.CSSProperties,
  title: { fontSize: 18, fontWeight: 700, color: COLORS.text } as React.CSSProperties,
  stats: { display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' } as React.CSSProperties,
  stat: { backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 8, padding: '12px 18px', display: 'flex', flexDirection: 'column', gap: 4, minWidth: 120 } as React.CSSProperties,
  statLabel: { fontSize: 10, color: COLORS.textDim, textTransform: 'uppercase', letterSpacing: 1.5 } as React.CSSProperties,
  statVal: { fontSize: 22, fontWeight: 700 } as React.CSSProperties,
  toolbar: { display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' } as React.CSSProperties,
  search: { flex: 1, minWidth: 200, padding: '8px 12px', backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, color: COLORS.text, fontSize: 12, fontFamily: 'inherit', outline: 'none' } as React.CSSProperties,
  filterBtn: { padding: '6px 12px', borderRadius: 6, border: `1px solid ${COLORS.border}`, backgroundColor: 'transparent', color: COLORS.textDim, fontSize: 10, cursor: 'pointer', fontFamily: 'inherit', transition: 'all .2s', textTransform: 'uppercase', letterSpacing: .5 } as React.CSSProperties,
  filterActive: { borderColor: COLORS.orange, color: COLORS.orange, backgroundColor: COLORS.orangeAlpha(0.08) },
  table: { width: '100%', borderCollapse: 'collapse' } as React.CSSProperties,
  th: { textAlign: 'left', padding: '8px 12px', fontSize: 10, color: COLORS.textDim, textTransform: 'uppercase', letterSpacing: 1, borderBottom: `1px solid ${COLORS.border}`, fontWeight: 700 } as React.CSSProperties,
  td: { padding: '8px 12px', fontSize: 12, color: COLORS.text, borderBottom: `1px solid ${COLORS.bgCard}` } as React.CSSProperties,
  badge: { fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 4, letterSpacing: .5 } as React.CSSProperties,
  catBadge: { backgroundColor: COLORS.purpleAlpha(0.1), color: COLORS.purple, border: `1px solid ${COLORS.purpleAlpha(0.2)}` },
  typeBadge: { backgroundColor: COLORS.greenAlpha(0.1), color: COLORS.green, border: `1px solid ${COLORS.greenAlpha(0.2)}` },
  srcBadge: (src: string) => ({
    backgroundColor: src === 'command' ? COLORS.orangeAlpha(0.1) : src === 'pipeline' ? COLORS.purpleAlpha(0.1) : COLORS.greenAlpha(0.1),
    color: src === 'command' ? COLORS.orange : src === 'pipeline' ? COLORS.purple : COLORS.green,
    border: `1px solid ${src === 'command' ? COLORS.orangeAlpha(0.2) : src === 'pipeline' ? COLORS.purpleAlpha(0.2) : COLORS.greenAlpha(0.2)}`,
  }),
  pagination: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 16, fontSize: 12, color: COLORS.textDim } as React.CSSProperties,
  pageBtn: { padding: '4px 10px', borderRadius: 4, border: `1px solid ${COLORS.border}`, backgroundColor: 'transparent', color: COLORS.textDim, fontSize: 11, cursor: 'pointer', fontFamily: 'inherit' } as React.CSSProperties,
  emptyState: { textAlign: 'center', padding: 40, color: COLORS.textDim, fontSize: 13 } as React.CSSProperties,
  addBtn: { padding: '6px 14px', borderRadius: 6, border: `1px solid ${COLORS.green}`, backgroundColor: COLORS.greenAlpha(0.08), color: COLORS.green, fontSize: 11, cursor: 'pointer', fontFamily: 'inherit', fontWeight: 600 } as React.CSSProperties,
  modal: { position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: COLORS.overlay, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 } as React.CSSProperties,
  modalBox: { backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 10, padding: 24, width: 480, maxHeight: '80vh', overflowY: 'auto' } as React.CSSProperties,
  formGroup: { marginBottom: 12 } as React.CSSProperties,
  label: { display: 'block', fontSize: 10, color: COLORS.textDim, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 } as React.CSSProperties,
  input: { width: '100%', padding: '8px 10px', backgroundColor: COLORS.bg, border: `1px solid ${COLORS.border}`, borderRadius: 6, color: COLORS.text, fontSize: 12, fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box' } as React.CSSProperties,
  formBtns: { display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 } as React.CSSProperties,
  cancelBtn: { padding: '6px 14px', borderRadius: 6, border: `1px solid ${COLORS.border}`, backgroundColor: 'transparent', color: COLORS.textDim, fontSize: 11, cursor: 'pointer', fontFamily: 'inherit' } as React.CSSProperties,
  saveBtn: { padding: '6px 14px', borderRadius: 6, border: 'none', backgroundColor: COLORS.orange, color: '#000', fontSize: 11, cursor: 'pointer', fontFamily: 'inherit', fontWeight: 700 } as React.CSSProperties,
  deleteBtn: { padding: '4px 10px', borderRadius: 4, border: `1px solid ${COLORS.redAlpha(0.3)}`, backgroundColor: 'transparent', color: COLORS.red, fontSize: 10, cursor: 'pointer', fontFamily: 'inherit' } as React.CSSProperties,
};

const PAGE_SIZE = 50;

const DictRow = memo(function DictRow({ entry, onEdit, onDelete }: { entry: DictEntry; onEdit: (e: DictEntry) => void; onDelete: (id: number) => void }) {
  return (
    <tr className="dict-row">
      <td style={S.td}><span style={{ ...S.badge, ...S.srcBadge(entry.source) }}>{entry.source}</span></td>
      <td style={{ ...S.td, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{entry.trigger_phrase}</td>
      <td style={S.td}><span style={{ ...S.badge, ...S.catBadge }}>{entry.category}</span></td>
      <td style={S.td}><span style={{ ...S.badge, ...S.typeBadge }}>{entry.action_type}</span></td>
      <td style={{ ...S.td, textAlign: 'right', color: COLORS.textDim, fontSize: 10 }}>{entry.usage_count || 0}</td>
      <td style={{ ...S.td, textAlign: 'right' }}>
        {entry.source === 'db' && (
          <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
            <button style={{ ...S.pageBtn, fontSize: 10, padding: '2px 6px' }} onClick={() => onEdit(entry)}>Edit</button>
            <button style={{ ...S.deleteBtn, fontSize: 9, padding: '2px 6px' }} onClick={() => onDelete(entry.id)}>Del</button>
          </div>
        )}
      </td>
    </tr>
  );
});

export default function DictionaryPage() {
  const [entries, setEntries] = useState<DictEntry[]>([]);
  const [stats, setStats] = useState<DictStats | null>(null);
  const [search, setSearch] = useState('');
  const [catFilter, setCatFilter] = useState('');
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editEntry, setEditEntry] = useState<DictEntry | null>(null);
  const [form, setForm] = useState({ trigger_phrase: '', category: '', action_type: 'powershell', steps: '', agents_involved: '' });
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const [savingEntry, setSavingEntry] = useState(false);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => () => {
    mountedRef.current = false;
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
  }, []);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => { toastTimerRef.current = null; setToast(null); }, 3000);
  };

  useEffect(() => {
    if (!showForm) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setShowForm(false); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [showForm]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [dictResp, statsResp] = await Promise.all([
        fetch(BACKEND_URL + '/api/dictionary', { signal: AbortSignal.timeout(10000) }),
        fetch(BACKEND_URL + '/api/dictionary/stats', { signal: AbortSignal.timeout(5000) }),
      ]);
      if (dictResp.ok) {
        const data = await dictResp.json();
        const all: DictEntry[] = [];
        for (const cmd of (data.commands || [])) {
          all.push({ id: cmd.id || all.length, trigger_phrase: cmd.trigger || cmd.name || '', category: cmd.category || '', action_type: cmd.action_type || '', source: 'command', usage_count: cmd.usage_count || 0 });
        }
        for (const p of (data.pipelines || [])) {
          all.push({ id: p.id || all.length + 1000, trigger_phrase: p.trigger || p.name || '', category: p.category || '', action_type: 'pipeline', source: 'pipeline', usage_count: p.usage_count || 0 });
        }
        for (const d of (data.db_entries || [])) {
          all.push({ id: d.id, pipeline_id: d.pipeline_id, trigger_phrase: d.trigger_phrase || '', steps: d.steps, category: d.category || '', action_type: d.action_type || '', agents_involved: d.agents_involved, avg_duration_ms: d.avg_duration_ms, usage_count: d.usage_count || 0, source: 'db' });
        }
        if (mountedRef.current) setEntries(all);
      }
      if (statsResp.ok && mountedRef.current) setStats(await statsResp.json());
    } catch (err) {
      console.warn('[Dictionary] fetch error:', err instanceof Error ? err.message : err);
    }
    if (mountedRef.current) setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const categories = useMemo(() => {
    const cats = new Set<string>();
    entries.forEach(e => { if (e.category) cats.add(e.category); });
    return Array.from(cats).sort();
  }, [entries]);

  const filtered = useMemo(() => {
    let list = entries;
    if (catFilter) list = list.filter(e => e.category === catFilter);
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(e => e.trigger_phrase.toLowerCase().includes(q) || e.category.toLowerCase().includes(q) || e.action_type.toLowerCase().includes(q));
    }
    return list;
  }, [entries, catFilter, search]);

  const paged = useMemo(() => filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE), [filtered, page]);
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  useEffect(() => { setPage(0); }, [search, catFilter]);

  const handleDelete = useCallback(async (id: number) => {
    if (!window.confirm('Supprimer cette commande ?')) return;
    try {
      const r = await fetch(BACKEND_URL + `/api/dictionary/command/${id}`, { method: 'DELETE', signal: AbortSignal.timeout(10000) });
      if (r.ok) { showToast('Commande supprimee', true); fetchAll(); }
      else showToast(`Erreur suppression (${r.status})`, false);
    } catch (err) {
      console.warn('[Dictionary] delete error:', err instanceof Error ? err.message : err);
      showToast('Erreur connexion', false);
    }
  }, [fetchAll]);

  const handleEdit = useCallback((entry: DictEntry) => {
    setEditEntry(entry);
    setForm({ trigger_phrase: entry.trigger_phrase, category: entry.category, action_type: entry.action_type, steps: entry.steps || '', agents_involved: entry.agents_involved || '' });
    setShowForm(true);
  }, []);

  const handleSave = useCallback(async () => {
    if (savingEntry) return;
    setSavingEntry(true);
    const body = { ...form };
    try {
      const url = editEntry
        ? BACKEND_URL + `/api/dictionary/command/${editEntry.id}`
        : BACKEND_URL + '/api/dictionary/command';
      const r = await fetch(url, {
        method: editEntry ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(10000),
      });
      if (r.ok) {
        showToast(editEntry ? 'Commande modifiee' : 'Commande creee', true);
        setShowForm(false);
        setEditEntry(null);
        fetchAll();
      } else {
        showToast(`Erreur sauvegarde (${r.status})`, false);
      }
    } catch (err) {
      console.warn('[Dictionary] save error:', err instanceof Error ? err.message : err);
      showToast('Erreur connexion', false);
    }
    setSavingEntry(false);
  }, [form, editEntry, fetchAll, savingEntry]);

  return (
    <>
      <style>{CSS}</style>
      <div className="dict-page" style={S.page}>
        {toast && (
          <div style={{
            padding: '8px 16px', borderRadius: 8, fontSize: 12, marginBottom: 12,
            fontFamily: 'inherit', animation: 'dictFade .3s ease',
            backgroundColor: toast.ok ? COLORS.greenAlpha(0.1) : COLORS.redAlpha(0.1),
            border: `1px solid ${toast.ok ? COLORS.greenAlpha(0.3) : COLORS.redAlpha(0.3)}`,
            color: toast.ok ? COLORS.green : COLORS.red,
          }}>{toast.msg}</div>
        )}
        <div style={S.header}>
          <div style={S.title}>Dictionnaire Vocal</div>
          <button style={S.addBtn} onClick={() => { setEditEntry(null); setForm({ trigger_phrase: '', category: '', action_type: 'powershell', steps: '', agents_involved: '' }); setShowForm(true); }}>
            + Ajouter
          </button>
        </div>

        {stats && (
          <div style={S.stats}>
            <div style={S.stat}>
              <span style={S.statLabel}>Commandes</span>
              <span style={{ ...S.statVal, color: COLORS.orange }}>{stats.commands}</span>
            </div>
            <div style={S.stat}>
              <span style={S.statLabel}>Pipelines</span>
              <span style={{ ...S.statVal, color: COLORS.purple }}>{stats.pipelines}</span>
            </div>
            <div style={S.stat}>
              <span style={S.statLabel}>DB Entries</span>
              <span style={{ ...S.statVal, color: COLORS.green }}>{stats.db_entries}</span>
            </div>
            <div style={S.stat}>
              <span style={S.statLabel}>Chains</span>
              <span style={{ ...S.statVal, color: COLORS.textDim }}>{stats.chains}</span>
            </div>
            <div style={S.stat}>
              <span style={S.statLabel}>Corrections</span>
              <span style={{ ...S.statVal, color: COLORS.textDim }}>{stats.corrections}</span>
            </div>
          </div>
        )}

        <div style={S.toolbar}>
          <input className="dict-input" style={S.search} placeholder="Rechercher commandes, categories..."
            value={search} onChange={e => setSearch(e.target.value)} />
          <button style={{ ...S.filterBtn, ...(catFilter === '' ? S.filterActive : {}) }} onClick={() => setCatFilter('')}>Tous</button>
          {categories.slice(0, 8).map(cat => (
            <button key={cat} style={{ ...S.filterBtn, ...(catFilter === cat ? S.filterActive : {}) }}
              onClick={() => setCatFilter(catFilter === cat ? '' : cat)}>{cat}</button>
          ))}
          {categories.length > 8 && <span style={{ fontSize: 10, color: COLORS.textDim }}>+{categories.length - 8}</span>}
        </div>

        {loading ? (
          <div style={S.emptyState}>Chargement du dictionnaire...</div>
        ) : filtered.length === 0 ? (
          <div style={S.emptyState}>Aucune commande trouvee{search ? ` pour "${search}"` : ''}</div>
        ) : (
          <>
            <div style={{ fontSize: 10, color: COLORS.textDim, marginBottom: 8 }}>{filtered.length} resultats</div>
            <table style={S.table}>
              <thead>
                <tr>
                  <th style={{ ...S.th, width: 80 }}>Source</th>
                  <th style={S.th}>Commande / Trigger</th>
                  <th style={{ ...S.th, width: 100 }}>Categorie</th>
                  <th style={{ ...S.th, width: 100 }}>Type</th>
                  <th style={{ ...S.th, width: 60, textAlign: 'right' }}>Usage</th>
                  <th style={{ ...S.th, width: 80, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {paged.map(entry => (
                  <DictRow key={`${entry.source}_${entry.id}`} entry={entry} onEdit={handleEdit} onDelete={handleDelete} />
                ))}
              </tbody>
            </table>

            {totalPages > 1 && (
              <div style={S.pagination}>
                <button style={S.pageBtn} onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0}>&lt;</button>
                <span>{page + 1} / {totalPages}</span>
                <button style={S.pageBtn} onClick={() => setPage(Math.min(totalPages - 1, page + 1))} disabled={page >= totalPages - 1}>&gt;</button>
              </div>
            )}
          </>
        )}

        {showForm && (
          <div style={S.modal} onClick={() => setShowForm(false)} role="dialog" aria-modal="true" aria-labelledby="dict-modal-title">
            <div style={S.modalBox} onClick={e => e.stopPropagation()}>
              <div id="dict-modal-title" style={{ fontSize: 16, fontWeight: 700, color: COLORS.text, marginBottom: 16 }}>
                {editEntry ? 'Modifier commande' : 'Nouvelle commande'}
              </div>
              <div style={S.formGroup}>
                <label style={S.label}>Trigger Phrase</label>
                <input className="dict-input" style={S.input} value={form.trigger_phrase}
                  onChange={e => setForm({ ...form, trigger_phrase: e.target.value })} placeholder="ouvre chrome" />
              </div>
              <div style={S.formGroup}>
                <label style={S.label}>Categorie</label>
                <input className="dict-input" style={S.input} value={form.category}
                  onChange={e => setForm({ ...form, category: e.target.value })} placeholder="navigation" />
              </div>
              <div style={S.formGroup}>
                <label style={S.label}>Action Type</label>
                <select style={{ ...S.input, cursor: 'pointer' }} value={form.action_type}
                  onChange={e => setForm({ ...form, action_type: e.target.value })}>
                  {['powershell', 'curl', 'python', 'pipeline', 'condition', 'system', 'media', 'browser', 'voice', 'shortcut', 'script'].map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div style={S.formGroup}>
                <label style={S.label}>Steps (JSON)</label>
                <textarea className="dict-input" style={{ ...S.input, minHeight: 60, resize: 'vertical' }} value={form.steps}
                  onChange={e => setForm({ ...form, steps: e.target.value })} placeholder='["step1", "step2"]' />
              </div>
              <div style={S.formGroup}>
                <label style={S.label}>Agents</label>
                <input className="dict-input" style={S.input} value={form.agents_involved}
                  onChange={e => setForm({ ...form, agents_involved: e.target.value })} placeholder="ia-fast, ia-system" />
              </div>
              <div style={S.formBtns}>
                <button style={S.cancelBtn} onClick={() => setShowForm(false)}>Annuler</button>
                <button style={{ ...S.saveBtn, ...(savingEntry ? { opacity: 0.5, cursor: 'not-allowed' } : {}) }} onClick={handleSave} disabled={savingEntry}>{savingEntry ? 'Sauvegarde...' : editEntry ? 'Modifier' : 'Creer'}</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
