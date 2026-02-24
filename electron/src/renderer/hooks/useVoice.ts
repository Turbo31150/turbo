import { useState, useEffect, useCallback, useRef } from 'react';
import { useWebSocket, WsMessage } from './useWebSocket';
import { AudioRecorder } from '../lib/audio';

interface VoiceState {
  recording: boolean;
  transcription: string;
  audioLevel: number;
}

export function useVoice() {
  const [state, setState] = useState<VoiceState>({
    recording: false,
    transcription: '',
    audioLevel: 0,
  });
  const { connected, request, subscribe } = useWebSocket();
  const recorderRef = useRef<AudioRecorder | null>(null);
  const levelAnimRef = useRef<number | undefined>(undefined);

  // Subscribe to voice channel events
  useEffect(() => {
    const unsub = subscribe('voice', (msg: WsMessage) => {
      switch (msg.event) {
        case 'transcription_result': {
          setState(prev => ({
            ...prev,
            transcription: msg.payload?.text || '',
          }));
          break;
        }

        case 'transcription_partial': {
          setState(prev => ({
            ...prev,
            transcription: msg.payload?.text || prev.transcription,
          }));
          break;
        }

        case 'tts_started': {
          // TTS playback started on backend
          break;
        }

        case 'tts_finished': {
          // TTS playback completed
          break;
        }

        case 'voice_error': {
          console.error('[Voice] Error:', msg.payload?.message);
          setState(prev => ({
            ...prev,
            recording: false,
          }));
          break;
        }
      }
    });

    return unsub;
  }, [subscribe]);

  // Update audio level continuously while recording
  const updateLevel = useCallback(() => {
    if (recorderRef.current) {
      const level = recorderRef.current.getLevel();
      setState(prev => ({ ...prev, audioLevel: level }));
    }
    levelAnimRef.current = requestAnimationFrame(updateLevel);
  }, []);

  // Start recording
  const startRecording = useCallback(async () => {
    if (state.recording || !connected) return;

    try {
      const recorder = new AudioRecorder();

      // Set up chunk callback to send audio data via WebSocket
      recorder.onChunk = (base64Chunk: string) => {
        request('voice', 'audio_chunk', {
          audio: base64Chunk,
          format: 'pcm_16bit',
          sample_rate: 16000,
        }).catch(() => {
          // Ignore send errors during recording
        });
      };

      await recorder.start();
      recorderRef.current = recorder;

      // Notify backend that recording started
      await request('voice', 'start_recording', {
        sample_rate: 16000,
        channels: 1,
        format: 'pcm_16bit',
      });

      setState(prev => ({
        ...prev,
        recording: true,
        transcription: '',
        audioLevel: 0,
      }));

      // Start level monitoring
      levelAnimRef.current = requestAnimationFrame(updateLevel);
    } catch (err: any) {
      console.error('[Voice] Failed to start recording:', err);
      setState(prev => ({
        ...prev,
        recording: false,
      }));
    }
  }, [state.recording, connected, request, updateLevel]);

  // Stop recording
  const stopRecording = useCallback(async () => {
    if (!state.recording) return;

    // Stop level animation
    if (levelAnimRef.current) {
      cancelAnimationFrame(levelAnimRef.current);
      levelAnimRef.current = undefined;
    }

    // Stop recorder
    if (recorderRef.current) {
      recorderRef.current.stop();
      recorderRef.current = null;
    }

    setState(prev => ({
      ...prev,
      recording: false,
      audioLevel: 0,
    }));

    // Notify backend
    if (connected) {
      try {
        await request('voice', 'stop_recording');
      } catch {
        // Ignore errors on stop
      }
    }
  }, [state.recording, connected, request]);

  // Text-to-speech
  const speak = useCallback(async (text: string) => {
    if (!connected || !text.trim()) return;
    try {
      await request('voice', 'tts_speak', { text: text.trim() });
    } catch (err: any) {
      console.error('[Voice] TTS error:', err);
    }
  }, [connected, request]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (levelAnimRef.current) {
        cancelAnimationFrame(levelAnimRef.current);
      }
      if (recorderRef.current) {
        recorderRef.current.stop();
        recorderRef.current = null;
      }
    };
  }, []);

  return {
    recording: state.recording,
    transcription: state.transcription,
    audioLevel: state.audioLevel,
    startRecording,
    stopRecording,
    speak,
  };
}
