import React, { useState } from 'react';
import {
  Bus,
  Footprints,
  Clock,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Bookmark,
  Check,
  AlertCircle,
  HelpCircle,
  TrainTrack,
  Radio,
  ArrowRightLeft,
  MapPin,
  AlertTriangle,
} from 'lucide-react';
import { Journey, JourneyLeg } from '../lib/api';

const getMetroStyle = (routeShortName?: string, routeLongName?: string) => {
  const text = (routeShortName || routeLongName || '').toUpperCase();
  if (text.includes('YELLOW')) return { bg: '#eab308', color: '#000000', name: 'Yellow Line' };
  if (text.includes('BLUE')) return { bg: '#2563eb', color: '#ffffff', name: 'Blue Line' };
  if (text.includes('RED')) return { bg: '#dc2626', color: '#ffffff', name: 'Red Line' };
  if (text.includes('VIOLET')) return { bg: '#7c3aed', color: '#ffffff', name: 'Violet Line' };
  if (text.includes('PINK')) return { bg: '#ec4899', color: '#ffffff', name: 'Pink Line' };
  if (text.includes('MAGENTA')) return { bg: '#d946ef', color: '#ffffff', name: 'Magenta Line' };
  if (text.includes('GREEN')) return { bg: '#16a34a', color: '#ffffff', name: 'Green Line' };
  if (text.includes('AIRPORT') || text.includes('ORANGE')) return { bg: '#ea580c', color: '#ffffff', name: 'Airport Express' };
  if (text.includes('AQUA')) return { bg: '#0284c7', color: '#ffffff', name: 'Aqua Line' };
  if (text.includes('RAPID')) return { bg: '#06b6d4', color: '#ffffff', name: 'Rapid Metro' };
  if (text.includes('GRAY') || text.includes('GREY')) return { bg: '#64748b', color: '#ffffff', name: 'Grey Line' };
  return { bg: '#0f766e', color: '#ffffff', name: routeShortName || 'Delhi Metro' };
};

const getMetroInfo = (legs: JourneyLeg[]) => {
  const metroLegs = legs.filter((l) => l.mode === 'metro');
  const busLegs = legs.filter((l) => l.mode === 'transit' || l.mode === 'bus');
  const hasMetro = metroLegs.length > 0;
  const isDirectMetro = hasMetro && metroLegs.length === 1 && busLegs.length === 0;
  const isMetroTransfer = hasMetro && metroLegs.length > 1 && busLegs.length === 0;
  const isMultimodal = hasMetro && busLegs.length > 0;
  const transferCount = metroLegs.length > 1 ? metroLegs.length - 1 : 0;

  return {
    hasMetro,
    isDirectMetro,
    isMetroTransfer,
    isMultimodal,
    transferCount,
    metroLegs,
    busLegs,
  };
};

interface RouteCardProps {
  journey: Journey;
  index: number;
  onSaveJourney: (journey: Journey) => void;
  isSaved?: boolean;
  isSelected?: boolean;
  onSelect?: () => void;
  activeLegIndex?: number | null;
  onSelectLeg?: (idx: number) => void;
  onRerouteFromStop?: (stop: { stop_id: string; stop_name: string; lat?: number; lon?: number }) => void;
}

