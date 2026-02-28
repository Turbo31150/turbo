const { app, BrowserWindow, globalShortcut, Tray, Menu, screen, ipcMain } = require('electron');
const path = require('path');

let mainWindow = null;
let widgetWindow = null;
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

function createWidgetWindow() {
  if (widgetWindow && !widgetWindow.isDestroyed()) {
    widgetWindow.show();
    widgetWindow.focus();
    return;
  }

  const { width: screenW } = screen.getPrimaryDisplay().workAreaSize;

  widgetWindow = new BrowserWindow({
    width: 420,
    height: 52,
    x: Math.round((screenW - 420) / 2),
    y: 8,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    minimizable: false,
    maximizable: false,
    skipTaskbar: true,
    hasShadow: false,
    backgroundColor: '#00000000',
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  widgetWindow.loadFile(path.join(__dirname, 'widget.html'));
  widgetWindow.setAlwaysOnTop(true, 'floating');

  widgetWindow.on('closed', () => { widgetWindow = null; });
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
    { label: 'Mini Widget', click: () => createWidgetWindow() },
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

// ── IPC Handlers ──
ipcMain.on('window:minimize', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win) win.minimize();
});

ipcMain.on('window:close', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win) win.close();
});

ipcMain.on('window:always-on-top', (event, val) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win) win.setAlwaysOnTop(val);
});

ipcMain.on('widget:detach', () => {
  createWidgetWindow();
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.hide();
});

ipcMain.on('widget:show-main', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.show();
    mainWindow.focus();
  }
});

ipcMain.on('widget:close', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win && !win.isDestroyed()) win.close();
});

ipcMain.on('widget:resize', (event, size) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win && !win.isDestroyed()) {
    win.setSize(size.width || 420, size.height || 52);
    win.setResizable(size.height > 60);
  }
});

app.whenReady().then(() => {
  createWindow();
  createTray();
});

app.on('window-all-closed', () => {
  globalShortcut.unregisterAll();
  app.quit();
});
