import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Play,
  Pause,
  RotateCcw,
  Square,
  Globe,
  Navigation,
  AlertTriangle,
  Send,
  Sparkles,
  ChevronRight,
  HelpCircle,
  X,
  RefreshCw,
  Edit2,
  Check,
  Radio,
  Footprints,
  TrainTrack,
  Bus,
} from 'lucide-react';
import {
  voiceService,
  SUPPORTED_VOICE_LANGUAGES,
  VoiceLanguageCode,
} from '../services/voiceService';
import {
  SafarSetuAPI,
  VoiceQueryResponse,
  VoiceStepGuidance,
  Journey,
  PlanRouteParams,
} from '../lib/api';

interface VoiceAssistantModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeJourney?: Journey | null;
  activeLegIndex?: number | null;
  onPlanRoute?: (params: PlanRouteParams) => void;
  onApplyReroute?: (plan: any) => void;
  onSelectLeg?: (legIndex: number) => void;
}

export const VoiceAssistantModal: React.FC<VoiceAssistantModalProps> = ({
  isOpen,
  onClose,
  activeJourney = null,
  activeLegIndex = 0,
  onPlanRoute,
  onApplyReroute,
  onSelectLeg,
}) => {
  const [selectedLanguage, setSelectedLanguage] = useState<VoiceLanguageCode>('auto');
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isMuted, setIsMuted] = useState(voiceService.isMuted);

  const [transcript, setTranscript] = useState('');
  const [editableTranscript, setEditableTranscript] = useState('');
  const [isEditingTranscript, setIsEditingTranscript] = useState(false);
  const [lastResponse, setLastResponse] = useState<VoiceQueryResponse | null>(null);
  const [stepGuidance, setStepGuidance] = useState<VoiceStepGuidance | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>('Ready to listen. Tap the microphone to start.');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const transcriptInputRef = useRef<HTMLInputElement>(null);

  // Sync step guidance when active leg changes in navigation
  useEffect(() => {
    if (activeJourney && activeJourney.legs && activeJourney.legs.length > 0) {
      const idx = activeLegIndex !== null && activeLegIndex !== undefined ? activeLegIndex : 0;
      fetchStepGuidance(activeJourney, idx);
    }
  }, [activeJourney, activeLegIndex]);

  // Clean up voice upon modal close
  useEffect(() => {
    if (!isOpen) {
      voiceService.stopListening();
      voiceService.stopSpeaking();
      setIsListening(false);
      setIsSpeaking(false);
    }
  }, [isOpen]);

  const fetchStepGuidance = async (journey: Journey, legIdx: number) => {
    try {
      const guidance = await SafarSetuAPI.getVoiceStepGuidance({
        journey,
        leg_index: legIdx,
        target_language: selectedLanguage === 'auto' ? 'en' : selectedLanguage,
      });
      setStepGuidance(guidance);
    } catch (err) {
      console.warn('Could not fetch step guidance:', err);
    }
  };

  const handleStartListening = () => {
    setErrorMessage(null);
    setTranscript('');
    setEditableTranscript('');
    setIsEditingTranscript(false);

    const isSupported = voiceService.isSpeechRecognitionSupported();
    if (!isSupported) {
      setErrorMessage(
        'Speech Recognition is not supported by your browser. Please type your query below or use Chrome/Edge/Safari.'
      );
      return;
    }

    setIsListening(true);
    setStatusMessage('Listening to your voice... Speak naturally.');

    voiceService.startListening({
      lang: selectedLanguage === 'auto' ? 'en-IN' : selectedLanguage,
      onStart: () => {
        setIsListening(true);
        setStatusMessage('Listening... (Hindi, English, Hinglish supported)');
      },
      onInterimResult: (text) => {
        setTranscript(text);
        setEditableTranscript(text);
      },
      onFinalResult: (finalText) => {
        setIsListening(false);
        setTranscript(finalText);
        setEditableTranscript(finalText);
        setStatusMessage('Speech recognized. Processing transit request...');
        processVoiceQuery(finalText);
      },
      onError: (err) => {
        setIsListening(false);
        setErrorMessage(err);
        setStatusMessage('Listening stopped. Tap the microphone to retry or type below.');
      },
      onEnd: () => {
        setIsListening(false);
      },
    });
  };

  const handleStopListening = () => {
    voiceService.stopListening();
    setIsListening(false);
    if (transcript.trim()) {
      processVoiceQuery(transcript.trim());
    } else {
      setStatusMessage('Listening stopped.');
    }
  };

  const processVoiceQuery = async (queryText: string) => {
    if (!queryText.trim()) return;

    setIsProcessing(true);
    setErrorMessage(null);
    setStatusMessage('Analyzing intent and searching transit routes...');

    try {
      const res = await SafarSetuAPI.sendVoiceQuery({
        query: queryText.trim(),
        language: selectedLanguage,
        target_language: selectedLanguage,
        current_journey: activeJourney,
        current_leg_index: activeLegIndex,
      });

      setLastResponse(res);
      setIsProcessing(false);
      setStatusMessage(`Detected: ${res.detected_language.toUpperCase()} • Intent: ${res.intent}`);

      // If backend returned planned route, trigger application handler
      if (res.action === 'NAVIGATE' && res.planned_route && onPlanRoute) {
        if (res.planned_route.journeys && res.planned_route.journeys.length > 0) {
          onPlanRoute({
            origin_stop_id: res.planned_route.origin_stop_id,
            destination_stop_id: res.planned_route.destination_stop_id,
            departure_date: res.planned_route.departure_date,
            departure_time: res.planned_route.requested_time,
            criterion: (res.entities?.criterion as any) || 'fastest',
            mode_preference: res.entities?.mode || 'all',
          });
        }
      }

      // If emergency reroute triggered, apply rerouted journeys
      if (res.action === 'REROUTE' && res.planned_route && onApplyReroute) {
        onApplyReroute(res.planned_route);
      }

      // If step guidance returned, update active step
      if (res.step_guidance) {
        setStepGuidance(res.step_guidance);
      }

      // Speak response verbally
      if (res.spoken_text && !isMuted) {
        speakResponse(res.spoken_text, res.response_language);
      }
    } catch (err: any) {
      setIsProcessing(false);
      setErrorMessage(err.message || 'Failed to process voice request. Please try again.');
      setStatusMessage('Request error. Please check your network connection.');
    }
  };

  const speakResponse = (text: string, langCode: string) => {
    setIsSpeaking(true);
    voiceService.speak({
      text,
      lang: langCode,
      onStart: () => setIsSpeaking(true),
      onEnd: () => setIsSpeaking(false),
      onError: () => setIsSpeaking(false),
    });
  };

  const handleToggleMute = () => {
    const muted = voiceService.toggleMute();
    setIsMuted(muted);
    if (muted) {
      setIsSpeaking(false);
    }
  };

  const handleReplaySpeech = () => {
    if (lastResponse?.spoken_text) {
      speakResponse(lastResponse.spoken_text, lastResponse.response_language);
    } else if (stepGuidance?.spoken_instruction) {
      speakResponse(stepGuidance.spoken_instruction, selectedLanguage);
    }
  };

  const handleStopSpeech = () => {
    voiceService.stopSpeaking();
    setIsSpeaking(false);
  };

  const handleEditSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsEditingTranscript(false);
    if (editableTranscript.trim()) {
      setTranscript(editableTranscript.trim());
      processVoiceQuery(editableTranscript.trim());
    }
  };

  const handleQuickPromptClick = (prompt: string) => {
    setTranscript(prompt);
    setEditableTranscript(prompt);
    processVoiceQuery(prompt);
  };

  const handleAnnounceNextStep = () => {
    if (activeJourney && activeJourney.legs) {
      const nextIdx = (activeLegIndex || 0) + 1;
      if (nextIdx < activeJourney.legs.length) {
        onSelectLeg?.(nextIdx);
        fetchStepGuidance(activeJourney, nextIdx);
        processVoiceQuery("What's my next stop?");
      } else {
        const arrivalMsg = "You are on the final leg of your journey. Approaching destination.";
        speakResponse(arrivalMsg, selectedLanguage);
      }
    } else {
      processVoiceQuery("What's my next stop?");
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop voice-assistant-backdrop" onClick={onClose}>
      <div
        className="modal-card voice-assistant-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="SafarSetu AI Multilingual Voice Assistant"
      >
        {/* Header */}
        <div className="voice-modal-header">
          <div className="voice-header-title-box">
            <div className="voice-avatar-glow">
              <Sparkles size={20} className="glow-sparkle" />
            </div>
            <div>
              <h3 className="voice-title">SafarSetu Voice Assistant</h3>
              <p className="voice-subtitle">Spoken Navigation • Hindi • Hinglish • English</p>
            </div>
          </div>

          <div className="voice-header-actions">
            {/* Language Switcher */}
            <div className="voice-lang-select-wrapper">
              <Globe size={14} className="lang-icon" />
              <select
                aria-label="Select voice language"
                value={selectedLanguage}
                onChange={(e) => {
                  const val = e.target.value as VoiceLanguageCode;
                  setSelectedLanguage(val);
                  voiceService.stopSpeaking();
                }}
                className="voice-lang-select"
              >
                <option value="auto">🌐 Auto-Detect</option>
                {SUPPORTED_VOICE_LANGUAGES.map((l) => (
                  <option key={l.langCode} value={l.langCode}>
                    {l.nativeLabel} ({l.label})
                  </option>
                ))}
              </select>
            </div>

            {/* Mute Button */}
            <button
              type="button"
              className={`btn-voice-control ${isMuted ? 'muted' : ''}`}
              onClick={handleToggleMute}
              title={isMuted ? 'Unmute voice output' : 'Mute voice output'}
              aria-label={isMuted ? 'Unmute' : 'Mute'}
            >
              {isMuted ? <VolumeX size={18} color="#ef4444" /> : <Volume2 size={18} />}
            </button>

            {/* Close Button */}
            <button
              type="button"
              className="btn-icon-close"
              onClick={onClose}
              title="Close Voice Assistant"
              aria-label="Close"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="voice-modal-content">
          {/* Main Visualizer & Mic Section */}
          <div className="voice-mic-hero-section">
            <div className="voice-visualizer-container">
              {/* Animated Equalizer Wave Bars */}
              <div className={`sound-wave-bars ${isListening ? 'active-listening' : isSpeaking ? 'active-speaking' : ''}`}>
                <span className="bar bar-1"></span>
                <span className="bar bar-2"></span>
                <span className="bar bar-3"></span>
                <span className="bar bar-4"></span>
                <span className="bar bar-5"></span>
              </div>

              {/* Big Circular Pulsing Mic Button */}
              <button
                type="button"
                className={`voice-big-mic-btn ${isListening ? 'listening' : isProcessing ? 'processing' : isSpeaking ? 'speaking' : ''}`}
                onClick={isListening ? handleStopListening : handleStartListening}
                title={isListening ? 'Tap to stop listening' : 'Tap to speak'}
                aria-label={isListening ? 'Stop listening' : 'Start voice navigation'}
                disabled={isProcessing}
              >
                {isProcessing ? (
                  <RefreshCw size={36} className="spin-icon" />
                ) : isListening ? (
                  <Square size={32} className="pulse-stop" />
                ) : (
                  <Mic size={38} className="mic-icon" />
                )}
              </button>
            </div>

            {/* Status Indicator */}
            <div className="voice-status-badge-row">
              <span
                className={`voice-status-pill ${
                  isListening
                    ? 'status-listening'
                    : isProcessing
                    ? 'status-processing'
                    : isSpeaking
                    ? 'status-speaking'
                    : 'status-idle'
                }`}
              >
                <Radio size={12} className={isListening || isSpeaking ? 'pulse-dot' : ''} />
                {isListening
                  ? 'Listening...'
                  : isProcessing
                  ? 'Processing Route...'
                  : isSpeaking
                  ? 'Speaking...'
                  : 'Ready'}
              </span>
              <p className="voice-status-text">{statusMessage}</p>
            </div>
          </div>

          {/* Error Notice */}
          {errorMessage && (
            <div className="voice-error-box">
              <AlertTriangle size={16} className="error-icon" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Transcript / Spoken Input Display */}
          {(transcript || isEditingTranscript) && (
            <div className="voice-transcript-card">
              <div className="transcript-header">
                <span className="transcript-label">Recognized Speech:</span>
                {!isEditingTranscript ? (
                  <button
                    type="button"
                    className="btn-edit-text"
                    onClick={() => {
                      setIsEditingTranscript(true);
                      setTimeout(() => transcriptInputRef.current?.focus(), 50);
                    }}
                    title="Correct text manually"
                  >
                    <Edit2 size={13} /> Edit
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-edit-text save"
                    onClick={handleEditSubmit}
                    title="Confirm edited text"
                  >
                    <Check size={13} /> Done
                  </button>
                )}
              </div>

              {isEditingTranscript ? (
                <form onSubmit={handleEditSubmit} className="transcript-edit-form">
                  <input
                    ref={transcriptInputRef}
                    type="text"
                    value={editableTranscript}
                    onChange={(e) => setEditableTranscript(e.target.value)}
                    className="transcript-input"
                    placeholder="Correct location or route name..."
                  />
                  <button type="submit" className="btn-send-edit" title="Send query">
                    <Send size={15} />
                  </button>
                </form>
              ) : (
                <p className="transcript-text">"{transcript}"</p>
              )}
            </div>
          )}

          {/* Spoken AI Guidance / Response Display */}
          {lastResponse && (
            <div className="voice-response-card">
              <div className="response-header">
                <span className="response-badge">
                  <Sparkles size={13} /> SafarSetu Assistant
                </span>
                {lastResponse.detected_language && (
                  <span className="lang-badge">
                    {lastResponse.detected_language.toUpperCase()}
                  </span>
                )}
              </div>

              <div className="response-body">
                <p className="response-text">{lastResponse.spoken_text}</p>
                {lastResponse.display_text && lastResponse.display_text !== lastResponse.spoken_text && (
                  <div className="response-markdown-note">
                    {lastResponse.display_text}
                  </div>
                )}
              </div>

              {/* Spoken Audio Controls Bar */}
              <div className="voice-playback-bar">
                <button
                  type="button"
                  className="btn-playback"
                  onClick={handleReplaySpeech}
                  title="Replay Spoken Guidance"
                >
                  <RotateCcw size={14} /> Replay
                </button>
                {isSpeaking ? (
                  <button
                    type="button"
                    className="btn-playback stop"
                    onClick={handleStopSpeech}
                    title="Stop Audio"
                  >
                    <Square size={14} /> Stop
                  </button>
                ) : null}
              </div>
            </div>
          )}

          {/* Step-by-Step Navigation Guidance Card (Active Journey Mode) */}
          {stepGuidance && (
            <div className="voice-step-guidance-card">
              <div className="step-guidance-header">
                <div className="step-count-pill">
                  <Navigation size={13} />
                  <span>
                    Step {stepGuidance.step_number} of {stepGuidance.total_steps}
                  </span>
                </div>
                <span className="step-type-pill">
                  {stepGuidance.step_type === 'walk' ? (
                    <>
                      <Footprints size={12} /> Walking
                    </>
                  ) : stepGuidance.step_type === 'board_metro' ? (
                    <>
                      <TrainTrack size={12} /> Metro Boarding
                    </>
                  ) : stepGuidance.step_type === 'transfer' ? (
                    <>
                      <RefreshCw size={12} /> Metro Interchange
                    </>
                  ) : (
                    <>
                      <Bus size={12} /> Transit
                    </>
                  )}
                </span>
              </div>

              <p className="step-instruction-text">{stepGuidance.spoken_instruction}</p>

              <div className="step-meta-row">
                <span className="step-stop-badge">📍 {stepGuidance.stop_name}</span>
                {stepGuidance.line_name && (
                  <span className="step-line-badge">🚆 {stepGuidance.line_name}</span>
                )}
                {stepGuidance.headsign && (
                  <span className="step-headsign-badge">Towards: {stepGuidance.headsign}</span>
                )}
                {stepGuidance.fare_inr !== undefined && stepGuidance.fare_inr !== null && (
                  <span className="step-fare-badge">₹{stepGuidance.fare_inr} Fare</span>
                )}
              </div>

              <div className="step-nav-actions">
                <button
                  type="button"
                  className="btn-nav-step"
                  onClick={handleAnnounceNextStep}
                >
                  <span>Announce Next Stop</span>
                  <ChevronRight size={15} />
                </button>
              </div>
            </div>
          )}

          {/* Quick Voice Prompt Suggestions */}
          <div className="voice-prompts-section">
            <span className="prompts-label">Try asking:</span>
            <div className="prompts-chips-grid">
              <button
                type="button"
                className="prompt-chip"
                onClick={() => handleQuickPromptClick('Take me from New Delhi Railway Station to India Gate using the cheapest route')}
              >
                🚇 "New Delhi to India Gate (cheapest route)"
              </button>
              <button
                type="button"
                className="prompt-chip"
                onClick={() => handleQuickPromptClick('मुझे कुतुब मीनार जाना है, सबसे सस्ता रूट बताओ')}
              >
                🇮🇳 "मुझे कुतुब मीनार जाना है, सबसे सस्ता रूट बताओ"
              </button>
              <button
                type="button"
                className="prompt-chip"
                onClick={() => handleQuickPromptClick("What's my next stop?")}
              >
                📍 "What's my next stop?"
              </button>
              <button
                type="button"
                className="prompt-chip"
                onClick={() => handleQuickPromptClick('How much will this route cost?')}
              >
                💳 "How much will this route cost?"
              </button>
              <button
                type="button"
                className="prompt-chip prompt-chip-emergency"
                onClick={() => handleQuickPromptClick("I missed my metro stop. Help me reach my destination.")}
              >
                🚨 "I missed my metro stop (Reroute me)"
              </button>
              <button
                type="button"
                className="prompt-chip"
                onClick={() => handleQuickPromptClick('Explain that in Hindi')}
              >
                🗣️ "Explain that in Hindi"
              </button>
            </div>
          </div>
        </div>

        {/* Text Typing Fallback Bar */}
        <div className="voice-modal-footer">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (editableTranscript.trim()) {
                setTranscript(editableTranscript.trim());
                processVoiceQuery(editableTranscript.trim());
              }
            }}
            className="voice-text-fallback-form"
          >
            <input
              type="text"
              className="voice-fallback-input"
              placeholder="Or type your transit question here..."
              value={editableTranscript}
              onChange={(e) => setEditableTranscript(e.target.value)}
              disabled={isProcessing}
            />
            <button
              type="submit"
              className="btn-voice-send"
              disabled={!editableTranscript.trim() || isProcessing}
              title="Send query"
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

