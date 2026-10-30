import React, { useState, useEffect } from 'react';
import {
  LifeBuoy,
  X,
  MapPin,
  TrainTrack,
  Bus,
  Car,
  Volume2,
  VolumeX,
  AlertTriangle,
  RotateCcw,
  CheckCircle,
  Clock,
  ArrowRight,
  Navigation,
  Compass,
  Footprints,
  Loader2,
} from 'lucide-react';
import { SafarSetuAPI, LostAssistanceResponse, RoutePlanResponse, NearestStationDetail } from '../lib/api';
import { voiceService } from '../services/voiceService';

export interface LostAssistanceModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeDestinationId?: string;
  activeDestinationName?: string;
  onApplyReroute: (plan: RoutePlanResponse, fromStopName: string) => void;
}

export const LostAssistanceModal: React.FC<LostAssistanceModalProps> = ({
  isOpen,
  onClose,
  activeDestinationId,
  activeDestinationName,
  onApplyReroute,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<LostAssistanceResponse | null>(null);
  const [selectedStationType, setSelectedStationType] = useState<'metro' | 'bus' | 'overall'>('metro');
  const [customDestination, setCustomDestination] = useState<string>(activeDestinationName || '');
  const [isSpeaking, setIsSpeaking] = useState(false);

  // Quick destination suggestion chips
  const popularDestinations = [
    'India Gate',
    'New Delhi Railway Station',
    'Rajiv Chowk',
    'Qutub Minar',
    'Akshardham',
    'Kashmere Gate',
    'AIIMS',
  ];

  useEffect(() => {
    if (isOpen) {
      if (activeDestinationName) {
        setCustomDestination(activeDestinationName);
      }
      detectLocationAndFetch();
    } else {
      voiceService.stop();
      setIsSpeaking(false);
    }
  }, [isOpen]);

  const detectLocationAndFetch = (overrideDest?: string) => {
    setLoading(true);
    setError(null);

    const destToUse = overrideDest !== undefined ? overrideDest : (activeDestinationId || customDestination);

    if (!navigator.geolocation) {
      // Fallback coordinates (Central Delhi / Connaught Place)
      fetchAssistance(28.6315, 77.2167, destToUse);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        fetchAssistance(pos.coords.latitude, pos.coords.longitude, destToUse);
      },
      (geoErr) => {
        console.warn('Geolocation failed or denied, using central transit node fallback:', geoErr);
        fetchAssistance(28.6315, 77.2167, destToUse);
      },
      { timeout: 8000, enableHighAccuracy: true }
    );
  };

  const fetchAssistance = async (lat: number, lon: number, destination?: string) => {
    try {
      setLoading(true);
      const isId = (destination && destination.startsWith('metro_')) || destination?.startsWith('bus_');
      const res = await SafarSetuAPI.getLostAssistance({
        user_lat: lat,
        user_lon: lon,
        destination_stop_id: isId ? destination : undefined,
        destination_name: !isId ? destination : undefined,
        preferred_mode: 'all',
      });
      setData(res);

      // Auto-speak reassuring voice announcement
      if (res.spoken_guidance?.en) {
        speakGuidance(res.spoken_guidance.en);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to determine nearby emergency transit stations.');
    } finally {
      setLoading(false);
    }
  };

  const speakGuidance = (text: string) => {
    try {
      voiceService.speak({
        text,
        lang: 'en',
        onStart: () => setIsSpeaking(true),
        onEnd: () => setIsSpeaking(false),
        onError: () => setIsSpeaking(false),
      });
      setIsSpeaking(true);
    } catch (e) {
      setIsSpeaking(false);
    }
  };

  const handleToggleSpeak = () => {
    if (isSpeaking) {
      voiceService.stop();
      setIsSpeaking(false);
    } else if (data?.spoken_guidance?.en) {
      speakGuidance(data.spoken_guidance.en);
    }
  };

  const handleApplyReroute = () => {
    if (!data) return;
    if (data.rerouted_plan && data.rerouted_plan.journeys.length > 0) {
      const fromName =
        (selectedStationType === 'metro' && data.nearest_metro?.stop_name) ||
        (selectedStationType === 'bus' && data.nearest_bus_stop?.stop_name) ||
        data.nearest_station_overall.stop_name;
      onApplyReroute(data.rerouted_plan, fromName);
      voiceService.stop();
      onClose();
    }
  };

  if (!isOpen) return null;

  const currentSelectedStation: NearestStationDetail | null =
    selectedStationType === 'metro' && data?.nearest_metro
      ? data.nearest_metro
      : selectedStationType === 'bus' && data?.nearest_bus_stop
      ? data.nearest_bus_stop
      : data?.nearest_station_overall || null;

  return (
    <div className="lost-modal-overlay" onClick={onClose} aria-modal="true" role="dialog">
      <div className="lost-modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="lost-modal-header">
          <div className="lost-header-left">
            <div className="lost-header-icon-box">
              <LifeBuoy size={22} />
              <span className="lost-beacon-ping" />
            </div>
            <div className="lost-header-text">
              <div className="lost-title-row">
                <h3>Lost Assistance &amp; Reroute</h3>
                <span className="lost-badge-sos">SOS</span>
              </div>
              <p className="lost-subtitle">
                Redirecting to nearest Delhi Metro, Bus Stand, or Auto Hub
              </p>
            </div>
          </div>

          <button
            type="button"
            className="lost-modal-close"
            onClick={onClose}
            aria-label="Close lost assistance"
          >
            <X size={20} />
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="lost-modal-body">
          {/* Loading State */}
          {loading && (
            <div className="lost-loading-card">
              <div className="lost-radar-animation">
                <div className="radar-circle circle-1" />
                <div className="radar-circle circle-2" />
                <MapPin size={24} className="radar-pin-icon" />
              </div>
              <h4>Triangulating Your Position...</h4>
              <p>Scanning 6,604 Delhi transit stops for your closest Metro, Bus &amp; Auto stands.</p>
            </div>
          )}

          {/* Error State */}
          {error && !loading && (
            <div className="lost-alert-box alert-danger">
              <AlertTriangle size={20} />
              <div>
                <strong>Location Notice:</strong> {error}
              </div>
            </div>
          )}

          {/* Result Content */}
          {data && !loading && (
            <>
              {/* Reassuring Voice Announcement Bar */}
              <div className="lost-reassurance-bar">
                <button
                  type="button"
                  className={`lost-voice-btn ${isSpeaking ? 'speaking' : ''}`}
                  onClick={handleToggleSpeak}
                  title={isSpeaking ? 'Mute voice' : 'Listen to voice instructions'}
                >
                  {isSpeaking ? <VolumeX size={18} /> : <Volume2 size={18} />}
                  <span>{isSpeaking ? 'Speaking...' : 'Listen'}</span>
                </button>
                <div className="lost-reassurance-text">
                  <p>{data.reassuring_message}</p>
                </div>
              </div>

              {/* Section 1: Choose Nearest Transit Stand */}
              <div className="lost-section">
                <div className="lost-section-title-row">
                  <span className="lost-section-number">1</span>
                  <span className="lost-section-heading">Select Nearest Transit Stand:</span>
                </div>

                <div className="lost-stands-grid">
                  {/* Metro Station Card */}
                  {data.nearest_metro && (
                    <div
                      className={`lost-stand-card ${selectedStationType === 'metro' ? 'active' : ''}`}
                      onClick={() => setSelectedStationType('metro')}
                    >
                      <div className="lost-stand-top">
                        <div className="stand-badge metro">
                          <TrainTrack size={15} />
                          <span>Metro</span>
                        </div>
                        <span className="stand-tag fastest">Fastest Rail</span>
                      </div>
                      <h4 className="stand-name">{data.nearest_metro.stop_name}</h4>
                      <div className="stand-metrics">
                        <span className="metric-pill">
                          <Compass size={13} />
                          <strong>~{Math.round(data.nearest_metro.distance_meters)}m</strong>
                        </span>
                        <span className="metric-pill">
                          <Footprints size={13} />
                          <strong>{data.nearest_metro.walk_minutes} min walk</strong>
                        </span>
                      </div>
                      {data.nearest_metro.lines.length > 0 && (
                        <div className="stand-chips">
                          {data.nearest_metro.lines.map((line, idx) => (
                            <span key={idx} className="line-chip metro-chip">{line}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* DTC Bus Stand Card */}
                  {data.nearest_bus_stop && (
                    <div
                      className={`lost-stand-card ${selectedStationType === 'bus' ? 'active' : ''}`}
                      onClick={() => setSelectedStationType('bus')}
                    >
                      <div className="lost-stand-top">
                        <div className="stand-badge bus">
                          <Bus size={15} />
                          <span>DTC Bus</span>
                        </div>
                        <span className="stand-tag low-cost">₹5 - ₹15</span>
                      </div>
                      <h4 className="stand-name">{data.nearest_bus_stop.stop_name}</h4>
                      <div className="stand-metrics">
                        <span className="metric-pill">
                          <Compass size={13} />
                          <strong>~{Math.round(data.nearest_bus_stop.distance_meters)}m</strong>
                        </span>
                        <span className="metric-pill">
                          <Footprints size={13} />
                          <strong>{data.nearest_bus_stop.walk_minutes} min walk</strong>
                        </span>
                      </div>
                      {data.nearest_bus_stop.lines.length > 0 && (
                        <div className="stand-chips">
                          {data.nearest_bus_stop.lines.slice(0, 3).map((line, idx) => (
                            <span key={idx} className="line-chip bus-chip">{line}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Auto Rickshaw Stand Card */}
                  <div className="lost-stand-card auto-card">
                    <div className="lost-stand-top">
                      <div className="stand-badge auto">
                        <Car size={15} />
                        <span>Auto Rickshaw</span>
                      </div>
                      <span className="stand-tag auto-tag">GNCTD Meter</span>
                    </div>
                    <h4 className="stand-name">Stand at {data.nearest_station_overall.stop_name}</h4>
                    <div className="stand-metrics">
                      <span className="metric-pill auto-price">
                        <strong>Fare: ~₹{data.auto_rickshaw_fare_estimate_inr}</strong>
                      </span>
                      <span className="metric-pill">
                        <strong>Direct Ride</strong>
                      </span>
                    </div>
                    <p className="stand-instructions">{data.auto_pickup_instructions}</p>
                  </div>
                </div>
              </div>

              {/* Walking Directions to Selected Stand */}
              {currentSelectedStation?.directions_text && (
                <div className="lost-directions-card">
                  <div className="directions-header">
                    <Footprints size={16} />
                    <strong>Walking Route to {currentSelectedStation.stop_name}:</strong>
                  </div>
                  <p>{currentSelectedStation.directions_text}</p>
                </div>
              )}

              {/* Section 2: Destination Confirmation & Fresh Route */}
              <div className="lost-section">
                <div className="lost-section-title-row">
                  <span className="lost-section-number">2</span>
                  <span className="lost-section-heading">Where were you travelling to?</span>
                </div>

                <div className="lost-destination-box">
                  <div className="lost-input-row">
                    <div className="lost-input-wrapper">
                      <MapPin size={17} className="lost-input-pin" />
                      <input
                        type="text"
                        className="lost-dest-input"
                        placeholder="Search destination (e.g. India Gate, New Delhi Station)..."
                        value={customDestination}
                        onChange={(e) => setCustomDestination(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            detectLocationAndFetch(customDestination);
                          }
                        }}
                      />
                    </div>
                    <button
                      type="button"
                      className="lost-dest-submit-btn"
                      onClick={() => detectLocationAndFetch(customDestination)}
                    >
                      <span>Re-Map</span>
                      <ArrowRight size={15} />
                    </button>
                  </div>

                  {/* Suggestion Chips */}
                  <div className="lost-chips-row">
                    <span className="chips-label">Popular:</span>
                    {popularDestinations.map((dest, i) => (
                      <button
                        key={i}
                        type="button"
                        className={`lost-quick-chip ${customDestination === dest ? 'active' : ''}`}
                        onClick={() => {
                          setCustomDestination(dest);
                          detectLocationAndFetch(dest);
                        }}
                      >
                        {dest}
                      </button>
                    ))}
                  </div>

                  {/* Recalculated Journey Preview Card */}
                  {data.rerouted_plan && data.rerouted_plan.journeys.length > 0 ? (
                    <div className="lost-reroute-result-card">
                      <div className="reroute-card-top">
                        <div className="reroute-title">
                          <CheckCircle size={17} className="check-icon" />
                          <strong>Updated Journey Available</strong>
                        </div>
                        <div className="reroute-meta-pills">
                          <span className="duration-pill">
                            <Clock size={13} />
                            <span>{Math.round(data.rerouted_plan.journeys[0].total_duration_minutes)} mins</span>
                          </span>
                          {data.rerouted_plan.journeys[0].fare_inr !== undefined && (
                            <span className="fare-pill">
                              ₹{data.rerouted_plan.journeys[0].fare_inr}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="reroute-steps-list">
                        <div className="reroute-step-item">
                          <span className="step-badge">1</span>
                          <div className="step-info">
                            <strong>Walk to {currentSelectedStation?.stop_name}</strong>
                            <span>{currentSelectedStation?.directions_text}</span>
                          </div>
                        </div>
                        <div className="reroute-step-item">
                          <span className="step-badge">2</span>
                          <div className="step-info">
                            <strong>Board transit to destination</strong>
                            <span>
                              {data.rerouted_plan.journeys[0].legs.length} leg(s) &bull; Verified timetable schedule
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="lost-no-plan-card">
                      <p>
                        Type or tap a destination above to map a fresh transit route from{' '}
                        <strong>{currentSelectedStation?.stop_name}</strong>.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="lost-modal-footer">
          <button
            type="button"
            className="lost-btn-cancel"
            onClick={onClose}
          >
            Cancel
          </button>

          <button
            type="button"
            className="lost-btn-navigate"
            onClick={handleApplyReroute}
            disabled={!data?.rerouted_plan || data.rerouted_plan.journeys.length === 0}
          >
            <Navigation size={17} />
            <span>Apply Reroute &amp; Navigate</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default LostAssistanceModal;
