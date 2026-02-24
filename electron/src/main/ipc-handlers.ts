import { ipcMain, BrowserWindow, app } from 'electron';
import { PythonBridge } from './python-bridge';
import { createWidgetWindow, closeWidget } from './window-manager';

export function setupIpcHandlers(
  mainWindow: BrowserWindow,
  pythonBridge: PythonBridge
): void {
  // Window controls
  ipcMain.handle('window:minimize', () => {
    mainWindow.minimize();
  });

  ipcMain.handle('window:maximize', () => {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  });

  ipcMain.handle('window:close', () => {
    mainWindow.hide();
  });

  // Widget management
  ipcMain.handle('widget:create', (_event, type: string) => {
    const widget = createWidgetWindow(type);
    return { type, id: widget.id };
  });

  ipcMain.handle('widget:close', (_event, type: string) => {
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

  // App info
  ipcMain.handle('app:version', () => {
    return app.getVersion();
  });
}
