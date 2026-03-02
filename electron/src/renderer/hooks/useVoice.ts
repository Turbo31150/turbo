import { useState, useEffect, useCallback, useRef } from 'react';
import { useWebSocket, WsMessage } from './useWebSocket';
import { AudioRecorder } from '../lib/audio';

interface VoiceState {
  recording: boolean;
  transcription: string;
  audioLevel: number;
  speaking: boolean;
}

export function useVoice() {
  const [state, setState] = useState<VoiceState>({
    recording: false,
    transcription: '',
    audioLevel: 0,
    speaking: false,
  });
  const { connected, request, subscribe } = useWebSocket();
  const recorderRef = useRef<AudioRecorder | null>(null);
  const levelAnimRef = useRef<number | undefined>(undefined);
  const recordingRef = useRef(false);

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
          setState(prev => ({ ...prev, speaking: true }));
          break;
        }

        case 'tts_finished': {
          setState(prev => ({ ...prev, speaking: false }));
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

  // Update audio level at ~15fps instead of 60fps to reduce re-renders
  const lastLevelUpdate = useRef(0);
  const updateLevel = useCallback(() => {
    if (!recordingRef.current) return;
    const now = performance.now();
    if (recorderRef.current && now - lastLevelUpdate.current > 66) {
      const level = recorderRef.current.getLevel();
      setState(prev => prev.audioLevel === level ? prev : { ...prev, audioLevel: level });
      lastLevelUpdate.current = now;
    }
    levelAnimRef.current = requestAnimationFrame(updateLevel);
  }, []);

  // Start recording
  const startRecording = useCallback(async () => {
    if (recordingRef.current || !connected) return;

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

      recordingRef.current = true;
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
      recordingRef.current = false;
      setState(prev => ({
        ...prev,
        recording: false,
      }));
    }
  }, [connected, request, updateLevel]);

  // Stop recording
  const stopRecording = useCallback(async () => {
    if (!recordingRef.current) return;

    // Stop level animation
    if (levelAnimRef.current) {
      cancelAnimationFrame(levelAnimRef.current);
      levelAnimRef.current = undefined;
    }

    // Stop recorder (triggers flush of remaining audio)
    if (recorderRef.current) {
      recorderRef.current.stop();
      recorderRef.current = null;
    }

    recordingRef.current = false;
    setState(prev => ({
      ...prev,
      recording: false,
      audioLevel: 0,
    }));

    // Wait for AudioWorklet flush to complete before stopping backend
    await new Promise(resolve => setTimeout(resolve, 120));

    // Notify backend and retrieve transcription from response
    if (connected) {
      try {
        const resp = await request('voice', 'stop_recording');
        const entry = resp?.payload?.transcription;
        if (entry) {
          const text = entry.corrected || entry.original || '';
          if (text && !text.startsWith('[')) {
            setState(prev => ({ ...prev, transcription: text }));
          }
        }
      } catch {
        // Ignore errors on stop
      }
    }
  }, [connected, request]);

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
    speaking: state.speaking,
    startRecording,
    stopRecording,
    speak,
  };
}
