const { app, BrowserWindow } = require('electron');
const path = require('path');

app.whenReady().then(() => {
  const win = new BrowserWindow({
    width: 1600,
    height: 1000,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  win.loadFile(path.join(__dirname, 'canvas', 'index.html'));
  console.log("JARVIS Interface loaded from: " + path.join(__dirname, 'canvas', 'index.html'));
});
