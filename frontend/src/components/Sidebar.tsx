import React, { useState, useEffect } from 'react';
import {
  Bus,
  LifeBuoy,
  Bookmark,
  Settings,
  MessageSquare,
  LogIn,
  LogOut,
  Radio,
  User,
  TrainTrack,
  Mic,
  Compass,
  Menu,
  X,
  Navigation,
  Download,
  Smartphone,
  CheckCircle2,
} from 'lucide-react';
import { usePWAState, promptPWAInstall, PWAState } from '../pwa';
import { IOSInstallModal } from './IOSInstallModal';
import { UserSession } from '../lib/supabase';
import { RealtimeStatusResponse } from '../lib/api';

export interface SidebarProps {
  session: UserSession | null;
  realtimeStatus: RealtimeStatusResponse | null;
  onOpenAuth: () => void;
  onSignOut: () => void;
  onOpenSaved: () => void;
  onOpenPreferences: () => void;
  onOpenFeedback: () => void;
  onOpenAccount?: () => void;
  onOpenMetroStatus?: () => void;
  onOpenVoice?: () => void;
  onOpenLost?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  session,
  realtimeStatus,
  onOpenAuth,
  onSignOut,
  onOpenSaved,
  onOpenPreferences,
  onOpenFeedback,
  onOpenAccount,
  onOpenMetroStatus,
  onOpenVoice,
  onOpenLost,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [pwaState, setPwaState] = useState<PWAState>({
    isInstallable: false,
    isInstalled: false,
    isIOS: false,
    isOffline: false,
  });
  const [showIOSModal, setShowIOSModal] = useState(false);
  const [isPromptDismissed, setIsPromptDismissed] = useState(false);

  useEffect(() => {
    const unsub = usePWAState((state) => setPwaState(state));
    return unsub;
  }, []);

  const handleInstallClick = async () => {
    const result = await promptPWAInstall();
    if (result === 'ios') {
      setShowIOSModal(true);
    } else if (result === 'unsupported' && !pwaState.isInstalled) {
      alert(
        'To install SafarSetu on this browser, open your browser menu (⋮ or ...) and select "Install SafarSetu" or "Add to Home Screen".'
      );
    }
  };

  // Close drawer on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  // Prevent background scroll when sidebar is open on mobile
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const isLiveActive = Boolean(
    realtimeStatus?.enabled &&
    realtimeStatus?.live_tracking_verified &&
    realtimeStatus?.cached_vehicles_count > 0
  );

  const handleNavClick = (callback?: () => void) => {
    if (callback) callback();
    setIsOpen(false);
  };

  const scrollToPlanner = () => {
    const el = document.getElementById('planner-explorer-section');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    setIsOpen(false);
  };

  const userInitials = session?.user?.email
    ? session.user.email.slice(0, 2).toUpperCase()
    : 'SS';

