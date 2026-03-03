import { ChildProcess, spawn } from 'child_process';
import { app } from 'electron';
import http from 'http';
import path from 'path';
import fs from 'fs';

const HEALTH_URL = 'http://127.0.0.1:9742/health';
const HEALTH_POLL_INTERVAL = 500;
const HEALTH_TIMEOUT = 30000;
const MAX_RETRIES = 3;
const PORT = 9742;
const DEBUG = !app.isPackaged;

// Resolve paths based on environment
function resolveUvPath(): string {
  // Check common locations
  const candidates = [
    process.env.UV_PATH,
    path.join(process.env.USERPROFILE || '', '.local', 'bin', 'uv.exe'),
  ].filter(Boolean) as string[];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return 'uv'; // fallback to PATH
}

function resolveWorkingDir(): string {
  if (app.isPackaged) {
    // In packaged mode, python_ws is in resources but src/ is still at turbo root
    // Use the parent of the extraResources python_ws
    const resourcePythonWs = path.join(process.resourcesPath, 'python_ws');
    if (fs.existsSync(resourcePythonWs)) {
      return process.resourcesPath;
    }
  }
  // Dev mode: electron/ is inside turbo project root
  return path.resolve(__dirname, '..', '..', '..');
}

export class PythonBridge {
  private process: ChildProcess | null = null;
  private ready = false;
  private retryCount = 0;
  private stopping = false;
  private killTimer: ReturnType<typeof setTimeout> | null = null;
  private restartTimer: ReturnType<typeof setTimeout> | null = null;

  async start(): Promise<void> {
    this.stopping = false;
    this.retryCount = 0;

    // Check if port is already in use (external server running)
    const portInUse = await this.checkPortInUse();
    if (portInUse) {
      if (DEBUG) console.log('[PythonBridge] Port 9742 already in use — using existing server.');
      this.ready = true;
      return;
    }

    await this.spawnProcess();
  }

  stop(): void {
    this.stopping = true;
    this.ready = false;
    if (this.restartTimer) { clearTimeout(this.restartTimer); this.restartTimer = null; }
    if (this.killTimer) { clearTimeout(this.killTimer); this.killTimer = null; }
    if (this.process) {
      if (DEBUG) console.log('[PythonBridge] Stopping Python process...');
      const proc = this.process;
      this.process = null;
      proc.stdout?.removeAllListeners('data');
      proc.stderr?.removeAllListeners('data');
      proc.removeAllListeners('exit');
      proc.removeAllListeners('error');
      proc.kill('SIGTERM');
      // Force kill after 5 seconds if still alive
      this.killTimer = setTimeout(() => {
        this.killTimer = null;
        if (!proc.killed) {
          if (DEBUG) console.log('[PythonBridge] Force killing Python process...');
          proc.kill('SIGKILL');
        }
      }, 5000);
    }
  }

  isReady(): boolean {
    return this.ready;
  }

  getPort(): number {
    return PORT;
  }

  private async spawnProcess(): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      const uvPath = resolveUvPath();
      const workDir = resolveWorkingDir();
      if (DEBUG) {
        console.log('[PythonBridge] Starting Python WS backend...');
        console.log(`[PythonBridge] UV path: ${uvPath}`);
        console.log(`[PythonBridge] Working dir: ${workDir}`);
      }

      this.process = spawn(uvPath, ['run', 'python', '-m', 'python_ws.server'], {
        cwd: workDir,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: Object.fromEntries(
          Object.entries(process.env).filter(([k]) =>
            !k.startsWith('CLAUDE') || k === 'CLAUDE_WORKSPACE'
          )
        ),
      });

      // Handle stdout (only log in dev)
      if (DEBUG) {
        this.process.stdout?.on('data', (data: Buffer) => {
          const lines = data.toString().trim().split('\n');
          for (const line of lines) {
            console.log(`[Python stdout] ${line}`);
          }
        });
      }

      // Handle stderr (only log in dev — uvicorn logs go to stderr)
      if (DEBUG) {
        this.process.stderr?.on('data', (data: Buffer) => {
          const lines = data.toString().trim().split('\n');
          for (const line of lines) {
            console.error(`[Python stderr] ${line}`);
          }
        });
      }

      // Handle process exit
      this.process.on('exit', (code, signal) => {
        if (DEBUG) console.log(`[PythonBridge] Python process exited with code=${code}, signal=${signal}`);
        this.ready = false;
        this.process = null;

        // Auto-restart on crash if not intentionally stopping
        if (!this.stopping && this.retryCount < MAX_RETRIES) {
          this.retryCount++;
          if (DEBUG) console.log(`[PythonBridge] Auto-restarting (attempt ${this.retryCount}/${MAX_RETRIES})...`);
          this.restartTimer = setTimeout(() => {
            this.restartTimer = null;
            this.spawnProcess().catch((err) => {
              console.error('[PythonBridge] Restart failed:', err);
            });
          }, 1000 * this.retryCount);
        } else if (this.retryCount >= MAX_RETRIES) {
          console.error(`[PythonBridge] Max retries (${MAX_RETRIES}) reached. Giving up.`);
        }
      });

      // Handle spawn error
      this.process.on('error', (err) => {
        console.error('[PythonBridge] Failed to spawn Python process:', err);
        reject(err);
      });

      // Wait for health check
      this.waitForHealth()
        .then(() => {
          this.ready = true;
          this.retryCount = 0;
          if (DEBUG) console.log('[PythonBridge] Python backend is ready.');
          resolve();
        })
        .catch((err) => {
          console.error('[PythonBridge] Health check failed:', err.message);
          // Don't reject — process might still start up, let auto-restart handle it
          resolve();
        });
    });
  }

  private checkPortInUse(): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
      const req = http.get(HEALTH_URL, (res) => {
        res.resume();
        resolve(res.statusCode === 200);
      });
      req.on('error', () => resolve(false));
      req.setTimeout(1000, () => {
        req.destroy();
        resolve(false);
      });
    });
  }

  private waitForHealth(): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      const startTime = Date.now();

      const poll = () => {
        if (Date.now() - startTime > HEALTH_TIMEOUT) {
          reject(new Error(`Health check timeout after ${HEALTH_TIMEOUT}ms`));
          return;
        }

        const req = http.get(HEALTH_URL, (res) => {
          if (res.statusCode === 200) {
            // Consume response data to free up memory
            res.resume();
            if (DEBUG) console.log('[PythonBridge] Health check passed.');
            resolve();
          } else {
            res.resume();
            setTimeout(poll, HEALTH_POLL_INTERVAL);
          }
        });

        req.on('error', () => {
          // Connection refused — server not ready yet
          setTimeout(poll, HEALTH_POLL_INTERVAL);
        });

        req.setTimeout(2000, () => {
          req.destroy();
          setTimeout(poll, HEALTH_POLL_INTERVAL);
        });
      };

      poll();
    });
  }
}
