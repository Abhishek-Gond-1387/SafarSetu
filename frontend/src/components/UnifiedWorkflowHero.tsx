import React, { useState } from 'react';
import {
  Compass,
  MapPin,
  Bus,
  TrainTrack,
  ArrowRight,
  LogIn,
  UserPlus,
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle2,
  Zap,
  Lock,
  Mail,
  User,
} from 'lucide-react';
import { UserSession, supabaseAuth } from '../lib/supabase';
import heroBg from '../assets/hero-delhi-transit.jpg';

interface UnifiedWorkflowHeroProps {
  session: UserSession | null;
  onProceedToJourney: () => void;
}

export const UnifiedWorkflowHero: React.FC<UnifiedWorkflowHeroProps> = ({
  session,
  onProceedToJourney,
}) => {
  const [authTab, setAuthTab] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.trim()) {
      setError('Please enter your email.');
      return;
    }
    if (!password) {
      setError('Please enter your password.');
      return;
    }

    setLoading(true);
    try {
      const { session: newSession, error: authError } = await supabaseAuth.signIn(
        email.trim(),
        password
      );
      if (authError) {
        setError(authError.message || 'Invalid credentials.');
      } else if (newSession) {
        onProceedToJourney();
      }
    } catch (err: any) {
      setError(err.message || 'Sign in failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (!email.trim()) {
      setError('Please enter your email.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }

    setLoading(true);
    try {
      const { user, error: authError } = await supabaseAuth.signUp(
        email.trim(),
        password,
        displayName.trim() || undefined
      );
      if (authError) {
        setError(authError.message || 'Sign up failed.');
      } else {
        const sess = supabaseAuth.getSession();
        if (sess) {
          onProceedToJourney();
        } else {
          setSuccess('Account created! You can now sign in.');
          setAuthTab('signin');
        }
      }
    } catch (err: any) {
      setError(err.message || 'Sign up failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoSignIn = () => {
    supabaseAuth.signInDemo();
    onProceedToJourney();
  };

  return (
    <section className="workflow-master-hero">
      {/* ── Background Media Canvas & Color Grading Overlays ── */}
      <div
        className="hero-bg-media"
        style={{ backgroundImage: `url(${heroBg || '/hero-delhi-transit.jpg'})` }}
      >
        {/* Layer 1: Left-to-Right Atmospheric Contrast Scrim */}
        <div className="hero-scrim-primary" />
        {/* Layer 2: Vertical Smooth Transition into Journey Selection Canvas */}
        <div className="hero-scrim-vertical" />
        {/* Layer 3: Warm Sunrise Screen Gradient */}
        <div className="hero-scrim-warmth" />
      </div>

      <div className="container workflow-hero-grid">
        {/* ── LEFT COLUMN: Step 1 First View Headline, Metrics & Narrative ── */}
        <div className="workflow-left-column">
          <div className="workflow-badge-pill">
            <span className="badge-pulse-dot" />
            <span className="badge-text">Step 1 • Welcome to SafarSetu</span>
            <span className="badge-hindi">सफ़रसेतु</span>
          </div>

          <h1 className="workflow-hero-title">
            <span className="title-row">Your city.</span>
            <span className="title-row">Every route.</span>
            <span className="title-row title-highlight">One tap.</span>
          </h1>

          <p className="workflow-hero-subtitle">
            Real-time bus positions, timetable-accurate journey planning, and transfer guidance across Delhi's 6,342 stops.
          </p>

          {/* Exact 3 Stats Requested */}
          <div className="workflow-stats-trio">
            <div className="workflow-stat-tile">
              <div className="stat-tile-icon cyan">
                <MapPin size={18} />
              </div>
              <div className="stat-tile-data">
                <span className="stat-num">6,342</span>
                <span className="stat-sub">Bus Stops</span>
              </div>
            </div>

            <div className="workflow-stat-tile">
              <div className="stat-tile-icon emerald">
                <Bus size={18} />
              </div>
              <div className="stat-tile-data">
                <span className="stat-num">2,964</span>
                <span className="stat-sub">Routes</span>
              </div>
            </div>

            <div className="workflow-stat-tile">
              <div className="stat-tile-icon amber">
                <TrainTrack size={18} />
              </div>
              <div className="stat-tile-data">
                <span className="stat-num">78K+</span>
                <span className="stat-sub">Trips Loaded</span>
              </div>
            </div>
          </div>

          {/* Workflow Sequence Guide */}
          <div className="workflow-sequence-guide">
            <div className="seq-step done">
              <span className="seq-num">1</span>
              <span>Explore Overview</span>
            </div>
            <div className="seq-arrow">→</div>
            <div className={`seq-step ${session ? 'done' : 'active'}`}>
              <span className="seq-num">2</span>
              <span>{session ? 'Authenticated' : 'Sign In / Sign Up'}</span>
            </div>
            <div className="seq-arrow">→</div>
            <div className="seq-step active">
              <span className="seq-num">3</span>
              <span>Journey Selection</span>
            </div>
          </div>
        </div>

        {/* ── RIGHT COLUMN: Step 2 Authentication Card (Seamless Transition to Step 3) ── */}
        <div className="workflow-right-column">
          <div className="workflow-auth-card">
            {session ? (
              /* Already Signed In: Direct One-Tap Journey Selection Launch */
              <div className="workflow-authenticated-box">
                <div className="auth-user-badge">
                  <CheckCircle2 size={24} color="#34d399" />
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#ffffff' }}>
                      Ready for Transit
                    </h3>
                    <p style={{ margin: '0.2rem 0 0', fontSize: '0.82rem', color: '#94a3b8' }}>
                      Signed in as <strong>{session.user.email || 'Delhi Commuter'}</strong>
                    </p>
                  </div>
                </div>

                <p style={{ fontSize: '0.86rem', color: '#cbd5e1', lineHeight: 1.5, margin: '1rem 0 1.25rem' }}>
                  Your commuter preferences and saved itineraries are synced. Choose your boarding station below to calculate multimodal routes.
                </p>

                <button
                  type="button"
                  className="btn-launch-journey"
                  onClick={onProceedToJourney}
                >
                  <Compass size={18} />
                  <span>Open Journey Selection</span>
                  <ArrowRight size={18} />
                </button>
              </div>
            ) : (
              /* Not Signed In: Inline Step 2 Sign In / Sign Up Tabs */
              <div>
                <div className="auth-card-header">
                  <div>
                    <h2 className="auth-card-title">Step 2 • Commuter Access</h2>
                    <p className="auth-card-sub">Sign in or continue to plan your trip across Delhi.</p>
                  </div>
                  <div className="auth-lock-icon">
                    <Lock size={16} />
                  </div>
                </div>

                {/* Tab Switcher */}
                <div className="auth-tab-switch">
                  <button
                    type="button"
                    className={`auth-tab-btn ${authTab === 'signin' ? 'active' : ''}`}
                    onClick={() => {
                      setAuthTab('signin');
                      setError(null);
                      setSuccess(null);
                    }}
                  >
                    <LogIn size={14} />
                    <span>Sign In</span>
                  </button>
                  <button
                    type="button"
                    className={`auth-tab-btn ${authTab === 'signup' ? 'active' : ''}`}
                    onClick={() => {
                      setAuthTab('signup');
                      setError(null);
                      setSuccess(null);
                    }}
                  >
                    <UserPlus size={14} />
                    <span>Create Account</span>
                  </button>
                </div>

                {error && (
                  <div className="auth-alert-error">
                    <AlertCircle size={15} style={{ flexShrink: 0 }} />
                    <span>{error}</span>
                  </div>
                )}

                {success && (
                  <div className="auth-alert-success">
                    <CheckCircle2 size={15} style={{ flexShrink: 0 }} />
                    <span>{success}</span>
                  </div>
                )}

                {/* Sign In Form */}
                {authTab === 'signin' ? (
                  <form onSubmit={handleSignIn} className="auth-form-body">
                    <div className="auth-input-group">
                      <label>Email Address</label>
                      <div className="input-wrap">
                        <Mail size={16} className="field-icon" />
                        <input
                          type="email"
                          placeholder="commuter@delhi.gov.in"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          required
                        />
                      </div>
                    </div>

                    <div className="auth-input-group">
                      <label>Password</label>
                      <div className="input-wrap">
                        <Lock size={16} className="field-icon" />
                        <input
                          type={showPassword ? 'text' : 'password'}
                          placeholder="••••••••"
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          required
                        />
                        <button
                          type="button"
                          className="toggle-pw-btn"
                          onClick={() => setShowPassword(!showPassword)}
                        >
                          {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                        </button>
                      </div>
                    </div>

                    <button type="submit" className="btn-auth-submit" disabled={loading}>
                      {loading ? 'Authenticating...' : 'Sign In & Open Journey Selection'}
                      <ArrowRight size={16} />
                    </button>
                  </form>
                ) : (
                  /* Sign Up Form */
                  <form onSubmit={handleSignUp} className="auth-form-body">
                    <div className="auth-input-group">
                      <label>Full Name</label>
                      <div className="input-wrap">
                        <User size={16} className="field-icon" />
                        <input
                          type="text"
                          placeholder="Aditya Sharma"
                          value={displayName}
                          onChange={(e) => setDisplayName(e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="auth-input-group">
                      <label>Email Address</label>
                      <div className="input-wrap">
                        <Mail size={16} className="field-icon" />
                        <input
                          type="email"
                          placeholder="you@example.com"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          required
                        />
                      </div>
                    </div>

                    <div className="auth-input-group">
                      <label>Password (min 6 characters)</label>
                      <div className="input-wrap">
                        <Lock size={16} className="field-icon" />
                        <input
                          type={showPassword ? 'text' : 'password'}
                          placeholder="••••••••"
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          required
                        />
                        <button
                          type="button"
                          className="toggle-pw-btn"
                          onClick={() => setShowPassword(!showPassword)}
                        >
                          {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                        </button>
                      </div>
                    </div>

                    <button type="submit" className="btn-auth-submit" disabled={loading}>
                      {loading ? 'Creating Account...' : 'Sign Up & Continue'}
                      <ArrowRight size={16} />
                    </button>
                  </form>
                )}

                {/* Instant Skip / Demo Action */}
                <div className="auth-quick-actions">
                  <div className="divider-line">
                    <span>or continue directly</span>
                  </div>

                  <button
                    type="button"
                    className="btn-demo-transit"
                    onClick={handleDemoSignIn}
                    title="Sign in with instant demo commuter account"
                  >
                    <Zap size={14} color="#f59e0b" />
                    <span>Instant Demo Commuter Login</span>
                  </button>

                  <button
                    type="button"
                    className="btn-skip-guest"
                    onClick={onProceedToJourney}
                  >
                    <span>Proceed as Guest to Step 3: Journey Selection</span>
                    <ArrowRight size={13} />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};

