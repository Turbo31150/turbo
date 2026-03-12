import { ipcMain, BrowserWindow, app } from 'electron';
import { PythonBridge } from './python-bridge';
import { createWidgetWindow, closeWidget } from './window-manager';

export function setupIpcHandlers(
  mainWindow: BrowserWindow,
  pythonBridge: PythonBridge
): void {
  // Window controls
  ipcMain.handle('window:minimize', () => {
    if (!mainWindow.isDestroyed()) mainWindow.minimize();
  });

  ipcMain.handle('window:maximize', () => {
    if (mainWindow.isDestroyed()) return;
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  });

  ipcMain.handle('window:close', () => {
    if (!mainWindow.isDestroyed()) mainWindow.hide();
  });

  // Widget management
  const ALLOWED_WIDGETS = new Set(['MiniCluster', 'MiniTrading', 'MiniVoice']);
  ipcMain.handle('widget:create', (_event, type: string) => {
    if (!ALLOWED_WIDGETS.has(type)) {
      return { type, error: `Unknown widget type: ${type}` };
    }
    const widget = createWidgetWindow(type);
    return { type, id: widget.id };
  });

  ipcMain.handle('widget:close', (_event, type: string) => {
    if (!ALLOWED_WIDGETS.has(type)) {
      return { type, error: `Unknown widget type: ${type}` };
    }
    closeWidget(type);
    return { type, closed: true };
  });

  // Python bridge status
  ipcMain.handle('python:status', () => {
    return {
      ready: pythonBridge.isReady(),
      port: pythonBridge.getPort(),
    };
  });

  // Node auth — tokens from env vars, never hardcoded in renderer
  const NODE_AUTH_MAP: Record<string, string> = {
    M1: process.env.LM_STUDIO_1_API_KEY || '',
    M2: process.env.LM_STUDIO_2_API_KEY || '',
    M3: process.env.LM_STUDIO_3_API_KEY || '',
  };
  ipcMain.handle('node:auth', (_event, nodeId: string) => {
    const key = NODE_AUTH_MAP[nodeId];
    return key ? `Bearer ${key}` : '';
  });

  // App info
  ipcMain.handle('app:version', () => {
    return app.getVersion();
  });
}
