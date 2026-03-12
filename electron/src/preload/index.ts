import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  // Window controls
  minimize: () => ipcRenderer.invoke('window:minimize'),
  maximize: () => ipcRenderer.invoke('window:maximize'),
  close: () => ipcRenderer.invoke('window:close'),

  // Widgets
  createWidget: (type: string) => ipcRenderer.invoke('widget:create', type),
  closeWidget: (type: string) => ipcRenderer.invoke('widget:close', type),

  // Python bridge status
  pythonStatus: () => ipcRenderer.invoke('python:status'),

  // Node auth (tokens from main process env vars)
  getNodeAuth: (nodeId: string) => ipcRenderer.invoke('node:auth', nodeId),

  // App info
  version: () => ipcRenderer.invoke('app:version'),

  // Listen for events from main (return cleanup functions)
  onNavigate: (callback: (page: string) => void) => {
    const handler = (_event: IpcRendererEvent, page: string) => callback(page);
    ipcRenderer.on('navigate', handler);
    return () => { ipcRenderer.removeListener('navigate', handler); };
  },
  onPttState: (callback: (pressed: boolean) => void) => {
    const handler = (_event: IpcRendererEvent, pressed: boolean) => callback(pressed);
    ipcRenderer.on('ptt-state', handler);
    return () => { ipcRenderer.removeListener('ptt-state', handler); };
  },
});
