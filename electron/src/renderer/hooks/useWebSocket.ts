import { useState, useEffect, useRef, useCallback } from 'react';
import { WsClient, WsMessage } from '../lib/ws-client';
import { WS_URL } from '../lib/config';

export type { WsMessage };

export type MessageHandler = (msg: WsMessage) => void;

// Singleton client instance — survives HMR via window reference
const GLOBAL_KEY = '__jarvis_ws_client__';
function getClient(url: string): WsClient {
  const w = window as any;
  if (!w[GLOBAL_KEY]) {
    w[GLOBAL_KEY] = new WsClient(url);
  }
  return w[GLOBAL_KEY];
}

export function useWebSocket(url: string = WS_URL) {
  const [connected, setConnected] = useState(false);
  const clientRef = useRef<WsClient>(getClient(url));
  const handlersRef = useRef<Map<string, Set<MessageHandler>>>(new Map());
  const pendingRef = useRef<Map<string, (msg: WsMessage) => void>>(new Map());
  const msgCounter = useRef(0);

  useEffect(() => {
    const client = clientRef.current;

    const onStateChange = (state: boolean) => {
      setConnected(state);
    };

    const onMessage = (msg: WsMessage) => {
      // Handle response to pending request
      if (msg.type === 'response' && msg.id) {
        const resolver = pendingRef.current.get(msg.id);
        if (resolver) {
          resolver(msg);
          pendingRef.current.delete(msg.id);
          return;
        }
      }

      // Handle push events - dispatch to channel handlers
      const channel = msg.channel;
      if (channel) {
        const handlers = handlersRef.current.get(channel);
        if (handlers) {
          handlers.forEach(h => h(msg));
        }
      }

      // Also dispatch to '*' wildcard handlers
      const wildcard = handlersRef.current.get('*');
      if (wildcard) {
        wildcard.forEach(h => h(msg));
      }
    };

    client.onStateChange(onStateChange);
    client.onMessage(onMessage);
    client.connect();

    // Set initial state
    setConnected(client.isConnected());

    return () => {
      client.offStateChange(onStateChange);
      client.offMessage(onMessage);
    };
  }, [url]);

  // Send request and wait for response
  const request = useCallback((channel: string, action: string, payload?: any): Promise<WsMessage> => {
    return new Promise((resolve, reject) => {
      const client = clientRef.current;
      if (!client.isConnected()) {
        reject(new Error('WebSocket not connected'));
        return;
      }

      const id = `req_${++msgCounter.current}_${Date.now()}`;
      const msg: WsMessage = {
        id,
        type: 'request',
        channel,
        action,
        payload: payload || {},
      };

      // Set timeout (longer for chat commands that run scripts)
      const timeoutMs = channel === 'chat' ? 120000 : 30000;
      const timeout = setTimeout(() => {
        pendingRef.current.delete(id);
        reject(new Error('Request timeout'));
      }, timeoutMs);

      pendingRef.current.set(id, (response) => {
        clearTimeout(timeout);
        if (response.error) {
          reject(new Error(response.error));
        } else {
          resolve(response);
        }
      });

      client.send(msg);
    });
  }, []);

  // Subscribe to channel events
  const subscribe = useCallback((channel: string, handler: MessageHandler) => {
    if (!handlersRef.current.has(channel)) {
      handlersRef.current.set(channel, new Set());
    }
    handlersRef.current.get(channel)!.add(handler);

    return () => {
      handlersRef.current.get(channel)?.delete(handler);
    };
  }, []);

  return { connected, request, subscribe };
}
