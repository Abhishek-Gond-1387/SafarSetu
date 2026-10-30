/**
 * SafarSetu Voice Service.
 *
 * Implements:
 * 1. Multilingual Speech-to-Text (STT) via Web Speech API with automatic detection
 *    and fallback handling for en-IN, hi-IN, Hinglish.
 * 2. Multilingual Text-to-Speech (TTS) via Web Speech Synthesis with natural Indian voices,
 *    playback controls (Play, Pause, Stop, Replay, Mute), and overlap prevention.
 */

// Define SpeechRecognition interface for TypeScript
interface IWindowSpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
}

declare global {
  interface Window {
    SpeechRecognition?: { new (): IWindowSpeechRecognition };
    webkitSpeechRecognition?: { new (): IWindowSpeechRecognition };
  }
}

export type VoiceLanguageCode = 'en' | 'hi' | 'hinglish' | 'fr' | 'es' | 'de' | 'auto';

export interface VoiceConfig {
  langCode: VoiceLanguageCode;
  speechLocale: string; // e.g. "en-IN", "hi-IN", "fr-FR"
  label: string;
  nativeLabel: string;
}

export const SUPPORTED_VOICE_LANGUAGES: VoiceConfig[] = [
  { langCode: 'en', speechLocale: 'en-IN', label: 'English (India)', nativeLabel: 'English' },
  { langCode: 'hi', speechLocale: 'hi-IN', label: 'Hindi', nativeLabel: 'हिन्दी' },
  { langCode: 'hinglish', speechLocale: 'hi-IN', label: 'Hinglish', nativeLabel: 'Hinglish' },
  { langCode: 'fr', speechLocale: 'fr-FR', label: 'French', nativeLabel: 'Français' },
  { langCode: 'es', speechLocale: 'es-ES', label: 'Spanish', nativeLabel: 'Español' },
  { langCode: 'de', speechLocale: 'de-DE', label: 'German', nativeLabel: 'Deutsch' },
];

class VoiceService {
  private recognition: IWindowSpeechRecognition | null = null;
  private currentUtterance: SpeechSynthesisUtterance | null = null;
  private isListeningInternal = false;
  private isMutedInternal = false;
  private lastSpokenText: string = '';
  private lastSpokenLang: string = 'en';

