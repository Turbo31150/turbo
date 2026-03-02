/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BACKEND_URL?: string;
  readonly VITE_WS_URL?: string;
  readonly VITE_OLLAMA_URL?: string;
  readonly VITE_M1_URL?: string;
  readonly VITE_M2_URL?: string;
  readonly VITE_M3_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface ElectronAPI {
  minimize: () => Promise<void>;
  maximize: () => Promise<void>;
  close: () => Promise<void>;
  createWidget: (type: string) => Promise<{ type: string; id: number }>;
  closeWidget: (type: string) => Promise<{ type: string; closed: boolean }>;
  pythonStatus: () => Promise<{ ready: boolean; port: number }>;
  getNodeAuth: (nodeId: string) => Promise<string>;
  version: () => Promise<string>;
  onNavigate: (callback: (page: string) => void) => void;
  onPttState: (callback: (pressed: boolean) => void) => void;
}

interface Window {
  electronAPI: ElectronAPI;
}
