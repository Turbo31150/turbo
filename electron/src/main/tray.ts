import { Tray, Menu, nativeImage, BrowserWindow, app } from 'electron';
import { createWidgetWindow, closeWidget, getWidgetWindows } from './window-manager';

let tray: Tray | null = null;

function createTrayIcon(): Electron.NativeImage {
  // 16x16 tray icon: cyan "J" on dark background, encoded as a proper PNG data URL
  // Generated from the pixel art pattern: dark bg (#0a0e14) + cyan J (#00d4ff)
  // Using nativeImage.createFromDataURL with a minimal 16x16 PNG
  const size = 16;
  const pixels = new Uint8Array(size * size * 4);

  // Fill with dark background (#0a0e14)
  for (let i = 0; i < size * size; i++) {
    pixels[i * 4] = 10; pixels[i * 4 + 1] = 14; pixels[i * 4 + 2] = 20; pixels[i * 4 + 3] = 255;
  }

  // Draw cyan "J" shape (#00d4ff)
  const set = (x: number, y: number) => {
    if (x >= 0 && x < size && y >= 0 && y < size) {
      const idx = (y * size + x) * 4;
      pixels[idx] = 0; pixels[idx + 1] = 212; pixels[idx + 2] = 255; pixels[idx + 3] = 255;
    }
  };
  for (let x = 5; x <= 11; x++) { set(x, 3); set(x, 4); }
  for (let y = 3; y <= 11; y++) { set(8, y); set(9, y); }
  set(7, 12); set(8, 12); set(9, 12); set(5, 12); set(6, 12);
  set(4, 11); set(5, 11); set(4, 10);

  // Encode as BMP (simpler than PNG, natively supported by nativeImage)
  // BMP = 14-byte header + 40-byte DIB header + pixel data (bottom-up, BGRA)
  const bmpSize = 54 + size * size * 4;
  const bmp = Buffer.alloc(bmpSize);
  // BMP file header
  bmp.write('BM', 0);
  bmp.writeUInt32LE(bmpSize, 2);
  bmp.writeUInt32LE(54, 10); // pixel data offset
  // DIB header (BITMAPINFOHEADER)
  bmp.writeUInt32LE(40, 14); // header size
  bmp.writeInt32LE(size, 18); // width
  bmp.writeInt32LE(-size, 22); // height (negative = top-down)
  bmp.writeUInt16LE(1, 26); // planes
  bmp.writeUInt16LE(32, 28); // bits per pixel
  bmp.writeUInt32LE(0, 30); // no compression
  // Pixel data (BGRA)
  for (let i = 0; i < size * size; i++) {
    const srcOff = i * 4;
    const dstOff = 54 + i * 4;
    bmp[dstOff] = pixels[srcOff + 2];     // B
    bmp[dstOff + 1] = pixels[srcOff + 1]; // G
    bmp[dstOff + 2] = pixels[srcOff];     // R
    bmp[dstOff + 3] = pixels[srcOff + 3]; // A
  }

  return nativeImage.createFromBuffer(bmp);
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
