import { useState, useEffect, useCallback, useRef } from 'react';
import { useWebSocket, WsMessage } from './useWebSocket';

export interface ToolCall {
  id: string;
  name: string;
  arguments?: any;
  result?: string;
  status: 'pending' | 'running' | 'complete' | 'error';
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  agent?: string;
  timestamp: number;
  toolCalls?: ToolCall[];
}

interface ChatState {
  messages: ChatMessage[];
  loading: boolean;
}

export function useChat() {
  const [state, setState] = useState<ChatState>({
    messages: [],
    loading: false,
  });
  const { connected, request, subscribe } = useWebSocket();
  const messageIdCounter = useRef(0);

  // Subscribe to chat channel events
  useEffect(() => {
    const unsub = subscribe('chat', (msg: WsMessage) => {
      switch (msg.event) {
        case 'agent_message': {
          const agentMsg: ChatMessage = {
            id: msg.payload?.id || `agent_${++messageIdCounter.current}_${Date.now()}`,
            role: 'assistant',
            content: msg.payload?.content || '',
            agent: msg.payload?.agent,
            timestamp: msg.payload?.timestamp || Date.now(),
            toolCalls: msg.payload?.toolCalls,
          };
          setState(prev => ({
            ...prev,
            messages: [...prev.messages, agentMsg],
            loading: false,
          }));
          break;
        }

        case 'agent_chunk': {
          // Streaming: append content to the last assistant message
          setState(prev => {
            const messages = [...prev.messages];
            const lastMsg = messages[messages.length - 1];
            if (lastMsg && lastMsg.role === 'assistant' && lastMsg.id === msg.payload?.id) {
              messages[messages.length - 1] = {
                ...lastMsg,
                content: lastMsg.content + (msg.payload?.chunk || ''),
              };
            } else {
              // New streaming message
              messages.push({
                id: msg.payload?.id || `stream_${++messageIdCounter.current}`,
                role: 'assistant',
                content: msg.payload?.chunk || '',
                agent: msg.payload?.agent,
                timestamp: Date.now(),
              });
            }
            return { ...prev, messages };
          });
          break;
        }

        case 'tool_use': {
          // Update tool call status on the latest assistant message
          setState(prev => {
            const messages = [...prev.messages];
            const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant');
            if (lastAssistant) {
              const toolCall: ToolCall = {
                id: msg.payload?.tool_id || `tool_${Date.now()}`,
                name: msg.payload?.tool_name || 'unknown',
                arguments: msg.payload?.arguments,
                result: msg.payload?.result,
                status: msg.payload?.status || 'running',
              };

              const existingIdx = lastAssistant.toolCalls?.findIndex(t => t.id === toolCall.id) ?? -1;
              const toolCalls = [...(lastAssistant.toolCalls || [])];
              if (existingIdx >= 0) {
                toolCalls[existingIdx] = toolCall;
              } else {
                toolCalls.push(toolCall);
              }

              const msgIdx = messages.findIndex(m => m.id === lastAssistant.id);
              if (msgIdx >= 0) {
                messages[msgIdx] = { ...lastAssistant, toolCalls };
              }
            }
            return { ...prev, messages };
          });
          break;
        }

        case 'agent_complete': {
          setState(prev => ({ ...prev, loading: false }));
          break;
        }

        case 'error': {
          const errMsg: ChatMessage = {
            id: `err_${++messageIdCounter.current}_${Date.now()}`,
            role: 'system',
            content: msg.payload?.message || msg.error || 'An error occurred',
            timestamp: Date.now(),
          };
          setState(prev => ({
            ...prev,
            messages: [...prev.messages, errMsg],
            loading: false,
          }));
          break;
        }
      }
    });

    return unsub;
  }, [subscribe]);

  // Send a user message
  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || !connected) return;

    const userMsg: ChatMessage = {
      id: `user_${++messageIdCounter.current}_${Date.now()}`,
      role: 'user',
      content: text.trim(),
      timestamp: Date.now(),
    };

    setState(prev => ({
      messages: [...prev.messages, userMsg],
      loading: true,
    }));

    try {
      await request('chat', 'send_message', {
        content: text.trim(),
        conversation_id: 'default',
      });
      // Response will come via subscribe events
    } catch (err: any) {
      const errMsg: ChatMessage = {
        id: `err_${++messageIdCounter.current}_${Date.now()}`,
        role: 'system',
        content: `Request failed: ${err.message}`,
        timestamp: Date.now(),
      };
      setState(prev => ({
        messages: [...prev.messages, errMsg],
        loading: false,
      }));
    }
  }, [connected, request]);

  // Clear conversation
  const clearConversation = useCallback(async () => {
    setState({ messages: [], loading: false });
    if (connected) {
      try {
        await request('chat', 'clear_conversation', { conversation_id: 'default' });
      } catch {
        // Ignore errors on clear
      }
    }
  }, [connected, request]);

  return {
    messages: state.messages,
    loading: state.loading,
    sendMessage,
    clearConversation,
  };
}
