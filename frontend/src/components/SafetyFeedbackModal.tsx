import React, { useState, useEffect } from 'react';
import {
  Shield,
  X,
  CheckCircle2,
  AlertTriangle,
  Moon,
  Sun,
  Footprints,
  TrainTrack,
  Bus,
  Car,
  Compass,
  ArrowRight,
  Loader2,
  Lock,
} from 'lucide-react';
import {
  SafarSetuAPI,
  Journey,
  JourneyLeg,
  SafetyExperience,
  SegmentType,
  TimeCategory,
} from '../lib/api';

export interface SafetyFeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  journey?: Journey | null;
  originName?: string;
  destinationName?: string;
  onSubmitted?: () => void;
  requireAuth?: () => void;
  isAuthenticated?: boolean;
}

const INFLUENCING_CONCERNS = [
  { key: 'poor_lighting', label: 'Poor street lighting', icon: '💡' },
  { key: 'isolated_location', label: 'Isolated location', icon: '👁️' },
  { key: 'harassment', label: 'Harassment / uncomfortable behavior', icon: '⚠️' },
  { key: 'poor_walking_conditions', label: 'Poor walking conditions', icon: '🚶‍♀️' },
  { key: 'uncomfortable_waiting_area', label: 'Uncomfortable waiting area', icon: '🪑' },
  { key: 'other', label: 'Other factors', icon: '📝' },
];

