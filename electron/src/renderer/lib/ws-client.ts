/**
 * WsClient — Singleton WebSocket client with auto-reconnect
 *
 * Used internally by useWebSocket hook.
 * Manages connection lifecycle, exponential backoff, and message dispatch.
 */

export interface WsMessage {
  id?: string;
  type: 'request' | 'response' | 'event';
  channel: string;
  action?: string;
  event?: string;
  payload?: any;
  error?: string;
}

type StateChangeCallback = (connected: boolean) => void;
type MessageCallback = (msg: WsMessage) => void;

export class WsClient {
  private url: string;
  private ws: WebSocket | null = null;
  private connected = false;
  private reconnectTimer: number | null = null;
  private reconnectDelay = 2000;
  private readonly maxReconnectDelay = 30000;
  private readonly baseReconnectDelay = 2000;
  private intentionallyClosed = false;

  private stateCallbacks = new Set<StateChangeCallback>();
  private messageCallbacks = new Set<MessageCallback>();
  private sendQueue: string[] = [];
  private heartbeatTimer: number | null = null;
  private readonly heartbeatInterval = 25000;

  constructor(url: string) {
    this.url = url;
  }

  /**
   * Open the WebSocket connection.
   * Safe to call multiple times — will no-op if already connected/connecting.
   */
  connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.intentionallyClosed = false;
    this.createConnection();
  }

  /**
   * Close the WebSocket connection permanently (no auto-reconnect).
   */
  disconnect(): void {
    this.intentionallyClosed = true;
    this.clearReconnectTimer();

    if (this.ws) {
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
      this.ws.onopen = null;
      this.ws.close();
      this.ws = null;
    }

    this.sendQueue = [];
    this.setConnected(false);
  }

  /**
   * Send a message. If not connected, queues the message for when connection resumes.
   */
  send(msg: WsMessage): void {
    const data = JSON.stringify(msg);

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    } else {
      // Queue for later
      this.sendQueue.push(data);
    }
  }

  /**
   * Check current connection state.
   */
  isConnected(): boolean {
    return this.connected;
  }

  // ---- Event registration ----

  onStateChange(cb: StateChangeCallback): void {
    this.stateCallbacks.add(cb);
  }

  offStateChange(cb: StateChangeCallback): void {
    this.stateCallbacks.delete(cb);
  }

  onMessage(cb: MessageCallback): void {
    this.messageCallbacks.add(cb);
  }

  offMessage(cb: MessageCallback): void {
    this.messageCallbacks.delete(cb);
  }

  // ---- Private methods ----

  private createConnection(): void {
    try {
      this.ws = new WebSocket(this.url);
    } catch (err) {
      console.error('[WsClient] Failed to create WebSocket:', err);
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log('[WsClient] Connected to', this.url);
      this.reconnectDelay = this.baseReconnectDelay;
      this.setConnected(true);
      this.flushQueue();
      this.startHeartbeat();
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        this.messageCallbacks.forEach(cb => {
          try {
            cb(msg);
          } catch (err) {
            console.error('[WsClient] Message handler error:', err);
          }
        });
      } catch (err) {
        console.error('[WsClient] Failed to parse message:', err);
      }
    };

    this.ws.onclose = (event: CloseEvent) => {
      console.log('[WsClient] Connection closed:', event.code, event.reason);
      this.ws = null;
      this.stopHeartbeat();
      this.setConnected(false);

      if (!this.intentionallyClosed) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      // onclose will fire after this, triggering reconnect
      console.warn('[WsClient] Connection error');
    };
  }

  private setConnected(value: boolean): void {
    if (this.connected !== value) {
      this.connected = value;
      this.stateCallbacks.forEach(cb => {
        try {
          cb(value);
        } catch (err) {
          console.error('[WsClient] State callback error:', err);
        }
      });
    }
  }

  private flushQueue(): void {
    while (this.sendQueue.length > 0 && this.ws?.readyState === WebSocket.OPEN) {
      const data = this.sendQueue.shift()!;
      this.ws.send(data);
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();

    console.log(`[WsClient] Reconnecting in ${this.reconnectDelay}ms...`);
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.createConnection();
    }, this.reconnectDelay);

    // Exponential backoff: 2s, 4s, 8s, 16s, max 30s
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = window.setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, this.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }
}
