/// <reference types="vite/client" />

interface ElectronAPI {
  minimize: () => Promise<void>;
  maximize: () => Promise<void>;
  close: () => Promise<void>;
  createWidget: (type: string) => Promise<{ type: string; id: number }>;
  closeWidget: (type: string) => Promise<{ type: string; closed: boolean }>;
  pythonStatus: () => Promise<{ ready: boolean; port: number }>;
  version: () => Promise<string>;
  onNavigate: (callback: (page: string) => void) => void;
  onPttState: (callback: (pressed: boolean) => void) => void;
}

interface Window {
  electronAPI: ElectronAPI;
}