export const SafetyFeedbackModal: React.FC<SafetyFeedbackModalProps> = ({
  isOpen,
  onClose,
  journey,
  originName,
  destinationName,
  onSubmitted,
  requireAuth,
  isAuthenticated = false,
}) => {
  const [experience, setExperience] = useState<SafetyExperience>('comfortable');
  const [selectedSegmentType, setSelectedSegmentType] = useState<SegmentType>('entire_journey');
  const [selectedSegmentId, setSelectedSegmentId] = useState<string>('entire_journey');
  const [selectedSegmentName, setSelectedSegmentName] = useState<string>('Entire Journey');
  const [selectedConcerns, setSelectedConcerns] = useState<string[]>([]);
  const [feedbackText, setFeedbackText] = useState('');
  const [timeCategory, setTimeCategory] = useState<TimeCategory>('daytime');

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Auto-detect daytime vs nighttime on open
  useEffect(() => {
    if (isOpen) {
      const h = new Date().getHours();
      setTimeCategory(h >= 20 || h < 6 ? 'nighttime' : 'daytime');
      setSuccess(false);
      setErrorMsg(null);
      setFeedbackText('');
      setSelectedConcerns([]);
      setExperience('comfortable');
      setSelectedSegmentType('entire_journey');
      setSelectedSegmentId('entire_journey');
      setSelectedSegmentName('Entire Journey');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleToggleConcern = (key: string) => {
    setSelectedConcerns((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!isAuthenticated) {
      if (requireAuth) {
        requireAuth();
      } else {
        setErrorMsg('Please sign in to share community safety feedback.');
      }
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      const routeId = journey
        ? `route_${journey.legs?.[0]?.from_stop_id || originName}_${journey.legs?.[journey.legs.length - 1]?.to_stop_id || destinationName}`
        : originName && destinationName
        ? `route_${originName}_${destinationName}`
        : 'general_route';

      await SafarSetuAPI.submitSafetyFeedback({
        journey_id: journey ? `journey_${journey.departure_time || Date.now()}` : undefined,
        route_id: routeId,
        segment_id: selectedSegmentId,
        segment_type: selectedSegmentType,
        segment_name: selectedSegmentName,
        experience_rating: experience,
        safety_concerns: selectedConcerns,
        feedback_text: feedbackText.trim() ? feedbackText.trim() : undefined,
        time_category: timeCategory,
      });

      setSuccess(true);
      if (onSubmitted) onSubmitted();
      setTimeout(() => {
        onClose();
      }, 1600);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to submit feedback. You may have already reviewed this segment.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="lost-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="lost-modal-card herroute-feedback-modal"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '580px' }}
      >
        {/* Header */}
        <div
          className="lost-modal-header"
          style={{
            background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 60%, #4338ca 100%)',
            borderBottom: '2.5px solid #ec4899',
          }}
        >
          <div className="lost-header-left">
            <div
              className="lost-header-icon-box"
              style={{
                background: 'linear-gradient(135deg, #ec4899 0%, #db2777 100%)',
                boxShadow: '0 4px 12px rgba(236, 72, 153, 0.4)',
              }}
            >
              <Shield size={22} color="#ffffff" />
            </div>
            <div className="lost-header-text">
              <div className="lost-title-row">
                <h3 style={{ color: '#ffffff' }}>HerRoute Safety Feedback</h3>
                <span
                  style={{
                    background: '#db2777',
                    color: '#ffffff',
                    fontSize: '0.65rem',
                    fontWeight: 850,
                    padding: '0.15rem 0.5rem',
                    borderRadius: '9999px',
                    letterSpacing: '0.04em',
                  }}
                >
                  WOMEN'S SAFETY
                </span>
              </div>
              <p className="lost-subtitle" style={{ color: '#c7d2fe' }}>
                Share your journey comfort to inform future women travelers.
              </p>
            </div>
          </div>

          <button
            type="button"
            className="lost-modal-close"
            onClick={onClose}
            aria-label="Close feedback modal"
          >
            <X size={20} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="lost-modal-body" style={{ background: '#faf5ff' }}>
          {success ? (
            <div className="herroute-success-state">
              <div className="herroute-success-icon-box">
                <CheckCircle2 size={44} color="#16a34a" />
              </div>
              <h4>Thank you for your feedback!</h4>
              <p>
                Your experience has been securely and anonymously added to HerRoute community insights.
                This helps fellow women commuters make safer, more informed travel choices.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
              {errorMsg && (
                <div className="lost-alert-box alert-danger">
                  <AlertTriangle size={18} />
                  <span>{errorMsg}</span>
                </div>
              )}

              {/* Time of Travel Filter Switch */}
              <div className="herroute-time-selector">
                <span className="herroute-label-small">Travel Time:</span>
                <div className="herroute-time-toggle">
                  <button
                    type="button"
                    className={`herroute-time-btn ${timeCategory === 'daytime' ? 'active' : ''}`}
                    onClick={() => setTimeCategory('daytime')}
                  >
                    <Sun size={14} />
                    <span>Daytime</span>
                  </button>
                  <button
                    type="button"
                    className={`herroute-time-btn ${timeCategory === 'nighttime' ? 'active' : ''}`}
                    onClick={() => setTimeCategory('nighttime')}
                  >
                    <Moon size={14} />
                    <span>Nighttime</span>
                  </button>
                </div>
              </div>

              {/* Question 1: Experience Selection */}
              <div className="herroute-form-section">
                <label className="herroute-section-label">
                  <span className="step-num-pill">1</span>
                  <span>How safe did you feel during your journey?</span>
                </label>

                <div className="herroute-experience-grid">
                  <button
                    type="button"
                    className={`herroute-exp-btn exp-comfortable ${experience === 'comfortable' ? 'selected' : ''}`}
                    onClick={() => setExperience('comfortable')}
                  >
                    <span className="exp-emoji">🟢</span>
                    <strong className="exp-title">Comfortable</strong>
                    <span className="exp-sub">Felt secure &amp; at ease</span>
                  </button>

                  <button
                    type="button"
                    className={`herroute-exp-btn exp-uncomfortable ${experience === 'uncomfortable' ? 'selected' : ''}`}
                    onClick={() => setExperience('uncomfortable')}
                  >
                    <span className="exp-emoji">🟡</span>
                    <strong className="exp-title">Somewhat Uncomfortable</strong>
                    <span className="exp-sub">Hesitant or uneasy</span>
                  </button>

                  <button
                    type="button"
                    className={`herroute-exp-btn exp-unsafe ${experience === 'unsafe' ? 'selected' : ''}`}
                    onClick={() => setExperience('unsafe')}
                  >
                    <span className="exp-emoji">🔴</span>
                    <strong className="exp-title">Unsafe Experience</strong>
                    <span className="exp-sub">Felt distressed or unsafe</span>
                  </button>
                </div>
              </div>

              {/* Question 2: Segment Selection */}
              <div className="herroute-form-section">
                <label className="herroute-section-label">
                  <span className="step-num-pill">2</span>
                  <span>Which part of the journey are you reviewing?</span>
                </label>

                <div className="herroute-segment-chips">
                  <button
                    type="button"
                    className={`segment-chip ${selectedSegmentType === 'entire_journey' ? 'active' : ''}`}
                    onClick={() => {
                      setSelectedSegmentType('entire_journey');
                      setSelectedSegmentId('entire_journey');
                      setSelectedSegmentName('Entire Journey');
                    }}
                  >
                    <Compass size={14} />
                    <span>Entire Journey</span>
                  </button>

                  {/* Individual Legs if available */}
                  {journey &&
                    journey.legs &&
                    journey.legs.map((leg, idx) => {
                      const isWalk = leg.mode === 'walking' || leg.mode === 'walk';
                      const isMetro = leg.mode === 'metro';
                      const sType: SegmentType = isWalk ? 'walking' : isMetro ? 'metro' : 'bus';
                      const sId = leg.from_stop_id || `leg_${idx}`;
                      const sName = `${isWalk ? 'Walk' : isMetro ? 'Metro' : 'Bus'}: ${leg.from_stop_name || ''}`;

                      return (
                        <button
                          key={idx}
                          type="button"
                          className={`segment-chip ${selectedSegmentId === sId ? 'active' : ''}`}
                          onClick={() => {
                            setSelectedSegmentType(sType);
                            setSelectedSegmentId(sId);
                            setSelectedSegmentName(sName);
                          }}
                        >
                          {isWalk ? <Footprints size={14} /> : isMetro ? <TrainTrack size={14} /> : <Bus size={14} />}
                          <span>{sName}</span>
                        </button>
                      );
                    })}

                  {/* Generic options if no specific active journey */}
                  {(!journey || !journey.legs || journey.legs.length === 0) && (
                    <>
                      <button
                        type="button"
                        className={`segment-chip ${selectedSegmentType === 'walking' ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedSegmentType('walking');
                          setSelectedSegmentId('walking_route');
                          setSelectedSegmentName('Walking Route');
                        }}
                      >
                        <Footprints size={14} />
                        <span>Walking Route</span>
                      </button>

                      <button
                        type="button"
                        className={`segment-chip ${selectedSegmentType === 'metro' ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedSegmentType('metro');
                          setSelectedSegmentId('metro_journey');
                          setSelectedSegmentName('Metro Journey');
                        }}
                      >
                        <TrainTrack size={14} />
                        <span>Metro Journey</span>
                      </button>

                      <button
                        type="button"
                        className={`segment-chip ${selectedSegmentType === 'bus' ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedSegmentType('bus');
                          setSelectedSegmentId('bus_journey');
                          setSelectedSegmentName('Bus Journey');
                        }}
                      >
                        <Bus size={14} />
                        <span>Bus Journey</span>
                      </button>

                      <button
                        type="button"
                        className={`segment-chip ${selectedSegmentType === 'auto' ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedSegmentType('auto');
                          setSelectedSegmentId('auto_journey');
                          setSelectedSegmentName('Auto / Cab Ride');
                        }}
                      >
                        <Car size={14} />
                        <span>Auto-Rickshaw Journey</span>
                      </button>

                      <button
                        type="button"
                        className={`segment-chip ${selectedSegmentType === 'station_interchange' ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedSegmentType('station_interchange');
                          setSelectedSegmentId('station_interchange');
                          setSelectedSegmentName('Station / Interchange');
                        }}
                      >
                        <Compass size={14} />
                        <span>Metro / Bus Stop Interchange</span>
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Question 3: What influenced your experience? */}
              <div className="herroute-form-section">
                <label className="herroute-section-label">
                  <span className="step-num-pill">3</span>
                  <span>What influenced your experience? (Select all that apply)</span>
                </label>

                <div className="herroute-concerns-grid">
                  {INFLUENCING_CONCERNS.map((item) => {
                    const isSelected = selectedConcerns.includes(item.key);
                    return (
                      <button
                        key={item.key}
                        type="button"
                        className={`concern-toggle-btn ${isSelected ? 'selected' : ''}`}
                        onClick={() => handleToggleConcern(item.key)}
                      >
                        <span className="concern-icon">{item.icon}</span>
                        <span className="concern-text">{item.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Optional Text Field */}
              <div className="herroute-form-section">
                <label className="herroute-section-label" style={{ justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                    <span className="step-num-pill">4</span>
                    <span>Additional Observations (Optional)</span>
                  </div>
                  <span className="privacy-badge">
                    <Lock size={11} />
                    <span>Kept Private</span>
                  </span>
                </label>

                <textarea
                  className="herroute-textarea"
                  placeholder="Share details (e.g. good lighting near exit 2, deserted underpass at night). No personal identifying details."
                  maxLength={500}
                  rows={2}
                  value={feedbackText}
                  onChange={(e) => setFeedbackText(e.target.value)}
                />
              </div>

              {/* Form Action Buttons */}
              <div className="herroute-modal-footer">
                <button
                  type="button"
                  className="herroute-btn-skip"
                  onClick={onClose}
                  disabled={loading}
                >
                  Skip Feedback
                </button>

                <button
                  type="submit"
                  className="herroute-btn-submit"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      <span>Submitting...</span>
                    </>
                  ) : (
                    <>
                      <Shield size={16} />
                      <span>Submit Anonymously</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default SafetyFeedbackModal;
