/**
 * JARVIS Desktop — Centralized configuration.
 * Single source of truth for URLs, version, and polling intervals.
 */

export const APP_VERSION = '10.6';
export const APP_NAME = 'JARVIS Desktop';
export const APP_STACK = 'Electron 33 + React 19 + Vite 6';

export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:9742';
export const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://127.0.0.1:9742/ws';

export const OLLAMA_URL = import.meta.env.VITE_OLLAMA_URL ?? 'http://127.0.0.1:11434';

export const LM_NODES = [
  { id: 'M1', name: 'M1 / qwen3-8b', url: import.meta.env.VITE_M1_URL ?? 'http://127.0.0.1:1234' },
  { id: 'M2', name: 'M2 / deepseek-r1', url: import.meta.env.VITE_M2_URL ?? 'http://192.168.1.26:1234' },
  { id: 'M3', name: 'M3 / deepseek-r1', url: import.meta.env.VITE_M3_URL ?? 'http://192.168.1.113:1234' },
] as const;

export const INTERVALS = {
  cluster: 30_000,
  lmStudio: 60_000,
  metrics: 15_000,
  models: 30_000,
  clock: 30_000,
} as const;
