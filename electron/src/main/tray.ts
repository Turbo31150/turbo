import { Tray, Menu, nativeImage, BrowserWindow, app } from 'electron';
import { createWidgetWindow, closeWidget, getWidgetWindows } from './window-manager';

let tray: Tray | null = null;

function createTrayIcon(): Electron.NativeImage {
  // Create a 16x16 tray icon programmatically (cyan "J" on dark background)
  // This is a minimal PNG generated as a data URL
  const size = 16;
  const canvas = Buffer.alloc(size * size * 4); // RGBA

  // Fill with dark background (#0a0e14)
  for (let i = 0; i < size * size; i++) {
    canvas[i * 4] = 10;      // R
    canvas[i * 4 + 1] = 14;  // G
    canvas[i * 4 + 2] = 20;  // B
    canvas[i * 4 + 3] = 255; // A
  }

  // Draw cyan "J" shape (#00d4ff) — simplified pixel art
  const cyan = [0, 212, 255, 255];
  const setPixel = (x: number, y: number) => {
    if (x >= 0 && x < size && y >= 0 && y < size) {
      const idx = (y * size + x) * 4;
      canvas[idx] = cyan[0];
      canvas[idx + 1] = cyan[1];
      canvas[idx + 2] = cyan[2];
      canvas[idx + 3] = cyan[3];
    }
  };

  // "J" letter (columns 4-11, rows 2-13)
  // Top bar
  for (let x = 5; x <= 11; x++) { setPixel(x, 3); setPixel(x, 4); }
  // Vertical stroke (right side)
  for (let y = 3; y <= 11; y++) { setPixel(8, y); setPixel(9, y); }
  // Bottom curve
  setPixel(7, 12); setPixel(8, 12); setPixel(9, 12);
  setPixel(5, 12); setPixel(6, 12);
  setPixel(4, 11); setPixel(5, 11);
  setPixel(4, 10);

  const img = nativeImage.createFromBuffer(canvas, { width: size, height: size });
  return img;
}

export function setupTray(mainWindow: BrowserWindow): void {
  const icon = createTrayIcon();
  tray = new Tray(icon);
  tray.setToolTip('JARVIS Desktop');

  const buildContextMenu = (): Menu => {
    const widgets = getWidgetWindows();

    return Menu.buildFromTemplate([
      {
        label: mainWindow.isVisible() ? 'Hide JARVIS' : 'Show JARVIS',
        click: () => {
          if (mainWindow.isVisible()) {
            mainWindow.hide();
          } else {
            mainWindow.show();
            mainWindow.focus();
          }
        },
      },
      { type: 'separator' },
      {
        label: 'Dashboard',
        click: () => {
          mainWindow.show();
          mainWindow.focus();
          mainWindow.webContents.send('navigate', 'dashboard');
        },
      },
      {
        label: 'Chat',
        click: () => {
          mainWindow.show();
          mainWindow.focus();
          mainWindow.webContents.send('navigate', 'chat');
        },
      },
      {
        label: 'Trading',
        click: () => {
          mainWindow.show();
          mainWindow.focus();
          mainWindow.webContents.send('navigate', 'trading');
        },
      },
      {
        label: 'Voice',
        click: () => {
          mainWindow.show();
          mainWindow.focus();
          mainWindow.webContents.send('navigate', 'voice');
        },
      },
      { type: 'separator' },
      {
        label: 'Widgets',
        submenu: [
          {
            label: 'MiniCluster',
            type: 'checkbox',
            checked: widgets.has('MiniCluster'),
            click: (menuItem) => {
              if (menuItem.checked) {
                createWidgetWindow('MiniCluster');
              } else {
                closeWidget('MiniCluster');
              }
            },
          },
          {
            label: 'MiniTrading',
            type: 'checkbox',
            checked: widgets.has('MiniTrading'),
            click: (menuItem) => {
              if (menuItem.checked) {
                createWidgetWindow('MiniTrading');
              } else {
                closeWidget('MiniTrading');
              }
            },
          },
          {
            label: 'MiniVoice',
            type: 'checkbox',
            checked: widgets.has('MiniVoice'),
            click: (menuItem) => {
              if (menuItem.checked) {
                createWidgetWindow('MiniVoice');
              } else {
                closeWidget('MiniVoice');
              }
            },
          },
        ],
      },
      { type: 'separator' },
      {
        label: 'Quit',
        click: () => {
          mainWindow.removeAllListeners('close');
          tray?.destroy();
          tray = null;
          app.quit();
        },
      },
    ]);
  };

  // Rebuild context menu each time to reflect current state
  tray.on('right-click', () => {
    const menu = buildContextMenu();
    tray?.setContextMenu(menu);
  });

  // Set initial context menu
  tray.setContextMenu(buildContextMenu());

  // Double-click toggles main window
  tray.on('double-click', () => {
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}