  constructor() {
    if (typeof window !== 'undefined') {
      const SpeechClass = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechClass) {
        try {
          this.recognition = new SpeechClass();
          this.recognition.continuous = false;
          this.recognition.interimResults = true;
        } catch (e) {
          console.warn('[VoiceService] SpeechRecognition init failed:', e);
        }
      }
    }
  }

  public isSpeechRecognitionSupported(): boolean {
    return !!(typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition));
  }

  public isSpeechSynthesisSupported(): boolean {
    return !!(typeof window !== 'undefined' && window.speechSynthesis);
  }

  public get isListening(): boolean {
    return this.isListeningInternal;
  }

  public get isMuted(): boolean {
    return this.isMutedInternal;
  }

  public toggleMute(): boolean {
    this.isMutedInternal = !this.isMutedInternal;
    if (this.isMutedInternal) {
      this.stopSpeaking();
    }
    return this.isMutedInternal;
  }

  public setMute(muted: boolean): void {
    this.isMutedInternal = muted;
    if (muted) {
      this.stopSpeaking();
    }
  }

  /**
   * Start listening for microphone speech input.
   */
  public startListening({
    lang = 'en-IN',
    onInterimResult,
    onFinalResult,
    onError,
    onStart,
    onEnd,
  }: {
    lang?: string;
    onInterimResult?: (transcript: string) => void;
    onFinalResult: (transcript: string) => void;
    onError: (errorMessage: string) => void;
    onStart?: () => void;
    onEnd?: () => void;
  }): void {
    if (!this.recognition) {
      onError('Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari, or type your query.');
      return;
    }

    // Cancel any active speech output so audio does not feedback into mic
    this.stopSpeaking();

    // Map language code to BCP-47 locale
    let locale = lang;
    if (lang === 'hi' || lang === 'hinglish') locale = 'hi-IN';
    else if (lang === 'en' || lang === 'auto') locale = 'en-IN';
    else if (lang === 'fr') locale = 'fr-FR';
    else if (lang === 'es') locale = 'es-ES';
    else if (lang === 'de') locale = 'de-DE';

    this.recognition.lang = locale;

    this.recognition.onstart = () => {
      this.isListeningInternal = true;
      onStart?.();
    };

    this.recognition.onresult = (event: any) => {
      let interim = '';
      let final = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const item = event.results[i];
        const text = item[0]?.transcript || '';
        if (item.isFinal) {
          final += text;
        } else {
          interim += text;
        }
      }

      if (interim && onInterimResult) {
        onInterimResult(interim);
      }
      if (final) {
        this.isListeningInternal = false;
        onFinalResult(final.trim());
      }
    };

    this.recognition.onerror = (event: any) => {
      this.isListeningInternal = false;
      let msg = 'Could not capture speech.';
      if (event.error === 'not-allowed') {
        msg = 'Microphone permission was denied. Please allow microphone access in your browser settings to use voice commands.';
      } else if (event.error === 'no-speech') {
        msg = 'No speech detected. Please try speaking again.';
      } else if (event.error === 'network') {
        msg = 'Network issue with speech recognition service. Please check your connection or type your query.';
      } else if (event.error === 'audio-capture') {
        msg = 'No microphone was found on your device.';
      }
      onError(msg);
      onEnd?.();
    };

    this.recognition.onend = () => {
      this.isListeningInternal = false;
      onEnd?.();
    };

    try {
      this.recognition.start();
    } catch (e: any) {
      console.warn('[VoiceService] recognition.start error, trying abort and restart:', e);
      try {
        this.recognition.abort();
        setTimeout(() => this.recognition?.start(), 100);
      } catch (err) {
        onError('Could not start microphone. Please try again.');
        onEnd?.();
      }
    }
  }

  /**
   * Stop speech recognition manually.
   */
  public stopListening(): void {
    if (this.recognition && this.isListeningInternal) {
      try {
        this.recognition.stop();
      } catch (e) {
        // ignore
      }
    }
    this.isListeningInternal = false;
  }

  /**
   * Speak a response aloud using natural speech synthesis.
   */
  public speak({
    text,
    lang = 'en',
    rate = 1.0,
    pitch = 1.0,
    onStart,
    onEnd,
    onError,
  }: {
    text: string;
    lang?: string;
    rate?: number;
    pitch?: number;
    onStart?: () => void;
    onEnd?: () => void;
    onError?: (err: any) => void;
  }): void {
    if (this.isMutedInternal || !this.isSpeechSynthesisSupported()) {
      onEnd?.();
      return;
    }

    // Clean text of markdown asterisks or badges for smooth verbal pronunciation
    const cleanText = text
      .replace(/[*_~`#]/g, '')
      .replace(/₹/g, 'Rupees ')
      .replace(/➔/g, 'to')
      .replace(/→/g, 'to')
      .replace(/\s+/g, ' ')
      .trim();

    if (!cleanText) {
      onEnd?.();
      return;
    }

    // Cancel any current utterance to prevent audio overlap
    this.stopSpeaking();

    this.lastSpokenText = cleanText;
    this.lastSpokenLang = lang;

    const utterance = new SpeechSynthesisUtterance(cleanText);

    // Map language code to voice selector
    let targetLocale = 'en-IN';
    if (lang === 'hi' || lang === 'hinglish') {
      targetLocale = 'hi-IN';
      utterance.rate = 0.95; // slightly slower for clear Hindi pronunciation
    } else if (lang === 'fr') {
      targetLocale = 'fr-FR';
    } else if (lang === 'es') {
      targetLocale = 'es-ES';
    } else if (lang === 'de') {
      targetLocale = 'de-DE';
    } else {
      targetLocale = 'en-IN';
      utterance.rate = rate;
    }

    utterance.lang = targetLocale;
    utterance.pitch = pitch;

    // Pick best matching voice available on system
    const voices = window.speechSynthesis.getVoices();
    if (voices && voices.length > 0) {
      const match =
        voices.find((v) => v.lang === targetLocale) ||
        voices.find((v) => v.lang.startsWith(targetLocale.split('-')[0])) ||
        voices.find((v) => v.lang.includes('IN') || v.lang.includes('en'));

      if (match) {
        utterance.voice = match;
      }
    }

    utterance.onstart = () => {
      this.currentUtterance = utterance;
      onStart?.();
    };

    utterance.onend = () => {
      this.currentUtterance = null;
      onEnd?.();
    };

    utterance.onerror = (e) => {
      this.currentUtterance = null;
      console.warn('[VoiceService] SpeechSynthesis error:', e);
      onError?.(e);
      onEnd?.();
    };

    try {
      window.speechSynthesis.speak(utterance);
    } catch (err) {
      console.error('[VoiceService] speak failed:', err);
      onEnd?.();
    }
  }

  /**
   * Pause ongoing speech synthesis.
   */
  public pause(): void {
    if (this.isSpeechSynthesisSupported() && window.speechSynthesis.speaking) {
      window.speechSynthesis.pause();
    }
  }

  /**
   * Resume paused speech synthesis.
   */
  public resume(): void {
    if (this.isSpeechSynthesisSupported() && window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
    }
  }

  /**
   * Stop and cancel all speech synthesis and listening immediately.
   */
  public stop(): void {
    this.stopSpeaking();
    this.stopListening();
  }

  /**
   * Stop and cancel all speech synthesis immediately.
   */
  public stopSpeaking(): void {
    if (this.isSpeechSynthesisSupported()) {
      try {
        window.speechSynthesis.cancel();
      } catch (e) {
        // ignore
      }
    }
    this.currentUtterance = null;
  }

  /**
   * Replay the last spoken guidance or statement.
   */
  public replay(onStart?: () => void, onEnd?: () => void): void {
    if (this.lastSpokenText) {
      this.speak({
        text: this.lastSpokenText,
        lang: this.lastSpokenLang,
        onStart,
        onEnd,
      });
    }
  }

  public isSpeaking(): boolean {
    return typeof window !== 'undefined' && !!window.speechSynthesis?.speaking;
  }

  public isPaused(): boolean {
    return typeof window !== 'undefined' && !!window.speechSynthesis?.paused;
  }
}

export const voiceService = new VoiceService();

