import React, { useState, useEffect, useRef } from 'react';
import { MapPin, Navigation, ArrowUpDown, Clock, Calendar, Search, Loader2, TrainTrack, Bus } from 'lucide-react';
import { SafarSetuAPI, StopItem, PlanRouteParams } from '../lib/api';

const isMetroStop = (stop: StopItem) => {
  return stop.stop_id.startsWith('metro_') || stop.stop_name.toLowerCase().includes('metro');
};

interface JourneySearchProps {
  onPlanRoute: (params: PlanRouteParams) => void;
  isLoading: boolean;
  initialOrigin?: StopItem | null;
  initialDestination?: StopItem | null;
}

export const JourneySearch: React.FC<JourneySearchProps> = ({
  onPlanRoute,
  isLoading,
  initialOrigin,
  initialDestination,
}) => {
  // Origin State
  const [originQuery, setOriginQuery] = useState(initialOrigin?.stop_name || '');
  const [originStop, setOriginStop] = useState<StopItem | null>(initialOrigin || null);
  const [originSuggestions, setOriginSuggestions] = useState<StopItem[]>([]);
  const [isOriginLoading, setIsOriginLoading] = useState(false);
  const [showOriginDropdown, setShowOriginDropdown] = useState(false);

  // Destination State
  const [destinationQuery, setDestinationQuery] = useState(initialDestination?.stop_name || '');
  const [destinationStop, setDestinationStop] = useState<StopItem | null>(initialDestination || null);
  const [destinationSuggestions, setDestinationSuggestions] = useState<StopItem[]>([]);
  const [isDestLoading, setIsDestLoading] = useState(false);
  const [showDestDropdown, setShowDestDropdown] = useState(false);

  // Time & Date State
  const getTodayDateStr = () => {
    // DTC GTFS calendar ended March 2024; we default to a realistic calendar date or today
    const now = new Date();
    return now.toISOString().split('T')[0];
  };

  const getCurrentTimeStr = () => {
    const now = new Date();
    const hrs = String(now.getHours()).padStart(2, '0');
    const mins = String(now.getMinutes()).padStart(2, '0');
    return `${hrs}:${mins}`;
  };

  const [travelDate, setTravelDate] = useState<string>(getTodayDateStr());
  const [travelTime, setTravelTime] = useState<string>(getCurrentTimeStr());
  const [criterion, setCriterion] = useState<'fastest' | 'cheapest' | 'balanced'>('fastest');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Sync if initial props change
  useEffect(() => {
    if (initialOrigin) {
      setOriginStop(initialOrigin);
      setOriginQuery(initialOrigin.stop_name);
    }
  }, [initialOrigin]);

  useEffect(() => {
    if (initialDestination) {
      setDestinationStop(initialDestination);
      setDestinationQuery(initialDestination.stop_name);
    }
  }, [initialDestination]);

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
      } catch (err) {
        setOriginSuggestions([]);
      } finally {
        setIsOriginLoading(false);
      }
    }, 280);

    return () => clearTimeout(timer);
  }, [originQuery, originStop]);

  // Debounced Destination Search
  useEffect(() => {
    if (!destinationQuery.trim() || (destinationStop && destinationStop.stop_name === destinationQuery.trim())) {
      setDestinationSuggestions([]);
      return;
    }

    const timer = setTimeout(async () => {
      setIsDestLoading(true);
      try {
        const res = await SafarSetuAPI.searchStops(destinationQuery.trim(), 8);
        setDestinationSuggestions(res.results || []);
        setShowDestDropdown(true);
      } catch (err) {
        setDestinationSuggestions([]);
      } finally {
        setIsDestLoading(false);
      }
    }, 280);

    return () => clearTimeout(timer);
  }, [destinationQuery, destinationStop]);

  const handleSwap = () => {
    const tempStop = originStop;
    const tempQuery = originQuery;

    setOriginStop(destinationStop);
    setOriginQuery(destinationQuery);

    setDestinationStop(tempStop);
    setDestinationQuery(tempQuery);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    let activeOrigin = originStop;
    let activeDest = destinationStop;

    // Auto-resolve origin if user typed without clicking dropdown
    if (!activeOrigin && originQuery.trim()) {
      if (originSuggestions.length > 0) {
        activeOrigin = originSuggestions[0];
        setOriginStop(activeOrigin);
        setOriginQuery(activeOrigin.stop_name);
      } else {
        try {
          const res = await SafarSetuAPI.searchStops(originQuery.trim(), 1);
          if (res.results && res.results.length > 0) {
            activeOrigin = res.results[0];
            setOriginStop(activeOrigin);
            setOriginQuery(activeOrigin.stop_name);
          }
        } catch {
          // Fall through
        }
      }
    }

    // Auto-resolve destination if user typed without clicking dropdown
    if (!activeDest && destinationQuery.trim()) {
      if (destinationSuggestions.length > 0) {
        activeDest = destinationSuggestions[0];
        setDestinationStop(activeDest);
        setDestinationQuery(activeDest.stop_name);
      } else {
        try {
          const res = await SafarSetuAPI.searchStops(destinationQuery.trim(), 1);
          if (res.results && res.results.length > 0) {
            activeDest = res.results[0];
            setDestinationStop(activeDest);
            setDestinationQuery(activeDest.stop_name);
          }
        } catch {
          // Fall through
        }
      }
    }

    if (!activeOrigin) {
      setErrorMsg('Please select a valid origin stop from suggestions or search for a stop name.');
      return;
    }
    if (!activeDest) {
      setErrorMsg('Please select a valid destination stop from suggestions or search for a stop name.');
      return;
    }
    if (activeOrigin.stop_id === activeDest.stop_id) {
      setErrorMsg('Origin and destination stops cannot be the same location.');
      return;
    }

    onPlanRoute({
      origin_stop_id: activeOrigin.stop_id,
      destination_stop_id: activeDest.stop_id,
      departure_date: travelDate,
      departure_time: travelTime,
      criterion,
      max_transfers: 3,
      max_walk_meters: 800,
    });
  };

  return (
    <form className="search-card" onSubmit={handleSubmit}>
      <h2 className="search-title">
        <Navigation size={18} color="var(--primary)" />
        <span>Plan Your Journey</span>
      </h2>

      {errorMsg && (
        <div className="alert-box alert-danger" role="alert">
          {errorMsg}
        </div>
      )}

      {/* Origin Stop */}
      <div className="form-group">
        <label className="form-label" htmlFor="origin-input">
          From (Origin Stop)
        </label>
        <div className="input-with-icon">
          <MapPin size={16} className="input-icon" />
          <input
            id="origin-input"
            type="text"
            className="form-input"
            placeholder="Search Delhi stop (e.g., Kashmere Gate, AIIMS)"
            value={originQuery}
            autoComplete="off"
            onChange={(e) => {
              setOriginQuery(e.target.value);
              setOriginStop(null);
            }}
            onFocus={() => {
              if (originSuggestions.length > 0) setShowOriginDropdown(true);
            }}
          />
          {isOriginLoading && (
            <Loader2
              size={16}
              className="animate-spin"
              style={{ position: 'absolute', right: '0.75rem', color: 'var(--text-muted)' }}
            />
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
                  aria-selected={originStop?.stop_id === stop.stop_id}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    setOriginStop(stop);
                    setOriginQuery(stop.stop_name);
                    setShowOriginDropdown(false);
                  }}
                  onClick={() => {
                    setOriginStop(stop);
                    setOriginQuery(stop.stop_name);
                    setShowOriginDropdown(false);
                  }}
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 0.8rem' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0, flex: 1 }}>
                    {isMetro ? (
                      <TrainTrack size={15} color="#7c3aed" style={{ flexShrink: 0 }} />
                    ) : (
                      <Bus size={15} color="#0f766e" style={{ flexShrink: 0 }} />
                    )}
                    <span className="suggestion-name" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {stop.stop_name}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexShrink: 0 }}>
                    {isMetro ? (
                      <span className="suggestion-type-badge metro">🚇 Metro</span>
                    ) : (
                      <span className="suggestion-type-badge bus">🚌 Bus</span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Swap Button */}
      <div className="swap-btn-container">
        <button
          type="button"
          className="btn-swap"
          onClick={handleSwap}
          title="Swap origin and destination"
          aria-label="Swap origin and destination"
        >
          <ArrowUpDown size={15} />
        </button>
      </div>

      {/* Destination Stop */}
      <div className="form-group">
        <label className="form-label" htmlFor="dest-input">
          To (Destination Stop)
        </label>
        <div className="input-with-icon">
          <Navigation size={16} className="input-icon" />
          <input
            id="dest-input"
            type="text"
            className="form-input"
            placeholder="Search destination stop (e.g., Nehru Place, Anand Vihar)"
            value={destinationQuery}
            autoComplete="off"
            onChange={(e) => {
              setDestinationQuery(e.target.value);
              setDestinationStop(null);
            }}
            onFocus={() => {
              if (destinationSuggestions.length > 0) setShowDestDropdown(true);
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

        {showDestDropdown && destinationSuggestions.length > 0 && (
          <ul className="suggestions-dropdown" role="listbox">
            {destinationSuggestions.map((stop) => {
              const isMetro = isMetroStop(stop);
              return (
                <li
                  key={stop.stop_id}
                  className="suggestion-item"
                  role="option"
                  aria-selected={destinationStop?.stop_id === stop.stop_id}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    setDestinationStop(stop);
                    setDestinationQuery(stop.stop_name);
                    setShowDestDropdown(false);
                  }}
                  onClick={() => {
                    setDestinationStop(stop);
                    setDestinationQuery(stop.stop_name);
                    setShowDestDropdown(false);
                  }}
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 0.8rem' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0, flex: 1 }}>
                    {isMetro ? (
                      <TrainTrack size={15} color="#7c3aed" style={{ flexShrink: 0 }} />
                    ) : (
                      <Bus size={15} color="#0f766e" style={{ flexShrink: 0 }} />
                    )}
                    <span className="suggestion-name" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {stop.stop_name}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexShrink: 0 }}>
                    {isMetro ? (
                      <span className="suggestion-type-badge metro">🚇 Metro</span>
                    ) : (
                      <span className="suggestion-type-badge bus">🚌 Bus</span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Date & Time */}
      <div className="date-time-row">
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label" htmlFor="travel-date">
            Departure Date
          </label>
          <input
            id="travel-date"
            type="date"
            className="form-input"
            value={travelDate}
            onChange={(e) => setTravelDate(e.target.value)}
          />
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label" htmlFor="travel-time">
            Time
          </label>
          <input
            id="travel-time"
            type="time"
            className="form-input"
            value={travelTime}
            onChange={(e) => setTravelTime(e.target.value)}
          />
        </div>
      </div>

      {/* Objective Criteria */}
      <div className="form-group" style={{ marginTop: '0.9rem' }}>
        <label className="form-label">Route Preference</label>
        <div className="criterion-selector">
          <button
            type="button"
            className={`criterion-btn ${criterion === 'fastest' ? 'active' : ''}`}
            onClick={() => setCriterion('fastest')}
          >
            Fastest
          </button>
          <button
            type="button"
            className={`criterion-btn ${criterion === 'cheapest' ? 'active' : ''}`}
            onClick={() => setCriterion('cheapest')}
          >
            Cheapest
          </button>
          <button
            type="button"
            className={`criterion-btn ${criterion === 'balanced' ? 'active' : ''}`}
            onClick={() => setCriterion('balanced')}
          >
            Balanced
          </button>
        </div>
      </div>

      {/* Submit Button */}
      <button
        type="submit"
        className="btn-primary"
        style={{ width: '100%', padding: '0.75rem' }}
        disabled={isLoading}
      >
        {isLoading ? (
          <>
            <Loader2 size={18} className="animate-spin" />
            <span>Calculating Route...</span>
          </>
        ) : (
          <>
            <Search size={18} />
            <span>Find Routes</span>
          </>
        )}
      </button>
    </form>
  );
};

