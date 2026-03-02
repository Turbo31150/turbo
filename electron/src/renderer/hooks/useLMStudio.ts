import { useState, useEffect, useCallback, useRef } from 'react';
import { LM_NODES, INTERVALS } from '../lib/config';

export interface LMModel {
  id: string;
  object: string;
  owned_by: string;
  loaded: boolean;
  size_gb?: number;
  context_length?: number;
  gpu_offload?: string;
  loaded_instances?: number;
}

export interface LMNode {
  id: string;
  name: string;
  url: string;
  status: 'online' | 'offline' | 'loading';
  models: LMModel[];
  latency: number;
  error?: string;
}

const NODES_CONFIG = LM_NODES;

// Auth cache — populated once via IPC from main process
const _authCache: Record<string, string> = {};
async function getAuth(nodeId: string): Promise<string> {
  if (_authCache[nodeId] !== undefined) return _authCache[nodeId];
  try {
    _authCache[nodeId] = await window.electronAPI.getNodeAuth(nodeId);
  } catch (_e: unknown) {
    _authCache[nodeId] = '';
  }
  return _authCache[nodeId];
}

async function fetchNodeModels(url: string, auth: string): Promise<{ models: LMModel[]; latency: number }> {
  const t0 = performance.now();
  const headers: Record<string, string> = {};
  if (auth) headers['Authorization'] = auth;
  const res = await fetch(`${url}/api/v1/models`, {
    headers,
    signal: AbortSignal.timeout(5000),
  });
  const latency = Math.round(performance.now() - t0);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  const models: LMModel[] = (data.models || data.data || []).map((m: any) => ({
    id: m.id || m.key || m.model,
    object: m.object || 'model',
    owned_by: m.owned_by || '',
    loaded: (m.loaded_instances || 0) > 0,
    size_gb: m.size_on_disk ? +(m.size_on_disk / 1e9).toFixed(1) : undefined,
    context_length: m.context_length || m.max_context_length,
    gpu_offload: m.gpu_offload,
    loaded_instances: m.loaded_instances || 0,
  }));
  return { models, latency };
}

async function sendChat(url: string, auth: string, model: string, prompt: string): Promise<{ text: string; latency: number }> {
  const t0 = performance.now();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (auth) headers['Authorization'] = auth;
  const res = await fetch(`${url}/api/v1/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      model, input: '/nothink\n' + prompt,
      temperature: 0.2, max_output_tokens: 256,
      stream: false, store: false,
    }),
    signal: AbortSignal.timeout(30000),
  });
  const latency = Math.round(performance.now() - t0);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  let text = '';
  for (const block of (data.output || []).reverse()) {
    if (block.type === 'message') {
      const c = block.content;
      text = typeof c === 'string' ? c : (c || []).map((p: any) => typeof p === 'string' ? p : p.text || '').join('');
      break;
    }
  }
  return { text: text || '(pas de reponse)', latency };
}

export function useLMStudio() {
  const [nodes, setNodes] = useState<LMNode[]>(
    NODES_CONFIG.map(c => ({ ...c, status: 'loading' as const, models: [], latency: -1 }))
  );
  const [refreshing, setRefreshing] = useState(false);
  const intervalRef = useRef<number>(0);
  const mountedRef = useRef(true);

  useEffect(() => () => { mountedRef.current = false; }, []);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    const updated = await Promise.all(
      NODES_CONFIG.map(async (cfg) => {
        try {
          const auth = await getAuth(cfg.id);
          const { models, latency } = await fetchNodeModels(cfg.url, auth);
          return { ...cfg, status: 'online' as const, models, latency, error: undefined };
        } catch (e) {
          return { ...cfg, status: 'offline' as const, models: [], latency: -1, error: e instanceof Error ? e.message : String(e) };
        }
      })
    );
    if (!mountedRef.current) return;
    setNodes(updated);
    setRefreshing(false);
  }, []);

  const testModel = useCallback(async (nodeId: string, model: string, prompt: string) => {
    const cfg = NODES_CONFIG.find(n => n.id === nodeId);
    if (!cfg) throw new Error('Node not found');
    const auth = await getAuth(cfg.id);
    return sendChat(cfg.url, auth, model, prompt);
  }, []);

  useEffect(() => {
    refresh();
    intervalRef.current = window.setInterval(refresh, INTERVALS.lmStudio);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [refresh]);

  return { nodes, refreshing, refresh, testModel };
}
