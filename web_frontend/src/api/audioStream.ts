// Audio Streaming Client for FastAPI Server-Side STT (/ws/audio)
// Streams raw microphone audio chunks to server-side Whisper / Faster-Whisper pipeline
// Emits partial and final transcription events without client-side model dependencies.

import { api } from './client';

export interface AudioStreamCallbacks {
  onPartialText?: (partial: string) => void;
  onFinalText?: (final: string) => void;
  onError?: (error: string) => void;
  onStatusChange?: (status: 'idle' | 'connecting' | 'streaming' | 'processing' | 'error') => void;
}

export class AudioStreamClient {
  private ws: WebSocket | null = null;
  private mediaStream: MediaStream | null = null;
  private mediaRecorder: MediaRecorder | null = null;
  private isRecording = false;
  private callbacks: AudioStreamCallbacks;

  constructor(callbacks: AudioStreamCallbacks = {}) {
    this.callbacks = callbacks;
  }

  setCallbacks(callbacks: AudioStreamCallbacks) {
    this.callbacks = { ...this.callbacks, ...callbacks };
  }

  async startStreaming(): Promise<boolean> {
    if (this.isRecording) return true;

    try {
      this.callbacks.onStatusChange?.('connecting');

      // 1. Request microphone access
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('Microphone access is not supported by your browser.');
      }

      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
          sampleRate: 16000,
        },
      });

      // 2. Determine WebSocket URL for /ws/audio
      const baseUrl = api.getBackendUrl();
      let wsUrl = baseUrl.replace(/^http/, 'ws');
      if (!wsUrl.includes('/ws/audio')) {
        wsUrl = `${wsUrl.replace(/\/+$/, '')}/ws/audio`;
      }

      // 3. Connect to WebSocket
      try {
        this.ws = new WebSocket(wsUrl);
        this.ws.binaryType = 'arraybuffer';
      } catch (wsErr: any) {
        console.warn('[AudioStream] Direct WS failed, falling back to simulation/web speech:', wsErr);
        this.startFallbackRecognition();
        return true;
      }

      this.ws.onopen = () => {
        console.log('[AudioStream] Connected to /ws/audio stream');
        this.callbacks.onStatusChange?.('streaming');
        this.startMediaRecorder();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'stt_partial' || data.type === 'partial') {
            this.callbacks.onPartialText?.(data.text || '');
          } else if (data.type === 'stt_final' || data.type === 'final') {
            this.callbacks.onFinalText?.(data.text || '');
            this.stopStreaming();
          } else if (data.type === 'stt_error' || data.type === 'error') {
            this.callbacks.onError?.(data.message || 'STT processing error');
          }
        } catch {
          // If server returns raw text
          if (typeof event.data === 'string') {
            this.callbacks.onPartialText?.(event.data);
          }
        }
      };

      this.ws.onerror = () => {
        console.warn('[AudioStream] WS error, switching to Web Speech fallback');
        this.cleanupWebSocket();
        this.startFallbackRecognition();
      };

      this.ws.onclose = () => {
        if (this.isRecording) {
          this.callbacks.onStatusChange?.('idle');
          this.isRecording = false;
        }
      };

      this.isRecording = true;
      return true;
    } catch (err: any) {
      console.error('[AudioStream] Start failed:', err);
      this.callbacks.onError?.(err.message || 'Failed to start audio stream');
      this.callbacks.onStatusChange?.('error');
      this.stopStreaming();
      return false;
    }
  }

  private startMediaRecorder() {
    if (!this.mediaStream) return;

    try {
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')
        ? 'audio/ogg;codecs=opus'
        : '';

      this.mediaRecorder = new MediaRecorder(this.mediaStream, mimeType ? { mimeType } : undefined);

      this.mediaRecorder.ondataavailable = async (e) => {
        if (e.data && e.data.size > 0 && this.ws && this.ws.readyState === WebSocket.OPEN) {
          const arrayBuffer = await e.data.arrayBuffer();
          this.ws.send(arrayBuffer);
        }
      };

      // Stream chunks every 250ms for low latency
      this.mediaRecorder.start(250);
    } catch (err) {
      console.warn('[AudioStream] MediaRecorder error, falling back:', err);
      this.startFallbackRecognition();
    }
  }

  // Fallback for browsers or offline previews without active FastAPI /ws/audio server
  private startFallbackRecognition() {
    this.callbacks.onStatusChange?.('streaming');
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      this.callbacks.onError?.('Local speech recognition not supported in browser.');
      this.callbacks.onStatusChange?.('idle');
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = 'hi-IN'; // Default Hinglish / Indian English
      recognition.interimResults = true;
      recognition.continuous = false;

      recognition.onresult = (event: any) => {
        let interim = '';
        let final = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            final += event.results[i][0].transcript;
          } else {
            interim += event.results[i][0].transcript;
          }
        }
        if (interim) {
          this.callbacks.onPartialText?.(interim);
        }
        if (final) {
          this.callbacks.onFinalText?.(final);
          this.stopStreaming();
        }
      };

      recognition.onerror = (e: any) => {
        console.warn('[AudioStream] Fallback speech error:', e);
        this.callbacks.onError?.('Speech recognition timed out');
        this.stopStreaming();
      };

      recognition.onend = () => {
        this.stopStreaming();
      };

      recognition.start();
    } catch (e: any) {
      this.callbacks.onError?.(e.message || 'Speech recognition initialization failed');
      this.stopStreaming();
    }
  }

  stopStreaming() {
    this.isRecording = false;
    this.callbacks.onStatusChange?.('idle');

    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      try {
        this.mediaRecorder.stop();
      } catch {}
    }
    this.mediaRecorder = null;

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((t) => t.stop());
      this.mediaStream = null;
    }

    this.cleanupWebSocket();
  }

  private cleanupWebSocket() {
    if (this.ws) {
      if (this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({ type: 'stream_end' }));
          this.ws.close();
        } catch {}
      }
      this.ws = null;
    }
  }

  getIsStreaming(): boolean {
    return this.isRecording;
  }
}
