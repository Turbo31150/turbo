const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Main window controls
  minimize: () => ipcRenderer.send('window:minimize'),
  close: () => ipcRenderer.send('window:close'),
  setAlwaysOnTop: (val) => ipcRenderer.send('window:always-on-top', val),

  // Widget controls
  detachWidget: () => ipcRenderer.send('widget:detach'),
  showMain: () => ipcRenderer.send('widget:show-main'),
  closeWidget: () => ipcRenderer.send('widget:close'),
  resizeWidget: (size) => ipcRenderer.send('widget:resize', size),
});
