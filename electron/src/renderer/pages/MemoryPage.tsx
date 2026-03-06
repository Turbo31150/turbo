import React, { useState, useEffect, useCallback, memo } from 'react';
import { COLORS, FONT, FONTS } from '../lib/theme';

const API_BASE = 'http://127.0.0.1:9742';

const CSS = `
@keyframes mFade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.m-page::-webkit-scrollbar{width:5px}
.m-page::-webkit-scrollbar-thumb{background:${COLORS.border};border-radius:3px}
.m-card{animation:mFade .2s ease;transition:border-color .3s}
.m-card:hover{border-color:${COLORS.orangeAlpha(0.25)}!important}
.m-input{background:${COLORS.bgInput};border:1px solid ${COLORS.border};color:${COLORS.text};padding:6px 10px;border-radius:4px;font-size:12px;font-family:${FONTS.mono};outline:none;width:100%}
.m-input:focus{border-color:${COLORS.orange}}
.m-btn{background:transparent;border:1px solid ${COLORS.border};color:${COLORS.text};padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px}
.m-btn:hover{border-color:${COLORS.orange};color:${COLORS.orange}}
.m-tab{padding:6px 14px;cursor:pointer;border-bottom:2px solid transparent;color:${COLORS.textDim};font-size:12px}
.m-tab.active{border-bottom-color:${COLORS.orange};color:${COLORS.orange}}
`;

interface Memory {
  id: number;
  content: string;
  category: string;
  similarity?: number;
  importance?: number;
  access_count?: number;
  created_at?: number;
}

interface Conversation {
  id: string;
  title: string;
  source: string;
  turn_count: number;
  total_tokens: number;
  updated_at: number;
}

type Tab = 'memories' | 'conversations' | 'search';

const Card = memo(({ children, color = COLORS.border }: { children: React.ReactNode; color?: string }) => (
  <div className="m-card" style={{
    background: COLORS.bgCard, border: `1px solid ${color}`,
    borderRadius: 6, padding: 12, marginBottom: 8,
  }}>
    {children}
  </div>
));

export default function MemoryPage() {
  const [tab, setTab] = useState<Tab>('memories');
  const [memories, setMemories] = useState<Memory[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Memory[]>([]);
  const [newMemory, setNewMemory] = useState('');
  const [newCategory, setNewCategory] = useState('general');

  const fetchMemories = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/api/memory/list?limit=50`);
      const data = await r.json();
      setMemories(data.memories || []);
    } catch {}
  }, []);

  const fetchConversations = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/api/conversations?limit=30`);
      const data = await r.json();
      setConversations(data.conversations || []);
    } catch {}
  }, []);

  useEffect(() => {
    fetchMemories();
    fetchConversations();
  }, [fetchMemories, fetchConversations]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const r = await fetch(`${API_BASE}/api/memory/recall?q=${encodeURIComponent(searchQuery)}&limit=10`);
      const data = await r.json();
      setSearchResults(data.results || []);
      setTab('search');
    } catch {}
  };

  const handleAdd = async () => {
    if (!newMemory.trim()) return;
    try {
      await fetch(`${API_BASE}/api/memory/remember`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: newMemory, category: newCategory }),
      });
      setNewMemory('');
      fetchMemories();
    } catch {}
  };

  const handleDelete = async (id: number) => {
    try {
      await fetch(`${API_BASE}/api/memory/${id}`, { method: 'DELETE' });
      fetchMemories();
    } catch {}
  };

  const fmtTs = (ts: number) => ts ? new Date(ts * 1000).toLocaleString('fr-FR') : '—';

  return (
    <div className="m-page" style={{
      height: '100%', overflow: 'auto', padding: 20,
      background: COLORS.bg, color: COLORS.text, fontFamily: FONTS.sans,
    }}>
      <style>{CSS}</style>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <span style={{ fontSize: 20 }}>MEMORY</span>
        <span style={{ fontSize: 12, color: COLORS.textDim }}>Agent Memory + Conversations</span>
      </div>

      {/* Search bar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input
          className="m-input"
          placeholder="Rechercher dans la memoire..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
        />
        <button className="m-btn" onClick={handleSearch}>Search</button>
        <button className="m-btn" onClick={() => { fetchMemories(); fetchConversations(); }}>Refresh</button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, borderBottom: `1px solid ${COLORS.border}`, marginBottom: 12 }}>
        {(['memories', 'conversations', 'search'] as Tab[]).map(t => (
          <div key={t} className={`m-tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t === 'memories' ? `Memories (${memories.length})` :
             t === 'conversations' ? `Conversations (${conversations.length})` :
             `Search (${searchResults.length})`}
          </div>
        ))}
      </div>

      {/* Add memory */}
      {tab === 'memories' && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <input className="m-input" style={{ flex: 1 }} placeholder="Nouveau souvenir..."
            value={newMemory} onChange={e => setNewMemory(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleAdd()} />
          <select className="m-input" style={{ width: 120 }}
            value={newCategory} onChange={e => setNewCategory(e.target.value)}>
            <option value="general">general</option>
            <option value="tech">tech</option>
            <option value="preference">preference</option>
            <option value="pattern">pattern</option>
            <option value="trading">trading</option>
          </select>
          <button className="m-btn" onClick={handleAdd}>Add</button>
        </div>
      )}

      {/* Content */}
      {tab === 'memories' && memories.map(m => (
        <Card key={m.id} color={m.category === 'preference' ? COLORS.purple : COLORS.border}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontSize: 12, marginBottom: 4 }}>{m.content}</div>
              <div style={{ fontSize: 10, color: COLORS.textDim }}>
                <span style={{ color: COLORS.orange }}>{m.category}</span>
                {' · '}importance: {m.importance} · accessed: {m.access_count}x
                {m.created_at && ` · ${fmtTs(m.created_at)}`}
              </div>
            </div>
            <button className="m-btn" style={{ fontSize: 10, color: COLORS.red, borderColor: COLORS.red }}
              onClick={() => handleDelete(m.id)}>X</button>
          </div>
        </Card>
      ))}

      {tab === 'conversations' && conversations.map(c => (
        <Card key={c.id}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: COLORS.orange }}>{c.title || c.id}</div>
              <div style={{ fontSize: 10, color: COLORS.textDim }}>
                {c.source} · {c.turn_count} turns · {c.total_tokens} tokens · {fmtTs(c.updated_at)}
              </div>
            </div>
            <div style={{ fontSize: 11, color: COLORS.textDim, fontFamily: FONTS.mono }}>{c.id}</div>
          </div>
        </Card>
      ))}

      {tab === 'search' && (searchResults.length === 0 ? (
        <div style={{ textAlign: 'center', color: COLORS.textDim, padding: 20 }}>
          {searchQuery ? 'Aucun resultat' : 'Entrez une requete de recherche'}
        </div>
      ) : searchResults.map(m => (
        <Card key={m.id} color={COLORS.green}>
          <div style={{ fontSize: 12, marginBottom: 4 }}>{m.content}</div>
          <div style={{ fontSize: 10, color: COLORS.textDim }}>
            <span style={{ color: COLORS.green }}>sim: {((m.similarity || 0) * 100).toFixed(1)}%</span>
            {' · '}<span style={{ color: COLORS.orange }}>{m.category}</span>
          </div>
        </Card>
      )))}
    </div>
  );
}
