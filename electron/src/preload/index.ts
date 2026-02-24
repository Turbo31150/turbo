import { contextBridge, ipcRenderer } from 'electron';

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

  // App info
  version: () => ipcRenderer.invoke('app:version'),

  // Listen for events from main (return cleanup functions)
  onNavigate: (callback: (page: string) => void) => {
    const handler = (_event: any, page: string) => callback(page);
    ipcRenderer.on('navigate', handler);
    return () => { ipcRenderer.removeListener('navigate', handler); };
  },
  onPttState: (callback: (pressed: boolean) => void) => {
    const handler = (_event: any, pressed: boolean) => callback(pressed);
    ipcRenderer.on('ptt-state', handler);
    return () => { ipcRenderer.removeListener('ptt-state', handler); };
  },
});
