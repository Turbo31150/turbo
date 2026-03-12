import { app, BrowserWindow, globalShortcut } from 'electron';
import { createMainWindow, getMainWindow } from './window-manager';
import { PythonBridge } from './python-bridge';
import { setupTray } from './tray';
import { setupIpcHandlers } from './ipc-handlers';

// Single-instance lock — prevent duplicate JARVIS instances
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    const win = getMainWindow();
    if (win) {
      if (win.isMinimized()) win.restore();
      win.show();
      win.focus();
    }
  });
}

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

  // Register global shortcuts — use getMainWindow() to avoid stale ref
  globalShortcut.register('Control+Shift+J', () => {
    const win = getMainWindow();
    if (!win) return;
    if (win.isVisible()) {
      win.hide();
    } else {
      win.show();
      win.focus();
    }
  });

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
