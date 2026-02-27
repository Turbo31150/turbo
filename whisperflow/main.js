const { app, BrowserWindow, globalShortcut, Tray, Menu, screen } = require('electron');
const path = require('path');

let mainWindow = null;
let tray = null;
let isAlwaysOnTop = true;

function createWindow() {
  const { width: screenW, height: screenH } = screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    width: 380,
    height: 520,
    x: screenW - 400,
    y: screenH - 560,
    frame: false,
    transparent: false,
    alwaysOnTop: isAlwaysOnTop,
    resizable: true,
    minimizable: true,
    skipTaskbar: false,
    backgroundColor: '#0a0e14',
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));
  mainWindow.setMinimumSize(300, 400);

  // Restore on focus
  mainWindow.on('restore', () => mainWindow.show());

  // Global shortcut: Ctrl+Shift+W = toggle WhisperFlow
  globalShortcut.register('Ctrl+Shift+W', () => {
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

function createTray() {
  try {
    tray = new Tray(path.join(__dirname, 'icon.png'));
  } catch(e) {
    // No icon, skip tray
    return;
  }
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Afficher WhisperFlow', click: () => { mainWindow.show(); mainWindow.focus(); } },
    { label: 'Toujours visible', type: 'checkbox', checked: isAlwaysOnTop, click: (item) => {
      isAlwaysOnTop = item.checked;
      mainWindow.setAlwaysOnTop(isAlwaysOnTop);
    }},
    { type: 'separator' },
    { label: 'Quitter', click: () => app.quit() },
  ]);
  tray.setToolTip('JARVIS WhisperFlow');
  tray.setContextMenu(contextMenu);
  tray.on('click', () => { mainWindow.show(); mainWindow.focus(); });
}

app.whenReady().then(() => {
  createWindow();
  createTray();
});

app.on('window-all-closed', () => {
  globalShortcut.unregisterAll();
  app.quit();
});
