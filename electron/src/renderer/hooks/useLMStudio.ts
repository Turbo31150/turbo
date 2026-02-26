import { useState, useEffect, useCallback, useRef } from 'react';

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
  auth: string;
  status: 'online' | 'offline' | 'loading';
  models: LMModel[];
  latency: number;
  error?: string;
}

const NODES_CONFIG = [
  { id: 'M1', name: 'M1 / qwen3-8b', url: 'http://10.5.0.2:1234', auth: 'Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7' },
  { id: 'M2', name: 'M2 / deepseek-coder', url: 'http://192.168.1.26:1234', auth: 'Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4' },
  { id: 'M3', name: 'M3 / mistral-7b', url: 'http://192.168.1.113:1234', auth: 'Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux' },
];

async function fetchNodeModels(url: string, auth: string): Promise<{ models: LMModel[]; latency: number }> {
  const t0 = performance.now();
  const res = await fetch(`${url}/api/v1/models`, {
    headers: { 'Authorization': auth },
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
  const res = await fetch(`${url}/api/v1/chat`, {
    method: 'POST',
    headers: { 'Authorization': auth, 'Content-Type': 'application/json' },
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

  const refresh = useCallback(async () => {
    setRefreshing(true);
    const updated = await Promise.all(
      NODES_CONFIG.map(async (cfg) => {
        try {
          const { models, latency } = await fetchNodeModels(cfg.url, cfg.auth);
          return { ...cfg, status: 'online' as const, models, latency, error: undefined };
        } catch (e: any) {
          return { ...cfg, status: 'offline' as const, models: [], latency: -1, error: e.message };
        }
      })
    );
    setNodes(updated);
    setRefreshing(false);
  }, []);

  const testModel = useCallback(async (nodeId: string, model: string, prompt: string) => {
    const cfg = NODES_CONFIG.find(n => n.id === nodeId);
    if (!cfg) throw new Error('Node not found');
    return sendChat(cfg.url, cfg.auth, model, prompt);
  }, []);

  useEffect(() => {
    refresh();
    intervalRef.current = window.setInterval(refresh, 30000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [refresh]);

  return { nodes, refreshing, refresh, testModel };
}
