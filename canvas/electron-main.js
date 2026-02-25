// JARVIS Canvas — Electron Wrapper
// Launches direct-proxy.js then opens canvas in a native window
const { app, BrowserWindow, Tray, Menu, globalShortcut, nativeImage } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

const PROXY_PORT = 18800;
const PROXY_URL = `http://127.0.0.1:${PROXY_PORT}`;
let mainWindow = null;
let tray = null;
let proxyProcess = null;

// ── Start direct-proxy as child process ─────────────────────────────────────
function startProxy() {
  return new Promise((resolve) => {
    // Check if proxy already running
    const req = http.get(`${PROXY_URL}/health`, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try {
          const d = JSON.parse(data);
          if (d.ok) { console.log('[electron] Proxy already running'); resolve(true); return; }
        } catch (e) {}
        launchProxy(resolve);
      });
    });
    req.on('error', () => launchProxy(resolve));
    req.setTimeout(2000, () => { req.destroy(); launchProxy(resolve); });
  });
}

function launchProxy(resolve) {
  console.log('[electron] Starting direct-proxy...');
  proxyProcess = spawn(process.execPath.includes('electron') ? 'node' : process.execPath,
    [path.join(__dirname, 'direct-proxy.js')],
    { stdio: 'pipe', windowsHide: true }
  );
  proxyProcess.stdout.on('data', d => {
    const msg = d.toString().trim();
    console.log('[proxy]', msg);
    if (msg.includes('Direct Proxy on')) resolve(true);
  });
  proxyProcess.stderr.on('data', d => console.error('[proxy-err]', d.toString().trim()));
  proxyProcess.on('close', code => { console.log('[proxy] exited', code); proxyProcess = null; });
  // Fallback resolve after 3s
  setTimeout(() => resolve(true), 3000);
}

// ── Create tray icon (cyan "J") ─────────────────────────────────────────────
function createTray() {
  try {
    // Generate 16x16 cyan icon programmatically
    const icon = nativeImage.createFromDataURL('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAQ0lEQVQ4T2NkYPj/n4EBCBgZGUEsEGBkYmICs0EkIwMjI5wNEmBiQpJgYoKrYWRkhKthZGSCq2FkZISrAQkCAQBHJBAR7m8eUwAAAABJRU5ErkJggg==');
    tray = new Tray(icon);
    tray.setToolTip('JARVIS Canvas');
    tray.setContextMenu(Menu.buildFromTemplate([
      { label: 'Ouvrir JARVIS', click: () => { mainWindow?.show(); mainWindow?.focus(); } },
      { type: 'separator' },
      { label: 'Quitter', click: () => app.quit() }
    ]));
    tray.on('click', () => { mainWindow?.show(); mainWindow?.focus(); });
  } catch (e) {
    console.error('[electron] Tray error (non-fatal):', e.message);
  }
}

// ── Create main window ──────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 750,
    minWidth: 800,
    minHeight: 500,
    title: 'JARVIS — Canvas Standalone',
    backgroundColor: '#060a12',
    autoHideMenuBar: true,
    frame: true,
    // icon set by tray
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  mainWindow.loadURL(PROXY_URL);

  mainWindow.on('close', (e) => {
    // Minimize to tray instead of closing
    if (!app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── App lifecycle ───────────────────────────────────────────────────────────
app.on('ready', async () => {
  await startProxy();
  createWindow();
  createTray();

  // Ctrl+Shift+J to toggle window
  globalShortcut.register('CommandOrControl+Shift+J', () => {
    if (mainWindow?.isVisible()) { mainWindow.hide(); }
    else { mainWindow?.show(); mainWindow?.focus(); }
  });
});

app.on('before-quit', () => {
  app.isQuitting = true;
  if (proxyProcess) {
    proxyProcess.kill();
    proxyProcess = null;
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (!mainWindow) createWindow();
});
