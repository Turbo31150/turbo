import { useState, useEffect, useCallback, useRef } from 'react';
import { useWebSocket, WsMessage } from './useWebSocket';
import { INTERVALS } from '../lib/config';

export interface GpuInfo {
  name: string;
  vram_total: number;
  vram_used: number;
  temperature?: number;
}

export interface ModelInfo {
  id: string;
  name: string;
  loaded: boolean;
  size?: number;
}

export interface ClusterNode {
  name: string;
  url: string;
  status: 'online' | 'offline' | 'degraded';
  role?: string;
  models: ModelInfo[];
  latency: number;
  gpus: GpuInfo[];
  vram_total: number;
  vram_used: number;
  default_model?: string;
  weight?: number;
}

/** Transform backend node dict to typed ClusterNode array. */
function parseNodes(raw: any): ClusterNode[] {
  if (!raw || typeof raw !== 'object') return [];
  // Backend returns { "M1": {...}, "M2": {...} } dict
  const entries = Array.isArray(raw) ? raw : Object.values(raw);
  return entries.map((n: any) => ({
    name: n.name || 'unknown',
    url: n.url || n.proxy_path || '',
    status: n.online ? 'online' : 'offline',
    role: n.role,
    models: (n.models_loaded || n.models || []).map((m: any) =>
      typeof m === 'string' ? { id: m, name: m, loaded: true } : m
    ),
    latency: n.latency_ms ?? -1,
    gpus: typeof n.gpus === 'number'
      ? Array.from({ length: n.gpus }, (_, i) => ({
          name: `GPU ${i}`,
          vram_total: Math.round(((n.vram_gb || 0) * 1024) / (n.gpus || 1)),
          vram_used: 0,
        }))
      : Array.isArray(n.gpus) ? n.gpus : [],
    vram_total: (n.vram_gb || 0) * 1024, // GB -> MB
    vram_used: 0,
    default_model: n.default_model,
    weight: n.weight,
  }));
}

interface ClusterState {
  nodes: ClusterNode[];
  loading: boolean;
  error: string | null;
}

export function useCluster() {
  const [state, setState] = useState<ClusterState>({
    nodes: [],
    loading: true,
    error: null,
  });
  const { connected, request, subscribe } = useWebSocket();
  const intervalRef = useRef<number | undefined>(undefined);

  const fetchClusterStatus = useCallback(async () => {
    if (!connected) return;

    try {
      const response = await request('cluster', 'get_status');
      const nodes = parseNodes(response.payload?.nodes);
      setState({
        nodes,
        loading: false,
        error: null,
      });
    } catch (err: any) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: err.message || 'Failed to fetch cluster status',
      }));
    }
  }, [connected, request]);

  // Subscribe to push events from cluster channel
  useEffect(() => {
    const unsub = subscribe('cluster', (msg: WsMessage) => {
      if (msg.event === 'node_status_update' && msg.payload) {
        setState(prev => {
          const updatedNodes = prev.nodes.map(node => {
            if (node.name === msg.payload.name) {
              return { ...node, ...msg.payload };
            }
            return node;
          });

          // If node is new, add it
          const exists = prev.nodes.some(n => n.name === msg.payload.name);
          if (!exists && msg.payload.name) {
            updatedNodes.push(msg.payload as ClusterNode);
          }

          return { ...prev, nodes: updatedNodes };
        });
      }

      if (msg.event === 'cluster_full_update' && msg.payload?.nodes) {
        setState(prev => ({
          ...prev,
          nodes: parseNodes(msg.payload.nodes),
          error: null,
        }));
      }
    });

    return unsub;
  }, [subscribe]);

  // Initial fetch and periodic refresh
  useEffect(() => {
    let id: number | undefined;
    if (connected) {
      fetchClusterStatus();
      id = window.setInterval(fetchClusterStatus, INTERVALS.cluster);
    } else {
      setState(prev => ({ ...prev, loading: false, error: 'Not connected' }));
    }

    return () => {
      if (id !== undefined) clearInterval(id);
    };
  }, [connected, fetchClusterStatus]);

  const refreshCluster = useCallback(() => {
    setState(prev => ({ ...prev, loading: true }));
    fetchClusterStatus();
  }, [fetchClusterStatus]);

  return {
    nodes: state.nodes,
    loading: state.loading,
    error: state.error,
    refreshCluster,
  };
}