  return (
    <>
      {/* ── Top Navigation Bar with the 3 Lines (Hamburger) on the Left ── */}
      <header className="app-top-nav-bar" aria-label="Main Application Header">
        <div className="nav-bar-container">
          {/* Left: 3 Lines Hamburger Menu Button + SafarSetu Brand */}
          <div className="nav-left-group">
            <button
              type="button"
              className="nav-hamburger-btn"
              onClick={() => setIsOpen((prev) => !prev)}
              aria-label={isOpen ? 'Close navigation sidebar' : 'Open navigation sidebar'}
              aria-expanded={isOpen}
              title="Open Navigation Menu"
            >
              <div className="hamburger-icon-lines" aria-hidden="true">
                <span className={`bar ${isOpen ? 'bar-open-1' : ''}`} />
                <span className={`bar ${isOpen ? 'bar-open-2' : ''}`} />
                <span className={`bar ${isOpen ? 'bar-open-3' : ''}`} />
              </div>
              <span className="hamburger-text-label">Menu</span>
            </button>

            <div className="nav-brand-group" onClick={scrollToPlanner} role="button" tabIndex={0}>
              <div className="nav-brand-icon" aria-hidden="true">
                <Bus size={20} />
              </div>
              <div className="nav-brand-text">
                <div className="nav-brand-title-row">
                  <span className="nav-brand-title">SafarSetu</span>
                  <span className="logo-hindi-pill">सफ़रसेतु</span>
                </div>
                <span className="nav-brand-sub">Delhi / NCR Transit</span>
              </div>
            </div>
          </div>

          {/* Right: Quick Action Badges & Voice AI */}
          <div className="nav-right-actions">
            {/* Live OTD Telemetry */}
            {realtimeStatus ? (
              <div
                className={`nav-status-pill otd-pill ${isLiveActive
                    ? 'fresh'
                    : realtimeStatus.last_poll_status === 'stale'
                      ? 'stale'
                      : 'unavailable'
                  }`}
                title={
                  isLiveActive
                    ? `Delhi OTD Live Feed Connected (${realtimeStatus.cached_vehicles_count} active GPS vehicles)`
                    : 'Delhi OTD Live Feed: Operating on timetable schedules'
                }
              >
                <span className="pulse-dot" />
                <span className="pill-text-desktop">
                  {isLiveActive
                    ? `Live OTD (${realtimeStatus.cached_vehicles_count})`
                    : 'Live OTD Standby'}
                </span>
                <span className="pill-text-mobile">
                  {isLiveActive ? `${realtimeStatus.cached_vehicles_count} OTD` : 'OTD'}
                </span>
              </div>
            ) : null}

            {/* DMRC Metro Status Badge */}
            {onOpenMetroStatus && (
              <button
                type="button"
                className="nav-status-pill metro-pill"
                onClick={onOpenMetroStatus}
                title="View Delhi Metro (DMRC) Real-Time Line Status & Headways"
              >
                <TrainTrack size={14} />
                <span className="pill-text-desktop">DMRC: Normal</span>
                <span className="live-dot" style={{ width: 6, height: 6, background: '#16a34a' }} />
              </button>
            )}

            {/* PWA Install Prompt on Navbar with Cross Button */}
            {!pwaState.isInstalled && !isPromptDismissed && (
              <div className="nav-install-pill-box">
                <button
                  type="button"
                  className="nav-install-pill-btn"
                  onClick={handleInstallClick}
                  title="Download and install SafarSetu on your device as a native app"
                >
                  <Download size={14} />
                  <span className="pill-text-desktop">Install App</span>
                  <span className="pill-text-mobile">App</span>
                </button>
                <button
                  type="button"
                  className="nav-install-pill-close"
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsPromptDismissed(true);
                  }}
                  title="Dismiss install prompt"
                  aria-label="Dismiss install prompt"
                >
                  <X size={12} />
                </button>
              </div>
            )}

            {/* Multilingual Voice AI Trigger */}
            {onOpenVoice && (
              <button
                type="button"
                className="nav-voice-ai-btn"
                onClick={onOpenVoice}
                title="Open Multilingual AI Voice Assistant (Hindi, English, Hinglish)"
              >
                <Mic size={15} />
                <span className="btn-label-desktop">Voice AI</span>
              </button>
            )}

            {/* Commuter Account / Sign In */}
            {session ? (
              <button
                type="button"
                className="nav-account-avatar-btn"
                onClick={() => handleNavClick(onOpenAccount)}
                title={`Signed in as ${session.user.email || 'Delhi Commuter'}. Click for account settings.`}
                aria-label="Account Settings"
              >
                <span>{userInitials}</span>
              </button>
            ) : (
              <button
                type="button"
                className="nav-signin-btn"
                onClick={onOpenAuth}
                aria-label="Sign In"
              >
                <LogIn size={15} />
                <span className="btn-label-desktop">Sign In</span>
              </button>
            )}
          </div>
        </div>

        {/* PWA Install Prompt Banner on Navbar with Cross Button */}
        {!pwaState.isInstalled && !isPromptDismissed && (
          <div className="nav-pwa-banner-strip">
            <div className="nav-pwa-banner-left" onClick={handleInstallClick} role="button" tabIndex={0}>
              <div className="nav-pwa-banner-icon">
                <Download size={14} />
              </div>
              <div className="nav-pwa-banner-msg">
                <span className="pwa-bold-txt">Install SafarSetu App:</span>
                <span className="pwa-info-txt"> One-tap access, offline transit routes &amp; live metro updates.</span>
              </div>
            </div>

            <div className="nav-pwa-banner-right">
              <button
                type="button"
                className="nav-pwa-banner-install-btn"
                onClick={handleInstallClick}
              >
                Install Now
              </button>
              <button
                type="button"
                className="nav-pwa-banner-close-btn"
                onClick={() => setIsPromptDismissed(true)}
                title="Dismiss install prompt"
                aria-label="Dismiss install prompt"
              >
                <X size={14} />
              </button>
            </div>
          </div>
        )}
      </header>

      {/* ── Slide-Out Drawer Backdrop ── */}
      {isOpen && (
        <div
          className="app-sidebar-backdrop"
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* ── The 3-Lines Slide-Out Sidebar Drawer ── */}
      <aside
        className={`app-sidebar-drawer ${isOpen ? 'drawer-open' : ''}`}
        aria-label="Navigation Drawer"
        aria-hidden={!isOpen}
      >
        {/* Drawer Header */}
        <div className="drawer-header">
          <div className="drawer-brand" onClick={scrollToPlanner}>
            <div className="drawer-brand-icon" aria-hidden="true">
              <Bus size={22} />
            </div>
            <div className="drawer-brand-text">
              <div className="drawer-brand-title-row">
                <h3>SafarSetu</h3>
                <span className="logo-hindi-pill">सफ़रसेतु</span>
              </div>
              <span className="drawer-brand-sub">Delhi / NCR Transit</span>
            </div>
          </div>

          <button
            type="button"
            className="drawer-close-btn"
            onClick={() => setIsOpen(false)}
            aria-label="Close sidebar menu"
          >
            <X size={20} />
          </button>
        </div>

        {/* Voice AI Assistant Featured Card */}
        {onOpenVoice && (
          <div className="drawer-voice-card-wrapper">
            <button
              type="button"
              className="drawer-voice-action-btn"
              onClick={() => handleNavClick(onOpenVoice)}
              title="Speak with SafarSetu Multilingual AI Voice Assistant"
            >
              <div className="drawer-voice-icon-box">
                <Mic size={18} />
                <span className="pulse-ring" />
              </div>
              <div className="drawer-voice-text-box">
                <strong>Voice Assistant</strong>
                <span>Hindi • English • Hinglish</span>
              </div>
              <span className="drawer-ai-pill">AI</span>
            </button>
          </div>
        )}

        {/* Live System Feeds */}
        <div className="drawer-section">
          <span className="drawer-section-title">Live Transit Telemetry</span>

          {/* DMRC Metro Status */}
          {onOpenMetroStatus && (
            <button
              type="button"
              className="drawer-feed-item"
              onClick={() => handleNavClick(onOpenMetroStatus)}
            >
              <div className="feed-item-left">
                <div className="feed-icon-box metro-box">
                  <TrainTrack size={16} />
                </div>
                <div className="feed-item-text">
                  <strong>Delhi Metro (DMRC)</strong>
                  <span className="feed-status-green">Normal Operations</span>
                </div>
              </div>
              <span className="feed-dot green-dot" />
            </button>
          )}

          {/* DTC Bus Telemetry */}
          <div className="drawer-feed-item">
            <div className="feed-item-left">
              <div className={`feed-icon-box ${isLiveActive ? 'otd-box-active' : 'otd-box-standby'}`}>
                <Radio size={16} />
              </div>
              <div className="feed-item-text">
                <strong>DTC Bus Tracking</strong>
                <span className="feed-status-sub">
                  {isLiveActive
                    ? `${realtimeStatus?.cached_vehicles_count} GPS Vehicles Active`
                    : 'Timetable Schedules Mode'}
                </span>
              </div>
            </div>
            <span className={`feed-dot ${isLiveActive ? 'green-dot' : 'amber-dot'}`} />
          </div>
        </div>

        {/* Navigation Links */}
        <div className="drawer-section">
          <span className="drawer-section-title">Navigation &amp; Features</span>

          <nav className="drawer-nav-menu">
            <button
              type="button"
              className="drawer-nav-item active-nav-item"
              onClick={scrollToPlanner}
            >
              <Compass size={18} />
              <span>Journey Planner</span>
            </button>

            {onOpenLost && (
              <button
                type="button"
                className="drawer-nav-item drawer-nav-lost-item"
                onClick={() => handleNavClick(onOpenLost)}
              >
                <LifeBuoy size={18} />
                <span>Lost Button</span>
              </button>
            )}

            {session && (
              <button
                type="button"
                className="drawer-nav-item"
                onClick={() => handleNavClick(onOpenSaved)}
              >
                <Bookmark size={18} />
                <span>Saved Journeys</span>
              </button>
            )}

            <button
              type="button"
              className="drawer-nav-item"
              onClick={() => handleNavClick(onOpenPreferences)}
            >
              <Settings size={18} />
              <span>Preferences &amp; Filters</span>
            </button>

            <button
              type="button"
              className="drawer-nav-item"
              onClick={() => handleNavClick(onOpenFeedback)}
            >
              <MessageSquare size={18} />
              <span>Commuter Feedback</span>
            </button>

            {/* Install SafarSetu PWA App Button */}
            {!pwaState.isInstalled ? (
              <button
                type="button"
                className="drawer-nav-item drawer-install-app-btn"
                onClick={handleInstallClick}
                title="Download and install SafarSetu on your device as a native app"
              >
                <Download size={18} />
                <span>Install SafarSetu App</span>
                <span className="pwa-install-badge">INSTALL</span>
              </button>
            ) : (
              <div className="drawer-app-installed-badge">
                <CheckCircle2 size={16} color="#10b981" />
                <span>SafarSetu App Installed</span>
              </div>
            )}
          </nav>
        </div>

        {/* Commuter Account Profile & Sign In / Out at Bottom */}
        <div className="drawer-footer">
          {session ? (
            <div className="drawer-user-card">
              <div
                className="drawer-user-info"
                onClick={() => handleNavClick(onOpenAccount)}
                role="button"
                tabIndex={0}
                title="Account Settings"
              >
                <div className="drawer-avatar">{userInitials}</div>
                <div className="drawer-user-text">
                  <span className="drawer-user-name">
                    {session.user.display_name || 'Delhi Commuter'}
                  </span>
                  <span className="drawer-user-email">
                    {session.user.email || 'commuter@safarsetu'}
                  </span>
                </div>
              </div>

              <div className="drawer-user-actions">
                {onOpenAccount && (
                  <button
                    type="button"
                    className="drawer-action-btn"
                    onClick={() => handleNavClick(onOpenAccount)}
                  >
                    <User size={15} />
                    <span>Account</span>
                  </button>
                )}

                <button
                  type="button"
                  className="drawer-action-btn signout-danger"
                  onClick={() => handleNavClick(onSignOut)}
                >
                  <LogOut size={15} />
                  <span>Log Out</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="drawer-auth-cta">
              <div className="auth-cta-text">
                <strong>Sign In to SafarSetu</strong>
                <span>Sync saved journeys, live alerts &amp; route histories.</span>
              </div>
              <button
                type="button"
                className="drawer-signin-btn"
                onClick={() => handleNavClick(onOpenAuth)}
              >
                <LogIn size={16} />
                <span>Sign In / Register</span>
              </button>
            </div>
          )}
        </div>
      </aside>
      <IOSInstallModal isOpen={showIOSModal} onClose={() => setShowIOSModal(false)} />
    </>
  );
};

export default Sidebar;
