import React from 'react';
import { Bus, Bookmark, Settings, MessageSquare, LogIn, LogOut, Radio, User, TrainTrack } from 'lucide-react';
import { UserSession } from '../lib/supabase';
import { RealtimeStatusResponse } from '../lib/api';

interface HeaderProps {
  session: UserSession | null;
  realtimeStatus: RealtimeStatusResponse | null;
  onOpenAuth: () => void;
  onSignOut: () => void;
  onOpenSaved: () => void;
  onOpenPreferences: () => void;
  onOpenFeedback: () => void;
  onOpenAccount?: () => void;
  onOpenMetroStatus?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  session,
  realtimeStatus,
  onOpenAuth,
  onSignOut,
  onOpenSaved,
  onOpenPreferences,
  onOpenFeedback,
  onOpenAccount,
  onOpenMetroStatus,
}) => {
  const isLiveActive = Boolean(
    realtimeStatus?.enabled &&
    realtimeStatus?.live_tracking_verified &&
    realtimeStatus?.cached_vehicles_count > 0
  );

  return (
    <header className="app-header">
      <div className="container header-content">
        <div className="logo-group">
          <div className="logo-icon" aria-hidden="true">
            <Bus size={22} />
          </div>
          <div className="logo-text">
            <h1>SafarSetu</h1>
            <span>Delhi / NCR Multimodal Transit</span>
          </div>
        </div>

        <div className="header-actions">
          {/* Live OTD telemetry indicator badge */}
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
                  : realtimeStatus.api_key_configured
                  ? 'Delhi OTD Live Feed: Awaiting verification or currently silent'
                  : 'Delhi OTD Live Feed: API Key unconfigured. Operating on static schedules.'
              }
            >
              <span className="pulse-dot" />
              <span>
                {isLiveActive
                  ? `Live OTD (${realtimeStatus.cached_vehicles_count})`
                  : realtimeStatus.api_key_configured
                  ? 'Live OTD Standby'
                  : 'Live Feed Inactive'}
              </span>
            </div>
          ) : (
            <div className="live-badge unavailable">
              <Radio size={14} />
              <span>Offline Mode</span>
            </div>
          )}

          {/* DMRC Metro Real-Time Status Badge */}
          {onOpenMetroStatus && (
            <button
              type="button"
              className="btn-metro-badge"
              onClick={onOpenMetroStatus}
              title="View Delhi Metro (DMRC) Real-Time Line Status & Headways"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.45rem',
                padding: '0.35rem 0.75rem',
                borderRadius: '9999px',
                border: '1px solid #bbf7d0',
                background: '#f0fdf4',
                color: '#15803d',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <TrainTrack size={14} color="#15803d" />
              <span>DMRC Metro: Normal</span>
              <span className="live-dot" style={{ width: 6, height: 6, background: '#16a34a' }} />
            </button>
          )}

          {session ? (
            <>
              <button
                className="btn-icon"
                onClick={onOpenSaved}
                title="View your saved journeys"
                aria-label="Saved Journeys"
              >
                <Bookmark size={16} />
                <span>Saved</span>
              </button>

              <button
                className="btn-icon"
                onClick={onOpenPreferences}
                title="User Preferences"
                aria-label="User Preferences"
              >
                <Settings size={16} />
              </button>

              {onOpenAccount && (
                <button
                  className="btn-icon"
                  onClick={onOpenAccount}
                  title="My Account Settings"
                  aria-label="My Account"
                >
                  <User size={16} />
                  <span>Account</span>
                </button>
              )}

              <button
                className="btn-icon"
                onClick={onOpenFeedback}
                title="Send Commuter Feedback"
                aria-label="Commuter Feedback"
              >
                <MessageSquare size={16} />
              </button>

              <button
                className="btn-icon"
                onClick={onSignOut}
                title={`Signed in as ${session.user.email || 'Commuter'}. Click to sign out.`}
                aria-label="Sign Out"
              >
                <LogOut size={16} />
                <span>Sign Out</span>
              </button>
            </>
          ) : (
            <>
              <button
                className="btn-icon"
                onClick={onOpenFeedback}
                title="Send Commuter Feedback"
                aria-label="Commuter Feedback"
              >
                <MessageSquare size={16} />
              </button>

              <button className="btn-primary" onClick={onOpenAuth} aria-label="Sign In">
                <LogIn size={16} />
                <span>Sign In</span>
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
};

