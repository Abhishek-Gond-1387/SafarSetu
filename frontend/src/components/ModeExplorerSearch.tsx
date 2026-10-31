import React, { useState, useEffect } from 'react';
import {
  Navigation,
  MapPin,
  TrainTrack,
  Bus,
  Car,
  Clock,
  ArrowRight,
  CheckCircle2,
  Zap,
  Coins,
  Scale,
  Loader2,
  ChevronRight,
  Layers,
  ArrowUpDown,
  CircleDollarSign,
  Compass,
  Sparkles,
  LocateFixed,
  LocateOff,
  Crosshair,
  AlertCircle,
} from 'lucide-react';
import {
  SafarSetuAPI,
  StopItem,
  ModeOption,
  ModeExploreResponse,
  PlanRouteParams,
} from '../lib/api';

interface ModeExplorerSearchProps {
  onPlanRoute: (params: PlanRouteParams) => void;
  isLoading: boolean;
}

const isMetroStop = (stop: StopItem) => {
  return stop.stop_id.startsWith('metro_') || stop.stop_name.toLowerCase().includes('metro');
};

const getModePref = (modeId: string, origId?: string, destId?: string): 'bus' | 'metro' | 'all' | 'multimodal' => {
  if (modeId === 'auto' || modeId === 'cab' || modeId === 'multimodal') return 'all';
  if (modeId === 'metro') {
    // If either stop is not a metro station, pure rail is impossible without surface transit
    const origIsMetro = origId ? origId.startsWith('metro_') : false;
    const destIsMetro = destId ? destId.startsWith('metro_') : false;
    if (!origIsMetro || !destIsMetro) return 'all';
    return 'metro';
  }
  if (modeId === 'bus') return 'bus';
  return 'all';
};

const POPULAR_DESTINATIONS = [
  { label: '🏛️ Red Fort', query: 'Red Fort' },
  { label: '🎓 MAIT', query: 'MAIT' },
  { label: '📚 DU (Delhi Univ)', query: 'DU' },
  { label: '🛍️ Connaught Place (CP)', query: 'CP' },
  { label: '🔬 IIT Delhi', query: 'IIT' },
  { label: '🏥 AIIMS', query: 'AIIMS' },
  { label: '✈️ IGI Airport', query: 'IGI Airport' },
];