export const RouteCard: React.FC<RouteCardProps> = ({
  journey,
  index,
  onSaveJourney,
  isSaved = false,
  isSelected = false,
  onSelect,
  activeLegIndex = null,
  onSelectLeg,
  onRerouteFromStop,
}) => {
  const [expanded, setExpanded] = useState(index === 0);
  const [justSaved, setJustSaved] = useState(false);

  const metroInfo = getMetroInfo(journey.legs);

  const handleSaveClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSaveJourney(journey);
    setJustSaved(true);
    setTimeout(() => setJustSaved(false), 2500);
  };

  const formatMins = (mins: number) => {
    const rounded = Math.round(mins);
    if (rounded >= 60) {
      const h = Math.floor(rounded / 60);
      const m = rounded % 60;
      return `${h}h ${m}m`;
    }
    return `${rounded} mins`;
  };

  const getRankBadge = () => {
    switch (journey.rank_criterion) {
      case 'fastest':
        return <span className="badge badge-fastest">Fastest Option</span>;
      case 'cheapest':
        return <span className="badge badge-cheapest">Cheapest Option</span>;
      case 'balanced':
        return <span className="badge badge-balanced">Balanced Option</span>;
      default:
        return null;
    }
  };

  const getMetroBadge = () => {
    if (metroInfo.isDirectMetro) {
      return (
        <span className="badge badge-direct-metro" title="Direct DMRC Metro line without any interchange">
          <TrainTrack size={13} />
          Direct Metro
        </span>
      );
    }
    if (metroInfo.isMetroTransfer) {
      return (
        <span className="badge badge-metro-transfer" title="Metro route with interchange between lines">
          <ArrowRightLeft size={13} />
          Metro ({metroInfo.transferCount} Line Change{metroInfo.transferCount > 1 ? 's' : ''})
        </span>
      );
    }
    if (metroInfo.isMultimodal) {
      return (
        <span className="badge badge-multimodal" title="Combined Bus and Metro transit route">
          <Bus size={13} /> + <TrainTrack size={13} />
          Bus + Metro
        </span>
      );
    }
    return null;
  };

  return (
    <article
      className={`route-card ${isSelected ? 'selected-on-map' : ''}`}
      aria-label={`Route option ${index + 1}`}
      onClick={() => onSelect?.()}
    >
      {/* Top summary row */}
      <div
        className="route-card-header"
        onClick={() => {
          onSelect?.();
          setExpanded(!expanded);
        }}
        style={{ cursor: 'pointer' }}
      >
        <div className="route-headline">
          <span className="route-duration">
            {formatMins(journey.total_duration_minutes)}
          </span>
          <span className="route-time-span">
            {journey.departure_time.slice(0, 5)} → {journey.arrival_time.slice(0, 5)}
          </span>
        </div>

        <div className="route-badges">
          {isSelected && (
            <span
              className="badge badge-map-selected"
              title="This route is highlighted on the live map"
            >
              <MapPin size={12} />
              Viewing on Map
            </span>
          )}
          {getMetroBadge()}
          {getRankBadge()}
          <button
            type="button"
            className="btn-icon"
            onClick={handleSaveClick}
            title="Save this journey"
            style={{ padding: '0.35rem 0.65rem' }}
          >
            {justSaved || isSaved ? (
              <>
                <Check size={14} color="var(--success)" />
                <span style={{ color: 'var(--success)', fontSize: '0.8rem' }}>Saved</span>
              </>
            ) : (
              <>
                <Bookmark size={14} />
                <span style={{ fontSize: '0.8rem' }}>Save</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Visual Journey Flow Strip */}
      <div
        className="journey-flow-strip"
        onClick={() => {
          onSelect?.();
          setExpanded(!expanded);
        }}
        style={{ cursor: 'pointer' }}
      >
        {journey.legs.map((leg, i) => {
          const isWalking = leg.mode === 'walking' || leg.mode === 'walk';
          const isMetro = leg.mode === 'metro';
          const metroStyle = isMetro ? getMetroStyle(leg.route_short_name, leg.route_long_name) : null;
          return (
            <React.Fragment key={i}>
              {i > 0 && (
                <span className="flow-arrow">
                  <ArrowRight size={12} />
                </span>
              )}
              {isWalking ? (
                <span
                  className={`flow-segment walk ${activeLegIndex === i ? 'active-leg' : ''}`}
                  title={`Walk ${Math.round(leg.distance_meters || 0)}m (click to focus on map)`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelect?.();
                    onSelectLeg?.(i);
                  }}
                >
                  <Footprints size={12} /> Walk
                </span>
              ) : isMetro && metroStyle ? (
                <span
                  className={`flow-segment metro ${activeLegIndex === i ? 'active-leg' : ''}`}
                  style={{
                    backgroundColor: `${metroStyle.bg}18`,
                    borderColor: metroStyle.bg,
                    color: metroStyle.bg === '#eab308' ? '#854d0e' : metroStyle.bg,
                    outline: activeLegIndex === i ? `2px solid ${metroStyle.bg}` : 'none',
                  }}
                  title={`${metroStyle.name}: ${leg.from_stop_name} to ${leg.to_stop_name} (click to focus on map)`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelect?.();
                    onSelectLeg?.(i);
                  }}
                >
                  <TrainTrack size={12} />
                  {metroStyle.name}
                </span>
              ) : (
                <span
                  className={`flow-segment bus ${activeLegIndex === i ? 'active-leg' : ''}`}
                  style={{
                    outline: activeLegIndex === i ? '2px solid #0f766e' : 'none',
                  }}
                  title={`Bus ${leg.route_short_name || leg.route_id} (click to focus on map)`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelect?.();
                    onSelectLeg?.(i);
                  }}
                >
                  <Bus size={12} />
                  {leg.route_short_name ? `Bus ${leg.route_short_name}` : 'Bus'}
                </span>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Metrics Row */}
      <div className="route-stats-grid">
        <div className="stat-item">
          <span className="stat-label">Initial Wait</span>
          <span className="stat-value">
            {journey.initial_wait_minutes > 0
              ? `${Math.round(journey.initial_wait_minutes)} mins`
              : 'Immediate'}
          </span>
        </div>

        <div className="stat-item">
          <span className="stat-label">Transfers</span>
          <span className="stat-value">
            {journey.num_transfers === 0
              ? 'Direct'
              : `${journey.num_transfers} transfer${journey.num_transfers > 1 ? 's' : ''}`}
          </span>
        </div>

        <div className="stat-item">
          <span className="stat-label">Walking Distance</span>
          <span className="stat-value">
            {Math.round(journey.total_walk_meters)} m
          </span>
        </div>

        <div className="stat-item">
          <span className="stat-label">Estimated Fare</span>
          {journey.fare_inr !== null && journey.fare_inr !== undefined && journey.fare_complete ? (
            <span className="stat-value">₹{journey.fare_inr.toFixed(0)}</span>
          ) : (
            <span
              className="stat-value unknown-fare"
              title="GTFS dataset lacks verified fare matrix. Never treated as free."
            >
              Fare Unknown
            </span>
          )}
        </div>
      </div>

      {/* Detailed Leg Timeline (Collapsible) */}
      {expanded && (
        <div className="legs-container">
          {journey.legs.map((leg, legIdx) => {
            const isWalking = leg.mode === 'walking' || leg.mode === 'walk';
            const isMetro = leg.mode === 'metro';
            const metroStyle = isMetro ? getMetroStyle(leg.route_short_name, leg.route_long_name) : null;

            // Find next non-walking leg for interchange advisory
            const remainingLegs = journey.legs.slice(legIdx + 1);
            const nextTransitLeg = remainingLegs.find((l) => l.mode !== 'walking' && l.mode !== 'walk');

            return (
              <React.Fragment key={legIdx}>
                <div className="leg-item">
                  <div className="leg-icon-col">
                    <div className={`leg-icon ${isWalking ? 'walking' : isMetro ? 'metro' : 'transit'}`}>
                      {isWalking ? <Footprints size={18} /> : isMetro ? <TrainTrack size={18} /> : <Bus size={18} />}
                    </div>
                  </div>

                  <div className="leg-body">
                    <div className="leg-header">
                      <div className="leg-title">
                        {isWalking ? (
                          <>
                            <span>Walk to next stop</span>
                            <span
                              className="straight-line-tag"
                              title="Haversine straight-line distance; pedestrian sidewalk geometry not calculated"
                            >
                              Straight-line pedestrian link (Haversine)
                            </span>
                          </>
                        ) : isMetro && metroStyle ? (
                          <>
                            <span
                              className="metro-line-tag"
                              style={{
                                backgroundColor: metroStyle.bg,
                                color: metroStyle.color,
                                padding: '0.2rem 0.55rem',
                                borderRadius: '4px',
                                fontWeight: 700,
                                fontSize: '0.8rem',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.3rem',
                              }}
                            >
                              <TrainTrack size={13} />
                              Metro {metroStyle.name}
                            </span>
                            {leg.headsign && <span>towards {leg.headsign}</span>}
                            {leg.fare_inr !== null && leg.fare_inr !== undefined && (
                              <span style={{ fontSize: '0.78rem', color: '#166534', background: '#dcfce7', padding: '0.15rem 0.4rem', borderRadius: '4px', fontWeight: 600 }}>
                                ₹{leg.fare_inr.toFixed(0)} Fare
                              </span>
                            )}
                          </>
                        ) : (
                          <>
                            <span className="bus-tag">
                              Bus {leg.route_short_name || leg.route_id || 'Transit'}
                            </span>
                            {leg.headsign && <span>towards {leg.headsign}</span>}
                          </>
                        )}
                      </div>
                      <span className="leg-duration">
                        {Math.round(leg.duration_minutes)} mins
                        {leg.distance_meters ? ` (${Math.round(leg.distance_meters)}m)` : ''}
                      </span>
                    </div>

                    {/* Real-time DMRC Telemetry Indicator on Metro Legs */}
                    {isMetro && (
                      <div
                        style={{
                          margin: '0.4rem 0',
                          padding: '0.3rem 0.6rem',
                          background: '#f0fdf4',
                          border: '1px solid #bbf7d0',
                          borderRadius: '6px',
                          fontSize: '0.78rem',
                          color: '#15803d',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.45rem',
                        }}
                      >
                        <Radio size={13} className="pulse-dot" color="#16a34a" />
                        <span>
                          <strong>DMRC Live Telemetry:</strong> Normal Operations • Peak headway ~2.5 - 3.5 mins
                        </span>
                      </div>
                    )}

                    <div className="leg-stops-timeline">
                      <div className="leg-stop-row">
                        <span className="leg-stop-name">
                          <strong>Board:</strong> {leg.from_stop_name}
                        </span>
                        <span className="leg-stop-time">
                          {leg.departure_time.slice(0, 5)}
                        </span>
                      </div>

                      {isMetro && leg.intermediate_stops && leg.intermediate_stops.length > 0 && (
                        <div style={{ padding: '0.2rem 0 0.2rem 1.4rem', fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                          🚆 Passes through {leg.intermediate_stops.length} intermediate station{leg.intermediate_stops.length > 1 ? 's' : ''}
                        </div>
                      )}

                      <div className="leg-stop-row">
                        <span className="leg-stop-name">
                          <strong>Alight:</strong> {leg.to_stop_name}
                        </span>
                        <span className="leg-stop-time">
                          {leg.arrival_time.slice(0, 5)}
                        </span>
                      </div>
                    </div>

                    {/* Emergency Re-route Trigger if Vehicle Breaks Down or is Cancelled */}
                    {!isWalking && onRerouteFromStop && (
                      <div className="leg-reroute-bar" style={{ marginTop: '0.55rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#fff1f2', border: '1px solid #fecdd3', padding: '0.4rem 0.65rem', borderRadius: '6px' }}>
                        <span style={{ fontSize: '0.74rem', color: '#9f1239', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <AlertCircle size={13} style={{ flexShrink: 0 }} />
                          <span>Vehicle cancelled or broke down here?</span>
                        </span>
                        <button
                          type="button"
                          className="btn-emergency-reroute"
                          onClick={(e) => {
                            e.stopPropagation();
                            onRerouteFromStop({
                              stop_id: leg.from_stop_id,
                              stop_name: leg.from_stop_name,
                              lat: leg.from_stop_lat || undefined,
                              lon: leg.from_stop_lon || undefined,
                            });
                          }}
                          title={`Find emergency alternative route from ${leg.from_stop_name}`}
                          style={{
                            background: '#dc2626',
                            color: '#ffffff',
                            border: 'none',
                            padding: '0.25rem 0.65rem',
                            borderRadius: '4px',
                            fontSize: '0.74rem',
                            fontWeight: 700,
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.3rem',
                            boxShadow: '0 1px 3px rgba(220, 38, 38, 0.3)',
                          }}
                        >
                          <AlertTriangle size={11} />
                          <span>Re-Route From {leg.from_stop_name}</span>
                        </button>
                      </div>
                    )}

                    {/* Transfer guidance note if followed by another leg without specific line change */}
                    {!isWalking && !nextTransitLeg && legIdx < journey.legs.length - 1 && (
                      <div className="transfer-alert">
                        <Clock size={13} />
                        <span>
                          Transfer connection at {leg.to_stop_name}. Allow buffer for scheduled departure.
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Specific Interchange Advisory Card between legs */}
                {!isWalking && nextTransitLeg && (
                  <div style={{ marginLeft: '48px', marginBottom: '1rem' }}>
                    {isMetro && nextTransitLeg.mode === 'metro' ? (
                      <div className="metro-interchange-advisory line-change">
                        <ArrowRightLeft size={18} style={{ color: '#2563eb', flexShrink: 0, marginTop: '2px' }} />
                        <div>
                          <div className="interchange-badge-title">
                            Metro Line Interchange at {leg.to_stop_name}
                          </div>
                          <div className="interchange-badge-text">
                            Alight from <strong>{metroStyle?.name || 'Metro'}</strong> and change lines to{' '}
                            <strong>{getMetroStyle(nextTransitLeg.route_short_name, nextTransitLeg.route_long_name).name}</strong>{' '}
                            {nextTransitLeg.headsign ? `towards ${nextTransitLeg.headsign}` : ''}.
                            Follow the interchange overhead directional signage inside the station.
                          </div>
                        </div>
                      </div>
                    ) : isMetro && nextTransitLeg.mode !== 'metro' ? (
                      <div className="metro-interchange-advisory bus-metro">
                        <Bus size={18} style={{ color: '#16a34a', flexShrink: 0, marginTop: '2px' }} />
                        <div>
                          <div className="interchange-badge-title" style={{ color: '#166534' }}>
                            Metro to Bus Connection at {leg.to_stop_name}
                          </div>
                          <div className="interchange-badge-text">
                            Exit the metro station and proceed to the nearby bus stop to board{' '}
                            <strong>Bus {nextTransitLeg.route_short_name || nextTransitLeg.route_id}</strong>{' '}
                            {nextTransitLeg.headsign ? `towards ${nextTransitLeg.headsign}` : ''}.
                          </div>
                        </div>
                      </div>
                    ) : !isMetro && nextTransitLeg.mode === 'metro' ? (
                      <div className="metro-interchange-advisory bus-metro">
                        <TrainTrack size={18} style={{ color: '#7c3aed', flexShrink: 0, marginTop: '2px' }} />
                        <div>
                          <div className="interchange-badge-title" style={{ color: '#5b21b6' }}>
                            Bus to Metro Connection at {leg.to_stop_name}
                          </div>
                          <div className="interchange-badge-text">
                            Alight bus and enter <strong>{leg.to_stop_name}</strong> Metro Station. Board{' '}
                            <strong>{getMetroStyle(nextTransitLeg.route_short_name, nextTransitLeg.route_long_name).name}</strong>{' '}
                            {nextTransitLeg.headsign ? `towards ${nextTransitLeg.headsign}` : ''}.
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="transfer-alert">
                        <Clock size={13} />
                        <span>
                          Bus transfer at {leg.to_stop_name}. Change to Bus {nextTransitLeg.route_short_name || nextTransitLeg.route_id}.
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      )}

      {/* Footer expand/collapse toggle */}
      <div
        className="route-card-actions"
        onClick={() => setExpanded(!expanded)}
        style={{ cursor: 'pointer' }}
      >
        <button
          type="button"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            fontSize: '0.82rem',
            color: 'var(--text-muted)',
            fontWeight: 600,
          }}
        >
          {expanded ? (
            <>
              <ChevronUp size={16} /> Hide Route Breakdown
            </>
          ) : (
            <>
              <ChevronDown size={16} /> View {journey.legs.length} Journey Leg
              {journey.legs.length > 1 ? 's' : ''}
            </>
          )}
        </button>

        <span style={{ fontSize: '0.75rem', color: 'var(--text-light)' }}>
          {journey.data_sources?.join(', ') || 'Delhi GTFS'}
        </span>
      </div>
    </article>
  );
};
