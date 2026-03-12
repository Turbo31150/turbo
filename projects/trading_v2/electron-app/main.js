/**
 * J.A.R.V.I.S. COMMAND CENTER - Electron Main Process
 * Lance l'interface + bridge Python (commander_v2 via Flask API)
 */
const { app, BrowserWindow, ipcMain, Tray, Menu } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let tray;
let pythonServer;

const ROOT = 'F:/BUREAU/TRADING_V2_PRODUCTION';
const PYTHON_SERVER = path.join(ROOT, 'scripts', 'jarvis_api.py');

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 750,
    minWidth: 800,
    minHeight: 500,
    frame: false,            // Pas de barre de titre Windows
    transparent: false,
    backgroundColor: '#0a0b10',
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
    icon: path.join(__dirname, 'icon.ico')
  });

  mainWindow.loadFile('index.html');

  // DevTools en mode dev
  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('close', (e) => {
    e.preventDefault();
    mainWindow.hide();
  });
}

function startPythonServer() {
  // Lance le serveur API Flask Python en arriere-plan
  pythonServer = spawn('python', [PYTHON_SERVER], {
    cwd: ROOT,
    stdio: ['pipe', 'pipe', 'pipe']
  });

  pythonServer.stdout.on('data', (data) => {
    console.log(`[PYTHON] ${data.toString().trim()}`);
  });

  pythonServer.stderr.on('data', (data) => {
    console.error(`[PYTHON ERR] ${data.toString().trim()}`);
  });

  pythonServer.on('close', (code) => {
    console.log(`[PYTHON] Server exited with code ${code}`);
  });
}

function createTray() {
  // System tray pour garder l'app en vie
  try {
    tray = new Tray(path.join(__dirname, 'icon.ico'));
  } catch {
    // Pas d'icone, skip tray
    return;
  }

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Ouvrir JARVIS', click: () => mainWindow.show() },
    { label: 'Quitter', click: () => {
      if (pythonServer) pythonServer.kill();
      app.exit();
    }}
  ]);

  tray.setToolTip('J.A.R.V.I.S. Command Center');
  tray.setContextMenu(contextMenu);
  tray.on('click', () => mainWindow.show());
}

// IPC handlers pour la fenetre
ipcMain.on('minimize', () => mainWindow.minimize());
ipcMain.on('maximize', () => {
  if (mainWindow.isMaximized()) mainWindow.unmaximize();
  else mainWindow.maximize();
});
ipcMain.on('close', () => mainWindow.hide());
ipcMain.on('quit', () => {
  if (pythonServer) pythonServer.kill();
  app.exit();
});

app.whenReady().then(() => {
  startPythonServer();
  createWindow();
  createTray();
});

app.on('window-all-closed', () => {
  // Ne pas quitter sur Mac
});

app.on('before-quit', () => {
  if (pythonServer) pythonServer.kill();
});
