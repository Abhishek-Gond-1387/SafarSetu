import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bus,
  LogIn,
  UserPlus,
  ArrowRight,
  Compass,
  MapPin,
  TrainTrack,
  Radio,
  CheckCircle2,
  Sparkles,
} from 'lucide-react';
import { UserSession } from '../lib/supabase';
import { RealtimeStatusResponse } from '../lib/api';
import heroBg from '../assets/hero-delhi-transit.jpg';

interface WelcomeLandingPageProps {
  session: UserSession | null;
  realtimeStatus: RealtimeStatusResponse | null;
}

export const WelcomeLandingPage: React.FC<WelcomeLandingPageProps> = ({
  session,
  realtimeStatus,
}) => {
  const navigate = useNavigate();

  const isLiveActive = Boolean(
    realtimeStatus?.enabled &&
    realtimeStatus?.live_tracking_verified &&
    realtimeStatus?.cached_vehicles_count > 0
  );

  return (
    <div className="welcome-landing-wrapper">
      {/* ── Landing Header ── */}
      <header className="landing-header">
        <div className="container landing-header-content">
          <div className="logo-group">
            <div className="logo-icon" aria-hidden="true">
              <Bus size={20} />
            </div>
            <div className="logo-text">
              <div className="logo-title-row">
                <h1>SafarSetu</h1>
                <span className="logo-hindi-pill">सफ़रसेतु</span>
              </div>
              <span>Delhi / NCR Multimodal Transit</span>
            </div>
          </div>

          <div className="header-actions">
            {realtimeStatus ? (
              <div
                className={`live-badge ${
                  isLiveActive
                    ? 'fresh'
                    : realtimeStatus.last_poll_status === 'stale'
                    ? 'stale'
                    : 'unavailable'
                }`}
                title={
                  isLiveActive
                    ? `Delhi OTD Live Feed Connected (${realtimeStatus.cached_vehicles_count} active GPS vehicles)`
                    : 'Delhi OTD Live Feed Standby'
                }
              >
                <span className="pulse-dot" />
                <span>
                  {isLiveActive
                    ? `Live OTD (${realtimeStatus.cached_vehicles_count})`
                    : 'Live Feed Standby'}
                </span>
              </div>
            ) : null}

            {session ? (
              <button
                type="button"
                className="btn-primary"
                onClick={() => navigate('/planner')}
              >
                <span>Journey Selection</span>
                <ArrowRight size={16} />
              </button>
            ) : (
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  type="button"
                  className="btn-icon"
                  onClick={() => navigate('/signin')}
                >
                  <LogIn size={15} />
                  <span>Sign In</span>
                </button>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => navigate('/signup')}
                >
                  <UserPlus size={15} />
                  <span>Sign Up</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ── Main Hero Section with Uploaded Delhi Transit Image & Color-Grading ── */}
      <main className="landing-hero-section">
        {/* Color-Graded Background Media */}
        <div
          className="hero-bg-media"
          style={{ backgroundImage: `url(${heroBg || '/hero-delhi-transit.jpg'})` }}
        >
          {/* Layer 1: Left-to-Right Atmospheric Scrim for High-Contrast Text */}
          <div className="hero-scrim-primary" />
          {/* Layer 2: Vertical Ambient Fade */}
          <div className="hero-scrim-vertical" />
          {/* Layer 3: Warm Sunrise Screen Gradient */}
          <div className="hero-scrim-warmth" />
        </div>

        <div className="container landing-hero-container">
          <div className="landing-content-card">
            {/* Step 1 Workflow Pill */}
            <div className="workflow-step-pill">
              <span className="step-num">Step 1 of 3</span>
              <span className="step-divider">•</span>
              <span className="step-title">Welcome to SafarSetu</span>
            </div>

            {/* Core 3-Line Punchy Headline */}
            <h1 className="landing-main-title">
              <span className="title-line">Your city.</span>
              <span className="title-line">Every route.</span>
              <span className="title-line title-highlight">One tap.</span>
            </h1>

            {/* Exact Tagline Requested */}
            <p className="landing-subtitle">
              Real-time bus positions, timetable-accurate journey planning, and transfer guidance across Delhi's 6,342 stops.
            </p>

            {/* Workflow Navigation Action Group */}
            <div className="landing-actions-box">
              {session ? (
                <div className="logged-in-action-wrap">
                  <div className="logged-in-notice">
                    <CheckCircle2 size={18} color="#34d399" />
                    <span>Signed in as <strong>{session.user.email || 'Commuter'}</strong></span>
                  </div>
                  <button
                    type="button"
                    className="landing-primary-btn"
                    onClick={() => navigate('/planner')}
                  >
                    <Compass size={18} />
                    <span>Proceed to Journey Selection</span>
                    <ArrowRight size={18} />
                  </button>
                </div>
              ) : (
                <div className="guest-action-wrap">
                  <button
                    type="button"
                    className="landing-primary-btn"
                    onClick={() => navigate('/signin')}
                  >
                    <span>Proceed to Sign In / Sign Up</span>
                    <ArrowRight size={18} />
                  </button>

                  <button
                    type="button"
                    className="landing-secondary-btn"
                    onClick={() => navigate('/signup')}
                  >
                    <UserPlus size={16} />
                    <span>Create New Account</span>
                  </button>

                  <button
                    type="button"
                    className="landing-guest-link"
                    onClick={() => navigate('/planner')}
                    title="Skip sign-in and explore journeys directly"
                  >
                    <span>Skip to Journey Selection as Guest</span>
                    <ArrowRight size={13} />
                  </button>
                </div>
              )}
            </div>

            {/* Exact 3 Stats Requested */}
            <div className="landing-stats-grid">
              <div className="landing-stat-item">
                <div className="stat-icon-wrap cyan">
                  <MapPin size={20} />
                </div>
                <div className="stat-text-wrap">
                  <div className="stat-big-num">6,342</div>
                  <div className="stat-label-text">Bus Stops</div>
                </div>
              </div>

              <div className="landing-stat-item">
                <div className="stat-icon-wrap emerald">
                  <Bus size={20} />
                </div>
                <div className="stat-text-wrap">
                  <div className="stat-big-num">2,964</div>
                  <div className="stat-label-text">Routes</div>
                </div>
              </div>

              <div className="landing-stat-item">
                <div className="stat-icon-wrap amber">
                  <TrainTrack size={20} />
                </div>
                <div className="stat-text-wrap">
                  <div className="stat-big-num">78K+</div>
                  <div className="stat-label-text">Trips Loaded</div>
                </div>
              </div>
            </div>

            {/* Visual 3-Step Breadcrumb Progress Bar */}
            <div className="workflow-footer-bar">
              <div className="workflow-step-node active">
                <span className="node-num">1</span>
                <span className="node-label">Welcome</span>
              </div>
              <div className="workflow-step-line" />
              <div className="workflow-step-node">
                <span className="node-num">2</span>
                <span className="node-label">Sign In / Sign Up</span>
              </div>
              <div className="workflow-step-line" />
              <div className="workflow-step-node">
                <span className="node-num">3</span>
                <span className="node-label">Journey Selection</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