export const ModeExplorerSearch: React.FC<ModeExplorerSearchProps> = ({
  onPlanRoute,
  isLoading,
}) => {
  // Location Permission & Geolocation State
  const [isLocationDisabled, setIsLocationDisabled] = useState<boolean>(() => {
    return localStorage.getItem('safarsetu_location_disabled') === 'true';
  });
  const [locationStep, setLocationStep] = useState<'prompt' | 'requesting' | 'detected' | 'manual'>(() => {
    return localStorage.getItem('safarsetu_location_disabled') === 'true' ? 'manual' : 'prompt';
  });
  const [isLocating, setIsLocating] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [detectedCoords, setDetectedCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [stopDistanceMeters, setStopDistanceMeters] = useState<number | null>(null);

  // Destination state
  const [destQuery, setDestQuery] = useState('');
  const [destStop, setDestStop] = useState<StopItem | null>(null);
  const [destSuggestions, setDestSuggestions] = useState<StopItem[]>([]);
  const [showDestDropdown, setShowDestDropdown] = useState(false);
  const [isDestLoading, setIsDestLoading] = useState(false);

  // Origin state
  const [originQuery, setOriginQuery] = useState('');
  const [originStop, setOriginStop] = useState<StopItem | null>(null);
  const [originSuggestions, setOriginSuggestions] = useState<StopItem[]>([]);
  const [showOriginDropdown, setShowOriginDropdown] = useState(false);
  const [isOriginLoading, setIsOriginLoading] = useState(false);

  // Mode Exploration state
  const [modeData, setModeData] = useState<ModeExploreResponse | null>(null);
  const [isExploring, setIsExploring] = useState(false);
  const [selectedModeId, setSelectedModeId] = useState<'metro' | 'bus' | 'multimodal' | 'auto' | 'cab'>('metro');
  const [selectedCriterion, setSelectedCriterion] = useState<'fastest' | 'cheapest' | 'balanced'>('fastest');

  // Custom stop selection for the selected mode
  const [chosenOriginStopId, setChosenOriginStopId] = useState<string>('');
  const [chosenDestStopId, setChosenDestStopId] = useState<string>('');

  // Date and Time
  const todayStr = new Date().toISOString().split('T')[0];
  const now = new Date();
  const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  const [travelDate, setTravelDate] = useState(todayStr);
  const [travelTime, setTravelTime] = useState(timeStr);

  // Check if browser already granted location on mount (unless user disabled it)
  useEffect(() => {
    if (localStorage.getItem('safarsetu_location_disabled') === 'true') {
      return;
    }
    if (navigator.permissions && navigator.permissions.query) {
      navigator.permissions.query({ name: 'geolocation' }).then((status) => {
        if (status.state === 'granted') {
          handleRequestLocation();
        }
      }).catch(() => {
        // Fallback to normal prompt
      });
    }
  }, []);

  // Disable location completely
  const handleDisableLocation = () => {
    setIsLocationDisabled(true);
    localStorage.setItem('safarsetu_location_disabled', 'true');
    setDetectedCoords(null);
    setStopDistanceMeters(null);
    setLocationStep('manual');
    setLocationError(null);
  };

  // Enable location and request current coordinates
  const handleEnableLocation = () => {
    setIsLocationDisabled(false);
    localStorage.removeItem('safarsetu_location_disabled');
    handleRequestLocation();
  };

  // Request browser geolocation
  const handleRequestLocation = () => {
    if (!navigator.geolocation) {
      setLocationError('Geolocation is not supported by your browser.');
      setLocationStep('manual');
      return;
    }

    setIsLocating(true);
    setLocationError(null);
    setIsLocationDisabled(false);
    localStorage.removeItem('safarsetu_location_disabled');

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const coords = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        setDetectedCoords(coords);

        try {
          const res = await SafarSetuAPI.getNearbyStops(coords.lat, coords.lon, 4500, 10);
          if (res.results && res.results.length > 0) {
            const closest = res.results[0];
            setOriginStop(closest);
            setOriginQuery(closest.stop_name);
            setStopDistanceMeters(closest.distance_meters);
            setLocationStep('detected');

            // If destination already chosen, explore modes from this new location
            if (destStop) {
              fetchModes(destStop, closest);
            }
          } else {
            // User coordinates outside Delhi transit dataset coverage
            setLocationError('Location detected, but no Delhi transit stops within 4km. Defaulting to Central Delhi (Rajiv Chowk).');
            const defRes = await SafarSetuAPI.searchStops('Rajiv Chowk', 1);
            if (defRes.results && defRes.results.length > 0) {
              setOriginStop(defRes.results[0]);
              setOriginQuery(defRes.results[0].stop_name);
            }
            setLocationStep('manual');
          }
        } catch (err) {
          console.error('Failed to resolve nearby stops from GPS:', err);
          setLocationStep('manual');
        } finally {
          setIsLocating(false);
        }
      },
      (err) => {
        console.warn('Geolocation denied or unavailable:', err.message);
        setIsLocating(false);
        setLocationError('Location permission denied or unavailable. Please choose your starting location manually.');
        setLocationStep('manual');
      },
      { enableHighAccuracy: true, timeout: 9000, maximumAge: 60000 }
    );
  };

  // Debounced Destination Search
  useEffect(() => {
    if (!destQuery.trim() || (destStop && destStop.stop_name === destQuery.trim())) {
      setDestSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsDestLoading(true);
      try {
        const res = await SafarSetuAPI.searchStops(destQuery.trim(), 8);
        setDestSuggestions(res.results || []);
        setShowDestDropdown(true);
      } catch {
        setDestSuggestions([]);
      } finally {
        setIsDestLoading(false);
      }
    }, 280);
    return () => clearTimeout(timer);
  }, [destQuery, destStop]);

  // Debounced Origin Search
  useEffect(() => {
    if (!originQuery.trim() || (originStop && originStop.stop_name === originQuery.trim())) {
      setOriginSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsOriginLoading(true);
      try {
        const res = await SafarSetuAPI.searchStops(originQuery.trim(), 8);
        setOriginSuggestions(res.results || []);
        setShowOriginDropdown(true);
      } catch {
        setOriginSuggestions([]);
      } finally {
        setIsOriginLoading(false);
      }
    }, 280);
    return () => clearTimeout(timer);
  }, [originQuery, originStop]);

  // Fetch transportation mode combinations and trigger route calculation
  const fetchModes = async (dest: StopItem, orig?: StopItem | null) => {
    setIsExploring(true);
    try {
      const res = await SafarSetuAPI.exploreModes({
        destination_stop_id: dest.stop_id,
        origin_stop_id: orig?.stop_id,
        departure_date: travelDate,
        departure_time: `${travelTime}:00`,
      });
      setModeData(res);

      const metroMode = res.modes.find((m) => m.mode_id === 'metro') || res.modes[0];
      const initialOrigId = metroMode?.recommended_origin_stop?.stop_id || orig?.stop_id || res.origin_stop?.stop_id || '';
      const initialDestId = metroMode?.recommended_destination_stop?.stop_id || dest.stop_id;

      if (metroMode) {
        setSelectedModeId(metroMode.mode_id);
        setChosenOriginStopId(initialOrigId);
        setChosenDestStopId(initialDestId);
      }

      // Auto-compute routes for the active path so the choosing page displays routes immediately
      if (initialOrigId && initialDestId) {
        const pref = getModePref(metroMode?.mode_id || 'all', initialOrigId, initialDestId);
        onPlanRoute({
          origin_stop_id: initialOrigId,
          destination_stop_id: initialDestId,
          departure_date: travelDate,
          departure_time: `${travelTime}:00`,
          criterion: selectedCriterion,
          mode_preference: pref,
          max_transfers: 3,
          max_walk_meters: 800,
        });
      }
    } catch (err) {
      console.error('Failed to explore modes', err);
    } finally {
      setIsExploring(false);
    }
  };

  const handleSelectDest = (stop: StopItem) => {
    setDestStop(stop);
    setDestQuery(stop.stop_name);
    setShowDestDropdown(false);
    fetchModes(stop, originStop);
  };

  const handleSelectOrigin = (stop: StopItem) => {
    setOriginStop(stop);
    setOriginQuery(stop.stop_name);
    setShowOriginDropdown(false);
    if (destStop) {
      fetchModes(destStop, stop);
    }
  };

  const handleQuickChip = async (query: string) => {
    setDestQuery(query);
    setIsDestLoading(true);
    try {
      const res = await SafarSetuAPI.searchStops(query, 5);
      if (res.results && res.results.length > 0) {
        handleSelectDest(res.results[0]);
      }
    } catch (err) {
      console.error('Quick chip search error:', err);
    } finally {
      setIsDestLoading(false);
    }
  };

  const handleModeChange = (mode: ModeOption) => {
    setSelectedModeId(mode.mode_id);
    let criterion: 'fastest' | 'cheapest' | 'balanced' = selectedCriterion;
    if (mode.mode_id === 'bus') {
      criterion = 'cheapest';
      setSelectedCriterion('cheapest');
    } else if (mode.mode_id === 'metro') {
      criterion = 'fastest';
      setSelectedCriterion('fastest');
    } else if (mode.mode_id === 'multimodal') {
      criterion = 'balanced';
      setSelectedCriterion('balanced');
    }

    const newOrig = mode.recommended_origin_stop?.stop_id || chosenOriginStopId || originStop?.stop_id || modeData?.origin_stop?.stop_id;
    const newDest = mode.recommended_destination_stop?.stop_id || chosenDestStopId || destStop?.stop_id || modeData?.destination_stop?.stop_id;

    if (mode.recommended_origin_stop) {
      setChosenOriginStopId(mode.recommended_origin_stop.stop_id);
    }
    if (mode.recommended_destination_stop) {
      setChosenDestStopId(mode.recommended_destination_stop.stop_id);
    }

    if (newOrig && newDest) {
      onPlanRoute({
        origin_stop_id: newOrig,
        destination_stop_id: newDest,
        departure_date: travelDate,
        departure_time: `${travelTime}:00`,
        criterion: criterion,
        mode_preference: getModePref(mode.mode_id, newOrig, newDest),
        max_transfers: 3,
        max_walk_meters: 800,
      });
    }
  };

  const handleCriterionChange = (criterion: 'fastest' | 'cheapest' | 'balanced') => {
    setSelectedCriterion(criterion);
    const finalOrigin = chosenOriginStopId || originStop?.stop_id || modeData?.origin_stop?.stop_id;
    const finalDest = chosenDestStopId || destStop?.stop_id || modeData?.destination_stop?.stop_id;
    if (finalOrigin && finalDest) {
      onPlanRoute({
        origin_stop_id: finalOrigin,
        destination_stop_id: finalDest,
        departure_date: travelDate,
        departure_time: `${travelTime}:00`,
        criterion: criterion,
        mode_preference: getModePref(selectedModeId, finalOrigin, finalDest),
        max_transfers: 3,
        max_walk_meters: 800,
      });
    }
  };

  const handlePlanJourney = () => {
    const finalOrigin = chosenOriginStopId || originStop?.stop_id || modeData?.origin_stop?.stop_id;
    const finalDest = chosenDestStopId || destStop?.stop_id || modeData?.destination_stop?.stop_id;

    if (!finalOrigin || !finalDest) return;

    onPlanRoute({
      origin_stop_id: finalOrigin,
      destination_stop_id: finalDest,
      departure_date: travelDate,
      departure_time: `${travelTime}:00`,
      criterion: selectedCriterion,
      mode_preference: getModePref(selectedModeId, finalOrigin, finalDest),
      max_transfers: 3,
      max_walk_meters: 800,
    });
  };

  const currentModeOption = modeData?.modes.find((m) => m.mode_id === selectedModeId);

  return (
    <div className="search-card mode-explorer-card">
      {/* ── STEP 0: Location Permission Prompt (Shown first before destination) ── */}
      {!isLocationDisabled && locationStep === 'prompt' && (
        <div className="location-permission-card">
          <div className="location-permission-icon-wrap">
            <LocateFixed size={26} color="#0f766e" />
          </div>
          <div className="location-permission-body">
            <h3 className="location-permission-title">Enable Live Location Access</h3>
            <p className="location-permission-text">
              Share your location to find the closest Metro stations &amp; DTC bus stops, and calculate accurate door-to-door distances, walking times, and fares from right where you are.
            </p>

            <div className="location-permission-buttons">
              <button
                type="button"
                className="btn btn-primary location-allow-btn"
                onClick={handleRequestLocation}
                disabled={isLocating}
              >
                {isLocating ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    <span>Detecting Nearest Stops...</span>
                  </>
                ) : (
                  <>
                    <Crosshair size={16} />
                    <span>Share My Current Location</span>
                  </>
                )}
              </button>
              <button
                type="button"
                className="btn-location-skip"
                onClick={handleDisableLocation}
                title="Do not use device location"
              >
                <LocateOff size={14} />
                <span>Disable Location (Manual Mode)</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Error notice if location denied */}
      {locationError && (
        <div className="alert-box alert-danger" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', fontSize: '0.82rem' }}>
          <AlertCircle size={15} style={{ flexShrink: 0 }} />
          <span>{locationError}</span>
        </div>
      )}

      {/* ── Active Origin Banner (When Location is Detected) ── */}
      {!isLocationDisabled && locationStep === 'detected' && originStop && (
        <div className="location-detected-banner">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
            <div className="live-gps-dot" />
            <span>
              Live GPS Origin: <strong>{originStop.stop_name}</strong>
              {stopDistanceMeters ? ` (~${Math.round(stopDistanceMeters)}m from your location)` : ''}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
            <button
              type="button"
              className="btn-change-location"
              onClick={() => setLocationStep('manual')}
            >
              Change Stop
            </button>
            <button
              type="button"
              className="btn-disable-location"
              onClick={handleDisableLocation}
              title="Turn off GPS location and enter starting point manually"
            >
              <LocateOff size={13} />
              <span>Disable Location</span>
            </button>
          </div>
        </div>
      )}

      {/* ── Disabled Location Notice with Re-Enable Action ── */}
      {isLocationDisabled && (
        <div className="location-disabled-banner">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.82rem', color: '#475569' }}>
            <LocateOff size={15} color="#64748b" />
            <span>Live location is <strong>Disabled</strong>. You can enter any starting stop manually.</span>
          </div>
          <button
            type="button"
            className="btn-enable-location"
            onClick={handleEnableLocation}
            title="Enable live GPS location"
          >
            <LocateFixed size={13} />
            <span>Enable Location</span>
          </button>
        </div>
      )}

      {/* ── Header: Where do you want to go? ── */}
      <div className="explorer-header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <div className="section-step-indicator">
              <span className="step-tag">Step 3 • Journey Selection</span>
              <span className="step-tag-hindi">मार्ग चयन</span>
            </div>
            <h2 className="search-title" style={{ margin: '0.4rem 0 0 0' }}>
              <Compass size={22} color="var(--primary)" />
              <span>Where do you want to go?</span>
            </h2>
          </div>

          {isLocationDisabled ? (
            <button
              type="button"
              className="location-pill-btn off"
              onClick={handleEnableLocation}
              title="Location tracking is off. Click to enable GPS."
            >
              <LocateOff size={12} />
              <span>Location: Disabled</span>
            </button>
          ) : (
            <button
              type="button"
              className="location-pill-btn on"
              onClick={handleDisableLocation}
              title="Location tracking is active. Click to disable."
            >
              <LocateFixed size={12} />
              <span>Location: Active</span>
            </button>
          )}
        </div>
        <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', marginTop: '0.45rem' }}>
          Select or search any destination landmark, college, or monument across Delhi/NCR to compare all transit modes.
        </p>
      </div>

      {/* Destination First Input */}
      <div className="form-group" style={{ position: 'relative', marginTop: '1rem' }}>
        <label className="form-label" htmlFor="destination-main-input">
          Destination (Where to?)
        </label>
        <div className="input-with-icon">
          <Navigation size={18} className="input-icon" color="var(--primary)" />
          <input
            id="destination-main-input"
            type="text"
            className="form-input destination-hero-input"
            placeholder="Search landmark (e.g., MAIT, DU, Red Fort, CP, IIT)"
            value={destQuery}
            autoComplete="off"
            onChange={(e) => {
              setDestQuery(e.target.value);
              setDestStop(null);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                if (destSuggestions.length > 0) {
                  handleSelectDest(destSuggestions[0]);
                }
              }
            }}
            onFocus={() => {
              if (destSuggestions.length > 0) setShowDestDropdown(true);
            }}
          />
          {isDestLoading && (
            <Loader2
              size={16}
              className="animate-spin"
              style={{ position: 'absolute', right: '0.75rem', color: 'var(--text-muted)' }}
            />
          )}
        </div>

        {/* Quick Landmarks Chips */}
        <div className="quick-chips-row">
          <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 600 }}>Quick Landmarks:</span>
          {POPULAR_DESTINATIONS.map((chip, idx) => (
            <button
              key={idx}
              type="button"
              className="quick-chip-btn"
              onClick={() => handleQuickChip(chip.query)}
            >
              {chip.label}
            </button>
          ))}
        </div>

        {showDestDropdown && destSuggestions.length > 0 && (
          <ul className="suggestions-dropdown" role="listbox">
            {destSuggestions.map((stop) => {
              const isMetro = isMetroStop(stop);
              return (
                <li
                  key={stop.stop_id}
                  className="suggestion-item"
                  role="option"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    handleSelectDest(stop);
                  }}
                  onClick={() => handleSelectDest(stop)}
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.65rem 0.85rem' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0, flex: 1 }}>
                    {isMetro ? (
                      <TrainTrack size={16} color="#7c3aed" style={{ flexShrink: 0 }} />
                    ) : (
                      <Bus size={16} color="#0f766e" style={{ flexShrink: 0 }} />
                    )}
                    <span className="suggestion-name" style={{ fontWeight: 600 }}>
                      {stop.stop_name}
                    </span>
                  </div>
                  <span className={`suggestion-type-badge ${isMetro ? 'metro' : 'bus'}`}>
                    {isMetro ? '🚇 Metro Station' : '🚌 Bus Stop'}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Origin (Starting Point) Input — Shown in manual mode or for customizing */}
      {(locationStep === 'manual' || !originStop) && (
        <div className="form-group" style={{ position: 'relative' }}>
          <label className="form-label" htmlFor="origin-main-input">
            From (Starting Location / Current Stop)
          </label>
          <div className="input-with-icon">
            <MapPin size={18} className="input-icon" />
            <input
              id="origin-main-input"
              type="text"
              className="form-input"
              placeholder="Starting stop (e.g., Kashmere Gate, Hauz Khas, Dwarka)"
              value={originQuery}
              autoComplete="off"
              onChange={(e) => {
                setOriginQuery(e.target.value);
                setOriginStop(null);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  if (originSuggestions.length > 0) {
                    handleSelectOrigin(originSuggestions[0]);
                  }
                }
              }}
              onFocus={() => {
                if (originSuggestions.length > 0) setShowOriginDropdown(true);
              }}
            />
            {isOriginLoading ? (
              <Loader2
                size={16}
                className="animate-spin"
                style={{ position: 'absolute', right: '0.75rem', color: 'var(--text-muted)' }}
              />
            ) : (
              <button
                type="button"
                className="btn-gps-inline"
                onClick={handleRequestLocation}
                title="Use current GPS location"
              >
                <Crosshair size={12} />
                <span>GPS</span>
              </button>
            )}
          </div>

          {showOriginDropdown && originSuggestions.length > 0 && (
            <ul className="suggestions-dropdown" role="listbox">
              {originSuggestions.map((stop) => {
                const isMetro = isMetroStop(stop);
                return (
                  <li
                    key={stop.stop_id}
                    className="suggestion-item"
                    role="option"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      handleSelectOrigin(stop);
                    }}
                    onClick={() => handleSelectOrigin(stop)}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.65rem 0.85rem' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0, flex: 1 }}>
                      {isMetro ? (
                        <TrainTrack size={16} color="#7c3aed" style={{ flexShrink: 0 }} />
                      ) : (
                        <Bus size={16} color="#0f766e" style={{ flexShrink: 0 }} />
                      )}
                      <span className="suggestion-name" style={{ fontWeight: 600 }}>
                        {stop.stop_name}
                      </span>
                    </div>
                    <span className={`suggestion-type-badge ${isMetro ? 'metro' : 'bus'}`}>
                      {isMetro ? '🚇 Metro Station' : '🚌 Bus Stop'}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      {/* Date & Time Row */}
      <div className="date-time-row" style={{ marginBottom: '1.25rem' }}>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Departure Date</label>
          <input
            type="date"
            className="form-input"
            value={travelDate}
            onChange={(e) => setTravelDate(e.target.value)}
          />
        </div>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Departure Time</label>
          <input
            type="time"
            className="form-input"
            value={travelTime}
            onChange={(e) => setTravelTime(e.target.value)}
          />
        </div>
      </div>

      {isExploring && (
        <div className="journey-searching-state">
          <Loader2 size={28} className="animate-spin" style={{ margin: '0 auto 0.75rem auto', color: 'var(--primary)' }} />
          <div style={{ fontWeight: 700, fontSize: '0.98rem', color: '#0f172a', marginBottom: '0.25rem' }}>
            Comparing Delhi Transit Modes &amp; Real-Time Fares...
          </div>
          <div style={{ fontSize: '0.82rem', color: '#64748b' }}>
            Evaluating Metro timetables, DTC bus routes, and first/last mile transfers from your location.
          </div>
        </div>
      )}

      {/* ── Journey Selection Step 3 Guide Banner (when no destination chosen yet) ── */}
      {!modeData && !isExploring && (
        <div className="journey-welcome-banner">
          <div className="journey-welcome-icon-box">
            <Sparkles size={24} color="#0284c7" />
          </div>
          <div className="journey-welcome-text">
            <h4>Ready for Step 3: Choose Your Delhi Destination</h4>
            <p>
              Tap any quick landmark chip above (e.g. <strong>MAIT, Red Fort, Connaught Place</strong>) or type any college, monument, or metro station to compare all 5 Delhi transit modes with real-time timetables and official fares.
            </p>
          </div>
        </div>
      )}

      {/* ── Mode Combinations & Fare Comparison Matrix ────────────────────────── */}
      {modeData && !isExploring && (
        <div className="modes-comparison-section">
          <div className="modes-section-headline">
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)' }}>
                Available Transportation Combinations & Routes
              </h3>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Door-to-Door Distance: {modeData.straight_line_distance_km} km (Road: ~{modeData.road_distance_km} km) • Select your preferred path below:
              </p>
            </div>
          </div>

          <div className="mode-cards-grid">
            {modeData.modes.map((mode) => {
              const isSelected = selectedModeId === mode.mode_id;
              const isMetro = mode.mode_id === 'metro';
              const isBus = mode.mode_id === 'bus';
              const isMultimodal = mode.mode_id === 'multimodal';
              const isAuto = mode.mode_id === 'auto';
              const isCab = mode.mode_id === 'cab';

              return (
                <div
                  key={mode.mode_id}
                  className={`mode-card ${isSelected ? 'selected' : ''}`}
                  onClick={() => handleModeChange(mode)}
                  role="button"
                  tabIndex={0}
                >
                  <div className="mode-card-top">
                    <div className="mode-card-icon-title">
                      <div className={`mode-icon-circle ${mode.mode_id}`}>
                        {isMetro && <TrainTrack size={20} />}
                        {isBus && <Bus size={20} />}
                        {isMultimodal && <Layers size={20} />}
                        {isAuto && <span style={{ fontSize: '1.1rem' }}>🛺</span>}
                        {isCab && <Car size={20} />}
                      </div>
                      <div>
                        <div className="mode-card-title">{mode.title}</div>
                        <div className="mode-card-metrics">
                          <span>~{Math.round(mode.estimated_duration_minutes)} mins</span>
                          <span>•</span>
                          <span>{mode.estimated_distance_km} km</span>
                        </div>
                      </div>
                    </div>

                    <div className="mode-card-fare">
                      <span className="fare-amount">₹{Math.round(mode.fare_inr)}</span>
                      <span className="fare-label">Fare</span>
                    </div>
                  </div>

                  <div className="mode-card-breakdown">
                    {mode.fare_breakdown}
                  </div>

                  <div className="mode-card-tags">
                    {mode.optimization_tags.map((tag, tIdx) => (
                      <span key={tIdx} className={`mode-tag ${tIdx === 0 ? 'primary-tag' : ''}`}>
                        {tag}
                      </span>
                    ))}
                  </div>

                  <div className="mode-card-footer">
                    {isSelected ? (
                      <div className="selected-indicator">
                        <CheckCircle2 size={14} color="#0f766e" />
                        <span>Active Mode</span>
                      </div>
                    ) : (
                      <div className="unselected-prompt">
                        <span>Select Mode</span>
                        <ChevronRight size={13} />
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* ── Stop Selection According to Chosen Mode ───────────────────────── */}
          {currentModeOption && (
            <div className="mode-customization-panel">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.85rem' }}>
                <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-main)', margin: 0, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Layers size={16} color="var(--primary)" />
                  Customize Stops &amp; Route Optimization for {currentModeOption.title}
                </h4>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  Auto-optimized candidate stations &amp; stops
                </span>
              </div>

              <div className="custom-stops-row">
                {/* Boarding Stop Choice */}
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label" style={{ fontSize: '0.8rem' }}>
                    1. Boarding Stop / Station
                  </label>
                  <select
                    className="form-input"
                    value={chosenOriginStopId}
                    onChange={(e) => {
                      setChosenOriginStopId(e.target.value);
                      const finalDest = chosenDestStopId || destStop?.stop_id || modeData?.destination_stop?.stop_id;
                      if (e.target.value && finalDest) {
                        onPlanRoute({
                          origin_stop_id: e.target.value,
                          destination_stop_id: finalDest,
                          departure_date: travelDate,
                          departure_time: `${travelTime}:00`,
                          criterion: selectedCriterion,
                          mode_preference: getModePref(selectedModeId, e.target.value, finalDest),
                          max_transfers: 3,
                          max_walk_meters: 800,
                        });
                      }
                    }}
                    style={{ fontSize: '0.85rem' }}
                  >
                    {currentModeOption.candidate_origin_stops.map((stop) => (
                      <option key={stop.stop_id} value={stop.stop_id}>
                        {stop.stop_name} ({stop.stop_id.startsWith('metro_') ? 'Metro' : 'Bus'})
                      </option>
                    ))}
                    {originStop && !currentModeOption.candidate_origin_stops.some((s) => s.stop_id === originStop.stop_id) && (
                      <option value={originStop.stop_id}>
                        {originStop.stop_name} ({originStop.stop_id.startsWith('metro_') ? 'Metro' : 'Bus'})
                      </option>
                    )}
                  </select>
                </div>

                {/* Destination Stop Choice */}
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label" style={{ fontSize: '0.8rem' }}>
                    2. Alighting Stop / Station
                  </label>
                  <select
                    className="form-input"
                    value={chosenDestStopId}
                    onChange={(e) => {
                      setChosenDestStopId(e.target.value);
                      const finalOrigin = chosenOriginStopId || originStop?.stop_id || modeData?.origin_stop?.stop_id;
                      if (finalOrigin && e.target.value) {
                        onPlanRoute({
                          origin_stop_id: finalOrigin,
                          destination_stop_id: e.target.value,
                          departure_date: travelDate,
                          departure_time: `${travelTime}:00`,
                          criterion: selectedCriterion,
                          mode_preference: getModePref(selectedModeId, finalOrigin, e.target.value),
                          max_transfers: 3,
                          max_walk_meters: 800,
                        });
                      }
                    }}
                    style={{ fontSize: '0.85rem' }}
                  >
                    {currentModeOption.candidate_destination_stops.map((stop) => (
                      <option key={stop.stop_id} value={stop.stop_id}>
                        {stop.stop_name} ({stop.stop_id.startsWith('metro_') ? 'Metro' : 'Bus'})
                      </option>
                    ))}
                    {destStop && !currentModeOption.candidate_destination_stops.some((s) => s.stop_id === destStop.stop_id) && (
                      <option value={destStop.stop_id}>
                        {destStop.stop_name} ({destStop.stop_id.startsWith('metro_') ? 'Metro' : 'Bus'})
                      </option>
                    )}
                  </select>
                </div>

                {/* Optimization Parameters (Distance vs Fare vs Balanced) */}
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label" style={{ fontSize: '0.8rem' }}>
                    3. Prioritize Optimization
                  </label>
                  <div className="optimization-btn-group">
                    <button
                      type="button"
                      className={`opt-btn ${selectedCriterion === 'fastest' ? 'active' : ''}`}
                      onClick={() => handleCriterionChange('fastest')}
                      title="Prioritize lowest total travel duration"
                    >
                      <Zap size={13} />
                      <span>Fastest</span>
                    </button>
                    <button
                      type="button"
                      className={`opt-btn ${selectedCriterion === 'cheapest' ? 'active' : ''}`}
                      onClick={() => handleCriterionChange('cheapest')}
                      title="Prioritize lowest transit fare"
                    >
                      <Coins size={13} />
                      <span>Cheapest</span>
                    </button>
                    <button
                      type="button"
                      className={`opt-btn ${selectedCriterion === 'balanced' ? 'active' : ''}`}
                      onClick={() => handleCriterionChange('balanced')}
                      title="Minimize pedestrian transfers"
                    >
                      <Scale size={13} />
                      <span>Balanced</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Plan / Refresh Journey Button */}
              <button
                type="button"
                className="btn btn-primary journey-update-route-btn"
                onClick={handlePlanJourney}
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    <span>Calculating Optimal Timetable &amp; Transfers...</span>
                  </>
                ) : (
                  <>
                    <span>Update Route for {currentModeOption.title}</span>
                    <ArrowRight size={18} className="btn-arrow-icon" />
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
