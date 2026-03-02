import { app, BrowserWindow, globalShortcut } from 'electron';
import { createMainWindow } from './window-manager';
import { PythonBridge } from './python-bridge';
import { setupTray } from './tray';
import { setupIpcHandlers } from './ipc-handlers';
import path from 'path';

const pythonBridge = new PythonBridge();

app.whenReady().then(async () => {
  // Start Python WS backend
  try {
    await pythonBridge.start();
  } catch (err) {
    console.error('[Main] Failed to start Python backend:', err);
  }

  // Create main window
  const mainWindow = createMainWindow();

  // Setup system tray
  setupTray(mainWindow);

  // Setup IPC handlers
  setupIpcHandlers(mainWindow, pythonBridge);

  // Register global shortcuts
  globalShortcut.register('Control+Shift+J', () => {
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  // PTT shortcut (Ctrl key hold) - will be handled per-window

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

app.on('window-all-closed', () => {
  // Don't quit, keep in tray
});

app.on('before-quit', () => {
  pythonBridge.stop();
  globalShortcut.unregisterAll();
});
