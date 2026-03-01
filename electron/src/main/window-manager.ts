import { BrowserWindow, screen, app } from 'electron';
import path from 'path';
import Store from 'electron-store';

const store = new Store({
  name: 'jarvis-windows',
  defaults: {
    widgetPositions: {} as Record<string, { x: number; y: number }>,
  },
});

const isDev = process.env.NODE_ENV === 'development';

let mainWindow: BrowserWindow | null = null;
const widgetWindows = new Map<string, BrowserWindow>();

// Widget size presets
const WIDGET_SIZES: Record<string, { width: number; height: number }> = {
  MiniCluster: { width: 320, height: 200 },
  MiniTrading: { width: 320, height: 180 },
  MiniVoice: { width: 200, height: 100 },
};

export function createMainWindow(): BrowserWindow {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    backgroundColor: '#0a0e14',
    frame: false,
    titleBarStyle: 'hidden',
    show: true,
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload', 'index.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  if (isDev) {
    mainWindow.loadURL('http://127.0.0.1:5173');
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadURL('http://127.0.0.1:18800/');
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  mainWindow.on('close', (event) => {
    // Minimize to tray instead of closing
    event.preventDefault();
    mainWindow?.hide();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  return mainWindow;
}

export function createWidgetWindow(
  type: string,
  options?: { x?: number; y?: number }
): BrowserWindow {
  // Close existing widget of the same type
  if (widgetWindows.has(type)) {
    widgetWindows.get(type)?.close();
    widgetWindows.delete(type);
  }

  const size = WIDGET_SIZES[type] || { width: 300, height: 200 };

  // Restore saved position or use provided/default position
  const savedPositions = store.get('widgetPositions') as Record<string, { x: number; y: number }>;
  const savedPos = savedPositions[type];
  const display = screen.getPrimaryDisplay();
  const defaultX = display.workAreaSize.width - size.width - 20;
  const defaultY = display.workAreaSize.height - size.height - 20;

  const x = options?.x ?? savedPos?.x ?? defaultX;
  const y = options?.y ?? savedPos?.y ?? defaultY;

  const widget = new BrowserWindow({
    width: size.width,
    height: size.height,
    x,
    y,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    resizable: true,
    skipTaskbar: true,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload', 'index.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  if (isDev) {
    widget.loadURL(`http://127.0.0.1:5173/src/widget-windows/widget.html?type=${type}`);
  } else {
    widget.loadFile(path.join(__dirname, '..', '..', 'dist', 'src', 'widget-windows', 'widget.html'), {
      query: { type },
    });
  }

  // Save position on move
  widget.on('moved', () => {
    const [wx, wy] = widget.getPosition();
    const positions = store.get('widgetPositions') as Record<string, { x: number; y: number }>;
    positions[type] = { x: wx, y: wy };
    store.set('widgetPositions', positions);
  });

  widget.on('closed', () => {
    widgetWindows.delete(type);
  });

  widgetWindows.set(type, widget);
  return widget;
}

export function getMainWindow(): BrowserWindow | null {
  return mainWindow;
}

export function getWidgetWindows(): Map<string, BrowserWindow> {
  return widgetWindows;
}

export function closeWidget(type: string): void {
  const widget = widgetWindows.get(type);
  if (widget) {
    widget.close();
    widgetWindows.delete(type);
  }
}
