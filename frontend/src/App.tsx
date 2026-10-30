import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import {
  Header,
} from './components/Header';
import { DataFreshnessBanner } from './components/DataFreshnessBanner';
import { JourneySearch } from './components/JourneySearch';
import { ModeExplorerSearch } from './components/ModeExplorerSearch';
import { RouteCard } from './components/RouteCard';
import { RouteMap } from './components/RouteMap';
import { SavedJourneysModal } from './components/SavedJourneysModal';
import { PreferencesModal } from './components/PreferencesModal';
import { FeedbackModal } from './components/FeedbackModal';
import { MetroStatusModal } from './components/MetroStatusModal';
import { SignInPage } from './pages/SignInPage';
import { SignUpPage } from './pages/SignUpPage';
import { AccountPage } from './pages/AccountPage';
import {
  SafarSetuAPI,
  HealthResponse,
  RealtimeStatusResponse,
  RoutePlanResponse,
  PlanRouteParams,
  Journey,
  StopItem,
} from './lib/api';
import { supabaseAuth, UserSession } from './lib/supabase';
import {
  Compass,
  AlertTriangle,
  Clock,
  ShieldAlert,
  ServerCrash,
  Navigation,
  MapPin,
} from 'lucide-react';

/* ──────────────────────────────────────────────────────────
   Protected Route — redirects unauthenticated users to /signin
   ────────────────────────────────────────────────────────── */
const ProtectedRoute: React.FC<{ session: UserSession | null; children: React.ReactNode }> = ({
  session,
  children,
}) => {
  if (!session) {
    return <Navigate to="/signin" replace />;
  }
  return <>{children}</>;
};

/* ──────────────────────────────────────────────────────────
   Main Transit Planner (protected)
   ────────────────────────────────────────────────────────── */
