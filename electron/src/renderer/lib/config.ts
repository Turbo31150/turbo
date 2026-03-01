/**
 * JARVIS Desktop — Centralized configuration.
 * Single source of truth for URLs, version, and polling intervals.
 */

export const APP_VERSION = '10.3';
export const APP_NAME = 'JARVIS Desktop';
export const APP_STACK = 'Electron 33 + React 19 + Vite 6';

export const BACKEND_URL = 'http://127.0.0.1:9742';
export const WS_URL = 'ws://127.0.0.1:9742/ws';

export const OLLAMA_URL = 'http://127.0.0.1:11434';

export const LM_NODES = [
  { id: 'M1', name: 'M1 / qwen3-8b', url: 'http://10.5.0.2:1234', auth: 'Bearer LMSTUDIO_KEY_M1_REDACTED' },
  { id: 'M2', name: 'M2 / deepseek-coder', url: 'http://192.168.1.26:1234', auth: 'Bearer LMSTUDIO_KEY_M2_REDACTED' },
  { id: 'M3', name: 'M3 / mistral-7b', url: 'http://192.168.1.113:1234', auth: 'Bearer LMSTUDIO_KEY_M3_REDACTED' },
] as const;

export const INTERVALS = {
  cluster: 30_000,
  lmStudio: 60_000,
  metrics: 15_000,
  models: 30_000,
  clock: 30_000,
} as const;
