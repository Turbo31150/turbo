/**
 * AudioRecorder — Web Audio API based recorder for voice input
 *
 * Captures microphone audio at 16kHz mono, chunked every 250ms as base64 PCM.
 * Uses AudioWorkletNode when available, falls back to ScriptProcessorNode.
 * Flushes remaining samples on stop() to avoid losing tail audio.
 */

// AudioWorklet processor code (inline, registered at runtime)
const WORKLET_PROCESSOR_CODE = `
class ChunkProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
    this._sampleCount = 0;
    this._chunkSize = 4000; // 250ms at 16kHz

    // Listen for flush command from main thread
    this.port.onmessage = (e) => {
      if (e.data.type === 'flush' && this._buffer.length > 0) {
        const int16 = new Int16Array(this._buffer.length);
        for (let j = 0; j < this._buffer.length; j++) {
          const s = Math.max(-1, Math.min(1, this._buffer[j]));
          int16[j] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        this.port.postMessage({ type: 'chunk', samples: int16.buffer }, [int16.buffer]);
        this._buffer = [];
        this._sampleCount = 0;
      }
    };
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const samples = input[0];
    for (let i = 0; i < samples.length; i++) {
      this._buffer.push(samples[i]);
      this._sampleCount++;

      if (this._sampleCount >= this._chunkSize) {
        const int16 = new Int16Array(this._buffer.length);
        for (let j = 0; j < this._buffer.length; j++) {
          const s = Math.max(-1, Math.min(1, this._buffer[j]));
          int16[j] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        this.port.postMessage({
          type: 'chunk',
          samples: int16.buffer
        }, [int16.buffer]);

        this._buffer = [];
        this._sampleCount = 0;
      }
    }

    // Send RMS level
    let sum = 0;
    for (let i = 0; i < samples.length; i++) {
      sum += samples[i] * samples[i];
    }
    const rms = Math.sqrt(sum / samples.length);
    this.port.postMessage({ type: 'level', rms });

    return true;
  }
}

registerProcessor('chunk-processor', ChunkProcessor);
`;

export class AudioRecorder {
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private scriptNode: ScriptProcessorNode | null = null;
  private analyser: AnalyserNode | null = null;
  private currentLevel = 0;
  private active = false;
  // ScriptProcessor accumulated samples (class-level for flush access)
  private _spAccum: number[] = [];

  // Callback for audio chunks (base64 encoded PCM int16)
  public onChunk: ((base64: string) => void) | null = null;

  /**
   * Start recording from microphone.
   * Requests permission, sets up 16kHz mono audio pipeline.
   */
  async start(): Promise<void> {
    if (this.active) return;

    // Request microphone access
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    // Create AudioContext at 16kHz
    this.audioContext = new AudioContext({ sampleRate: 16000 });
    this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);

    // Create analyser for level metering
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 256;
    this.sourceNode.connect(this.analyser);

    // Try AudioWorklet first, fall back to ScriptProcessor
    const workletAvailable = await this.trySetupWorklet();
    if (!workletAvailable) {
      this.setupScriptProcessor();
    }

    this.active = true;
  }

  /**
   * Stop recording, flush remaining audio, release resources.
   */
  stop(): void {
    this.active = false;

    // Flush remaining samples before disconnecting
    if (this.workletNode) {
      // Ask worklet to emit its remaining buffer
      this.workletNode.port.postMessage({ type: 'flush' });
      // Small delay for the flush message to be processed (best-effort)
      setTimeout(() => {
        this.workletNode?.disconnect();
        this.workletNode = null;
      }, 50);
    }

    // Flush ScriptProcessor accumulated samples
    if (this._spAccum.length > 0 && this.onChunk) {
      const int16 = new Int16Array(this._spAccum.length);
      for (let j = 0; j < this._spAccum.length; j++) {
        const s = Math.max(-1, Math.min(1, this._spAccum[j]));
        int16[j] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      this.onChunk(this.arrayBufferToBase64(int16.buffer));
      this._spAccum = [];
    }

    if (this.scriptNode) {
      this.scriptNode.disconnect();
      this.scriptNode = null;
    }

    if (this.analyser) {
      this.analyser.disconnect();
      this.analyser = null;
    }

    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
      this.mediaStream = null;
    }

    if (this.audioContext) {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
    }

    this.currentLevel = 0;
  }

  /**
   * Get current RMS audio level (0-1) for visualizer.
   */
  getLevel(): number {
    if (!this.analyser || !this.active) return 0;

    const dataArray = new Float32Array(this.analyser.fftSize);
    this.analyser.getFloatTimeDomainData(dataArray);

    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i] * dataArray[i];
    }
    this.currentLevel = Math.sqrt(sum / dataArray.length);

    return Math.min(1, this.currentLevel * 3); // Amplify for visual feedback
  }

  // ---- Private methods ----

  private async trySetupWorklet(): Promise<boolean> {
    if (!this.audioContext || !this.sourceNode) return false;

    try {
      // Create a blob URL for the worklet processor
      const blob = new Blob([WORKLET_PROCESSOR_CODE], { type: 'application/javascript' });
      const workletUrl = URL.createObjectURL(blob);

      await this.audioContext.audioWorklet.addModule(workletUrl);
      URL.revokeObjectURL(workletUrl);

      this.workletNode = new AudioWorkletNode(this.audioContext, 'chunk-processor');

      this.workletNode.port.onmessage = (event) => {
        if (event.data.type === 'chunk' && this.onChunk) {
          const base64 = this.arrayBufferToBase64(event.data.samples);
          this.onChunk(base64);
        } else if (event.data.type === 'level') {
          this.currentLevel = event.data.rms;
        }
      };

      this.sourceNode.connect(this.workletNode);
      this.workletNode.connect(this.audioContext.destination);

      return true;
    } catch (err) {
      console.warn('[AudioRecorder] AudioWorklet not available, falling back to ScriptProcessor:', err);
      return false;
    }
  }

  private setupScriptProcessor(): void {
    if (!this.audioContext || !this.sourceNode) return;

    const bufferSize = 4096; // ~256ms at 16kHz
    this.scriptNode = this.audioContext.createScriptProcessor(bufferSize, 1, 1);

    const chunkSize = 4000; // 250ms at 16kHz

    this.scriptNode.onaudioprocess = (event: AudioProcessingEvent) => {
      if (!this.active) return;

      const inputData = event.inputBuffer.getChannelData(0);

      // Accumulate samples (class-level for flush access)
      for (let i = 0; i < inputData.length; i++) {
        this._spAccum.push(inputData[i]);
      }

      // Calculate level
      let sum = 0;
      for (let i = 0; i < inputData.length; i++) {
        sum += inputData[i] * inputData[i];
      }
      this.currentLevel = Math.sqrt(sum / inputData.length);

      // Emit full chunks
      while (this._spAccum.length >= chunkSize) {
        const chunk = this._spAccum.splice(0, chunkSize);

        // Convert float32 to int16
        const int16 = new Int16Array(chunk.length);
        for (let j = 0; j < chunk.length; j++) {
          const s = Math.max(-1, Math.min(1, chunk[j]));
          int16[j] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        if (this.onChunk) {
          const base64 = this.arrayBufferToBase64(int16.buffer);
          this.onChunk(base64);
        }
      }

      // Pass through silence (required for ScriptProcessor to keep running)
      const outputData = event.outputBuffer.getChannelData(0);
      for (let i = 0; i < outputData.length; i++) {
        outputData[i] = 0;
      }
    };

    this.sourceNode.connect(this.scriptNode);
    this.scriptNode.connect(this.audioContext.destination);
  }

  private arrayBufferToBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }
}