const PlannerPage: React.FC<{
  session: UserSession | null;
  health: HealthResponse | null;
  realtimeStatus: RealtimeStatusResponse | null;
  backendError: string | null;
  isPlanning: boolean;
  routePlan: RoutePlanResponse | null;
  planError: string | null;
  selectedOrigin: StopItem | null;
  selectedDest: StopItem | null;
  savedOpen: boolean;
  prefOpen: boolean;
  feedbackOpen: boolean;
  metroOpen: boolean;
  onPlanRoute: (params: PlanRouteParams) => void;
  onSaveJourney: (journey: Journey) => void;
  onOpenSaved: () => void;
  onCloseSaved: () => void;
  onOpenPref: () => void;
  onClosePref: () => void;
  onOpenFeedback: () => void;
  onCloseFeedback: () => void;
  onOpenMetro: () => void;
  onCloseMetro: () => void;
  onSignOut: () => void;
  onOpenAccount: () => void;
  emergencyRerouteInfo: { stop_name: string; original_origin: string } | null;
  onDismissEmergency: () => void;
  onRerouteFromStop: (stop: { stop_id: string; stop_name: string; lat?: number; lon?: number }) => void;
  onRerouteFromGPS: () => void;
}> = ({
  session,
  health,
  realtimeStatus,
  backendError,
  isPlanning,
  routePlan,
  planError,
  selectedOrigin,
  selectedDest,
  savedOpen,
  prefOpen,
  feedbackOpen,
  metroOpen,
  onPlanRoute,
  onSaveJourney,
  onOpenSaved,
  onCloseSaved,
  onOpenPref,
  onClosePref,
  onOpenFeedback,
  onCloseFeedback,
  onOpenMetro,
  onCloseMetro,
  onSignOut,
  onOpenAccount,
  emergencyRerouteInfo,
  onDismissEmergency,
  onRerouteFromStop,
  onRerouteFromGPS,
}) => {
  const [searchMode, setSearchMode] = useState<'explorer' | 'standard'>('explorer');
  const [selectedJourneyIndex, setSelectedJourneyIndex] = useState<number>(0);
  const [selectedLegIndex, setSelectedLegIndex] = useState<number | null>(null);

  useEffect(() => {
    setSelectedJourneyIndex(0);
    setSelectedLegIndex(null);
  }, [routePlan]);

  return (
    <div className="app-layout">
      {/* Top Header */}
      <Header
        session={session}
        realtimeStatus={realtimeStatus}
        onOpenAuth={() => {}}   /* auth is now page-based; sign-in is /signin */
        onSignOut={onSignOut}
        onOpenSaved={onOpenSaved}
        onOpenPreferences={onOpenPref}
        onOpenFeedback={onOpenFeedback}
        onOpenAccount={onOpenAccount}
        onOpenMetroStatus={onOpenMetro}
      />

      {/* Freshness Banner */}
      <DataFreshnessBanner health={health} />

      {/* Main Commuter Workspace */}
      <main className="container app-main">
        {backendError && (
          <div className="alert-box alert-danger" style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <ServerCrash size={20} />
            <div>
              <strong>Backend Connectivity Notice:</strong> {backendError}. Ensure the SafarSetu FastAPI server is running on port 8000.
            </div>
          </div>
        )}

        {/* Mode Switcher Tabs */}
        <div className="search-mode-switcher-bar" style={{ marginBottom: '1.25rem' }}>
          <div className="search-mode-tabs" style={{ maxWidth: '480px', margin: '0 auto 1.5rem auto' }}>
            <button
              type="button"
              className={`search-mode-tab ${searchMode === 'explorer' ? 'active' : ''}`}
              onClick={() => setSearchMode('explorer')}
            >
              <Compass size={16} /> Destination &amp; Multi-Modal Modes
            </button>
            <button
              type="button"
              className={`search-mode-tab ${searchMode === 'standard' ? 'active' : ''}`}
              onClick={() => setSearchMode('standard')}
            >
              <Navigation size={16} /> Stop-to-Stop Planner
            </button>
          </div>
        </div>

        {searchMode === 'explorer' ? (
          /* ── Explorer Mode: Full-Width Command Card with Side-by-Side Map Results ── */
          <div className="explorer-view-wrapper">
            <ModeExplorerSearch
              onPlanRoute={onPlanRoute}
              isLoading={isPlanning}
            />

            {/* Calendar Validity Warning if any */}
            {routePlan?.calendar_validity_note && (
              <div className="alert-box alert-info" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '1.25rem' }}>
                <Clock size={16} color="var(--secondary)" />
                <span>{routePlan.calendar_validity_note}</span>
              </div>
            )}

            {/* Data freshness warnings from engine */}
            {routePlan?.data_freshness_warnings && routePlan.data_freshness_warnings.length > 0 && (
              <div className="alert-box alert-info" style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginTop: '1rem' }}>
                {routePlan.data_freshness_warnings.map((w, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <AlertTriangle size={15} color="var(--accent-dark)" />
                    <span>{w}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Route Planning Error */}
            {planError && (
              <div className="alert-box alert-danger" style={{ marginTop: '1.25rem' }}>
                <ShieldAlert size={18} style={{ display: 'inline', marginRight: 8, verticalAlign: 'middle' }} />
                <strong>Routing Advisory:</strong> {planError}
              </div>
            )}

            {/* Emergency Re-route Notice */}
            {emergencyRerouteInfo && (
              <div className="alert-box alert-danger" style={{ marginTop: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#fef2f2', border: '1.5px solid #fecaca' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                  <span style={{ fontSize: '1.25rem' }}>🚨</span>
                  <div>
                    <strong style={{ fontSize: '0.92rem', color: '#991b1b', display: 'block' }}>
                      Emergency Re-route Active
                    </strong>
                    <span style={{ fontSize: '0.8rem', color: '#7f1d1d' }}>
                      Transport cancelled at <strong>{emergencyRerouteInfo.stop_name}</strong>. Showing fail-safe alternative Metro, Bus &amp; Cab routes to your destination.
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={onDismissEmergency}
                  style={{
                    background: '#ffffff',
                    border: '1px solid #fca5a5',
                    color: '#991b1b',
                    padding: '0.3rem 0.65rem',
                    borderRadius: '4px',
                    fontSize: '0.76rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Dismiss
                </button>
              </div>
            )}

            {/* Results Display with Side Map */}
            {routePlan && routePlan.journeys.length > 0 ? (
              <div className="results-layout-with-map" style={{ marginTop: '1.5rem' }}>
                {/* Left Column: Route Cards */}
                <div className="routes-list-column">
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '0.75rem',
                      paddingBottom: '0.6rem',
                      borderBottom: '1.5px solid var(--border)',
                    }}
                  >
                    <div>
                      <h3 style={{ fontSize: '1.15rem', fontWeight: 800, margin: 0, color: 'var(--text-main)' }}>
                        {routePlan.journeys.length} Route Choice{routePlan.journeys.length > 1 ? 's' : ''} Available
                      </h3>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        Ranked by {routePlan.criterion} &bull; Click any card to highlight route on the map
                      </span>
                    </div>
                  </div>

                  {routePlan.journeys.map((journey, idx) => (
                    <RouteCard
                      key={idx}
                      journey={journey}
                      index={idx}
                      onSaveJourney={onSaveJourney}
                      isSelected={selectedJourneyIndex === idx}
                      onSelect={() => {
                        setSelectedJourneyIndex(idx);
                        setSelectedLegIndex(null);
                      }}
                      activeLegIndex={selectedJourneyIndex === idx ? selectedLegIndex : null}
                      onSelectLeg={(legIdx) => {
                        setSelectedJourneyIndex(idx);
                        setSelectedLegIndex(legIdx);
                      }}
                      onRerouteFromStop={onRerouteFromStop}
                    />
                  ))}
                </div>

                {/* Right Column: Sticky Live Route Map */}
                <div className="map-side-column">
                  <div className="map-sticky-card">
                    <div className="map-card-bar">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div className="pulse-dot" style={{ background: '#10b981', width: 8, height: 8 }} />
                        <strong style={{ fontSize: '0.88rem', color: 'var(--text-main)' }}>Interactive Route Map</strong>
                      </div>
                      <span style={{ fontSize: '0.78rem', background: '#e2e8f0', color: '#1e293b', padding: '0.2rem 0.6rem', borderRadius: '4px', fontWeight: 700 }}>
                        Viewing Route {selectedJourneyIndex + 1} of {routePlan.journeys.length}
                      </span>
                    </div>
                    <RouteMap
                      journey={routePlan.journeys[selectedJourneyIndex] || null}
                      activeLegIndex={selectedLegIndex}
                      onSelectLeg={(legIdx) => setSelectedLegIndex(legIdx)}
                      onRerouteFromStop={onRerouteFromStop}
                      onRerouteFromGPS={onRerouteFromGPS}
                    />
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          /* ── Standard Mode: Classic 2-Column Stop-to-Stop Planner ── */
          <div className="planner-grid">
            <aside>
              <JourneySearch
                onPlanRoute={onPlanRoute}
                isLoading={isPlanning}
                initialOrigin={selectedOrigin}
                initialDestination={selectedDest}
              />

              {/* Delhi Transit System Quick Facts */}
              {health && (() => {
                const primary = health.data_sources?.[0] || health.sources?.[0];
                return (
                  <div
                    style={{
                      marginTop: '1.25rem',
                      padding: '1rem',
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-md)',
                      fontSize: '0.82rem',
                    }}
                  >
                    <div style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
                      Transit System Snapshot
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', color: 'var(--text-muted)' }}>
                      <div>Stops: <strong style={{ color: 'var(--text-main)' }}>{primary?.stops_count?.toLocaleString() || '6,342'}</strong></div>
                      <div>Routes: <strong style={{ color: 'var(--text-main)' }}>{primary?.routes_count?.toLocaleString() || '2,964'}</strong></div>
                      <div>Trips: <strong style={{ color: 'var(--text-main)' }}>{primary?.trips_count?.toLocaleString() || '78,515'}</strong></div>
                      <div>Graph Nodes: <strong style={{ color: 'var(--text-main)' }}>{health.graph_nodes?.toLocaleString() || '11,466'}</strong></div>
                    </div>
                  </div>
                );
              })()}
            </aside>

            {/* Right Column: Comparison & Results */}
            <section className="results-container">
              {routePlan?.calendar_validity_note && (
                <div className="alert-box alert-info" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Clock size={16} color="var(--secondary)" />
                  <span>{routePlan.calendar_validity_note}</span>
                </div>
              )}

              {routePlan?.data_freshness_warnings && routePlan.data_freshness_warnings.length > 0 && (
                <div className="alert-box alert-info" style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                  {routePlan.data_freshness_warnings.map((w, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <AlertTriangle size={15} color="var(--accent-dark)" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}

              {planError && (
                <div className="alert-box alert-danger">
                  <ShieldAlert size={18} style={{ display: 'inline', marginRight: 8, verticalAlign: 'middle' }} />
                  <strong>Routing Advisory:</strong> {planError}
                </div>
              )}

              {routePlan && routePlan.journeys.length > 0 ? (
                <div className="results-layout-with-map">
                  <div className="routes-list-column">
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginBottom: '0.4rem',
                        paddingBottom: '0.4rem',
                        borderBottom: '1px solid var(--border)',
                      }}
                    >
                      <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0 }}>
                        Found {routePlan.journeys.length} Journey Option{routePlan.journeys.length > 1 ? 's' : ''}
                      </h3>
                      <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                        Ranked by {routePlan.criterion}
                      </span>
                    </div>

                    {routePlan.journeys.map((journey, idx) => (
                      <RouteCard
                        key={idx}
                        journey={journey}
                        index={idx}
                        onSaveJourney={onSaveJourney}
                        isSelected={selectedJourneyIndex === idx}
                        onSelect={() => {
                          setSelectedJourneyIndex(idx);
                          setSelectedLegIndex(null);
                        }}
                        activeLegIndex={selectedJourneyIndex === idx ? selectedLegIndex : null}
                        onSelectLeg={(legIdx) => {
                          setSelectedJourneyIndex(idx);
                          setSelectedLegIndex(legIdx);
                        }}
                        onRerouteFromStop={onRerouteFromStop}
                      />
                    ))}
                  </div>

                  <div className="map-side-column">
                    <div className="map-sticky-card">
                      <div className="map-card-bar">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                          <div className="pulse-dot" style={{ background: '#10b981', width: 8, height: 8 }} />
                          <strong style={{ fontSize: '0.85rem', color: 'var(--text-main)' }}>Live Route Map</strong>
                        </div>
                        <span style={{ fontSize: '0.75rem', background: '#e2e8f0', color: '#334155', padding: '0.2rem 0.55rem', borderRadius: '4px', fontWeight: 600 }}>
                          Route {selectedJourneyIndex + 1} of {routePlan.journeys.length}
                        </span>
                      </div>
                      <RouteMap
                        journey={routePlan.journeys[selectedJourneyIndex] || null}
                        activeLegIndex={selectedLegIndex}
                        onSelectLeg={(legIdx) => setSelectedLegIndex(legIdx)}
                        onRerouteFromStop={onRerouteFromStop}
                        onRerouteFromGPS={onRerouteFromGPS}
                      />
                    </div>
                  </div>
                </div>
              ) : !isPlanning && !planError ? (
                <div className="empty-state">
                  <div className="empty-state-icon">
                    <Compass size={28} />
                  </div>
                  <h3>Plan your transit route across Delhi &amp; NCR</h3>
                  <p style={{ maxWidth: '440px', margin: '0 auto', fontSize: '0.9rem', lineHeight: '1.5' }}>
                    Search for verified bus stops like <strong>Kashmere Gate</strong>, <strong>AIIMS</strong>, or <strong>Anand Vihar</strong>.
                    SafarSetu computes timetable-accurate direct and multi-transfer journeys with clear pedestrian transfer links.
                  </p>
                </div>
              ) : null}
            </section>
          </div>
        )}
      </main>

      {/* Modals */}
      <SavedJourneysModal
        isOpen={savedOpen}
        onClose={onCloseSaved}
        onSelectJourney={(_originId, _destId) => {}}
      />

      <PreferencesModal
        isOpen={prefOpen}
        onClose={onClosePref}
      />

      <FeedbackModal
        isOpen={feedbackOpen}
        onClose={onCloseFeedback}
      />

      <MetroStatusModal
        isOpen={metroOpen}
        onClose={onCloseMetro}
      />
    </div>
  );
};

/* ──────────────────────────────────────────────────────────
   Root App — manages global state, auth, and routes
   ────────────────────────────────────────────────────────── */
export const App: React.FC = () => {
  const navigate = useNavigate();

  // Authentication State
  const [session, setSession] = useState<UserSession | null>(supabaseAuth.getSession());

  // System & Health State
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [realtimeStatus, setRealtimeStatus] = useState<RealtimeStatusResponse | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);

  // Search & Routing State
  const [isPlanning, setIsPlanning] = useState(false);
  const [routePlan, setRoutePlan] = useState<RoutePlanResponse | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [lastPlanParams, setLastPlanParams] = useState<PlanRouteParams | null>(null);
  const [emergencyRerouteInfo, setEmergencyRerouteInfo] = useState<{ stop_name: string; original_origin: string } | null>(null);

  // Prefill state from Saved Journeys
  const [selectedOrigin, setSelectedOrigin] = useState<StopItem | null>(null);
  const [selectedDest, setSelectedDest] = useState<StopItem | null>(null);

  // Modal Visibility State
  const [savedOpen, setSavedOpen] = useState(false);
  const [prefOpen, setPrefOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [metroOpen, setMetroOpen] = useState(false);

  // Initialize Auth Listener & Health Fetch
  useEffect(() => {
    const unsub = supabaseAuth.onAuthStateChange((newSession) => {
      setSession(newSession);
    });

    fetchSystemStatus();

    // Periodic status refresh
    const interval = setInterval(fetchSystemStatus, 30000);
    return () => {
      unsub();
      clearInterval(interval);
    };
  }, []);

  const fetchSystemStatus = async () => {
    try {
      const [hRes, rtRes] = await Promise.all([
        SafarSetuAPI.getHealth().catch(() => null),
        SafarSetuAPI.getRealtimeStatus().catch(() => null),
      ]);
      if (hRes) {
        setHealth(hRes);
        setBackendError(null);
      } else {
        setBackendError('Backend service is currently unreachable on localhost:8000');
      }
      if (rtRes) {
        setRealtimeStatus(rtRes);
      }
    } catch (e: any) {
      setBackendError('Failed to connect to SafarSetu transit server.');
    }
  };

  const handlePlanRoute = async (params: PlanRouteParams) => {
    setIsPlanning(true);
    setPlanError(null);
    setRoutePlan(null);
    setLastPlanParams(params);

    try {
      const res = await SafarSetuAPI.planRoute(params);
      setRoutePlan(res);
      if (res.journeys.length === 0 && res.no_route_reason) {
        setPlanError(res.no_route_reason);
      }
    } catch (err: any) {
      setPlanError(err.message || 'Routing calculation failed. Check stop IDs and departure time.');
    } finally {
      setIsPlanning(false);
    }
  };

  const handleRerouteFromStop = async (stop: { stop_id: string; stop_name: string; lat?: number; lon?: number }) => {
    const destId = lastPlanParams?.destination_stop_id || routePlan?.destination_stop_id;
    if (!destId) {
      alert('Destination not set. Please search for a destination first.');
      return;
    }
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:00`;
    const todayStr = now.toISOString().split('T')[0];

    setEmergencyRerouteInfo({
      stop_name: stop.stop_name,
      original_origin: routePlan?.journeys?.[0]?.legs?.[0]?.from_stop_name || 'Original Station',
    });

    handlePlanRoute({
      origin_stop_id: stop.stop_id,
      destination_stop_id: destId,
      departure_date: todayStr,
      departure_time: timeStr,
      criterion: 'fastest',
      mode_preference: 'all',
      max_transfers: 3,
      max_walk_meters: 1000,
    });
  };

  const handleRerouteFromGPS = async () => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const res = await SafarSetuAPI.getNearbyStops(pos.coords.latitude, pos.coords.longitude, 3500, 5);
          if (res.results && res.results.length > 0) {
            const closest = res.results[0];
            handleRerouteFromStop({
              stop_id: closest.stop_id,
              stop_name: closest.stop_name,
              lat: closest.stop_lat,
              lon: closest.stop_lon,
            });
          } else {
            alert('No verified Delhi transit stops found within 3.5 km of your GPS location.');
          }
        } catch (err) {
          console.error('GPS reroute error:', err);
        }
      },
      (err) => {
        alert(`Location access denied or unavailable (${err.message}). Click on any station on the map instead.`);
      }
    );
  };

  const handleSaveJourney = async (journey: Journey) => {
    if (!session) {
      navigate('/signin');
      return;
    }

    if (!routePlan) return;

    try {
      const originName = journey.legs[0]?.from_stop_name || routePlan.origin_stop_id;
      const destName = journey.legs[journey.legs.length - 1]?.to_stop_name || routePlan.destination_stop_id;

      await SafarSetuAPI.saveJourney({
        journey_name: `${originName} to ${destName}`,
        origin_stop_id: routePlan.origin_stop_id,
        destination_stop_id: routePlan.destination_stop_id,
        departure_time_preference: journey.departure_time,
        ranking_criterion_preference: journey.rank_criterion,
      });
    } catch (err: any) {
      alert(`Could not save journey: ${err.message}`);
    }
  };

  const handleSignOut = async () => {
    await supabaseAuth.signOut();
    navigate('/signin');
  };

  const handleSelectSavedJourney = async (originId: string, destId: string) => {
    setSelectedOrigin({
      stop_id: originId,
      stop_name: originId,
      stop_lat: 0,
      stop_lon: 0,
    });
    setSelectedDest({
      stop_id: destId,
      stop_name: destId,
      stop_lat: 0,
      stop_lon: 0,
    });
    setSavedOpen(false);
  };

  return (
    <Routes>
      {/* Public auth routes */}
      <Route path="/signin" element={<SignInPage />} />
      <Route path="/signup" element={<SignUpPage />} />

      {/* Protected account settings */}
      <Route
        path="/account"
        element={
          <ProtectedRoute session={session}>
            <AccountPage session={session} />
          </ProtectedRoute>
        }
      />

      {/* Protected main planner — default landing after login */}
      <Route
        path="/"
        element={
          <ProtectedRoute session={session}>
            <PlannerPage
              session={session}
              health={health}
              realtimeStatus={realtimeStatus}
              backendError={backendError}
              isPlanning={isPlanning}
              routePlan={routePlan}
              planError={planError}
              selectedOrigin={selectedOrigin}
              selectedDest={selectedDest}
              savedOpen={savedOpen}
              prefOpen={prefOpen}
              feedbackOpen={feedbackOpen}
              metroOpen={metroOpen}
              onPlanRoute={handlePlanRoute}
              onSaveJourney={handleSaveJourney}
              onOpenSaved={() => setSavedOpen(true)}
              onCloseSaved={() => setSavedOpen(false)}
              onOpenPref={() => setPrefOpen(true)}
              onClosePref={() => setPrefOpen(false)}
              onOpenFeedback={() => setFeedbackOpen(true)}
              onCloseFeedback={() => setFeedbackOpen(false)}
              onOpenMetro={() => setMetroOpen(true)}
              onCloseMetro={() => setMetroOpen(false)}
              onSignOut={handleSignOut}
              onOpenAccount={() => navigate('/account')}
              emergencyRerouteInfo={emergencyRerouteInfo}
              onDismissEmergency={() => setEmergencyRerouteInfo(null)}
              onRerouteFromStop={handleRerouteFromStop}
              onRerouteFromGPS={handleRerouteFromGPS}
            />
          </ProtectedRoute>
        }
      />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default App;
