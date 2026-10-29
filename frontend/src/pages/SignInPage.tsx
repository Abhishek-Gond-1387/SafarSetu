/**
 * SignInPage — Full-page sign-in with SafarSetu branding.
 * Uses Supabase Auth via SupabaseAuthClient (no service-role key).
 */
import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Bus, Eye, EyeOff, AlertCircle, LogIn, Zap } from 'lucide-react';
import { supabaseAuth } from '../lib/supabase';
import '../styles/auth.css';

export const SignInPage: React.FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim()) { setError('Please enter your email address.'); return; }
    if (!password) { setError('Please enter your password.'); return; }

    setLoading(true);
    try {
      const { session, error: authError } = await supabaseAuth.signIn(email.trim(), password);
      if (authError) {
        const msg = authError.message || authError.error_description || 'Sign-in failed. Check your credentials.';
        setError(msg);
      } else if (session) {
        navigate('/');
      }
    } catch (err: any) {
      setError(err.message || 'Unexpected error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = () => {
    supabaseAuth.signInDemo();
    navigate('/');
  };

  return (
    <div className="auth-page">
      {/* ── Left: branding panel ── */}
      <div className="auth-brand">
        <div className="auth-brand-top">
          <div className="auth-brand-logo">
            <div className="auth-brand-logo-icon">
              <Bus size={24} color="#5eead4" />
            </div>
            <div>
              <h1>SafarSetu</h1>
              <span>Delhi / NCR Multimodal Transit</span>
            </div>
          </div>
        </div>

        <div className="auth-brand-hero">
          <div className="auth-brand-tagline">
            Your city.<br />
            <em>Every route.</em><br />
            One tap.
          </div>
          <p className="auth-brand-sub">
            Real-time bus positions, timetable-accurate journey planning,
            and transfer guidance across Delhi's 6,342 stops.
          </p>
          <div className="auth-brand-stats">
            <div className="auth-stat">
              <div className="auth-stat-num">6,342</div>
              <div className="auth-stat-label">Bus Stops</div>
            </div>
            <div className="auth-stat">
              <div className="auth-stat-num">2,964</div>
              <div className="auth-stat-label">Routes</div>
            </div>
            <div className="auth-stat">
              <div className="auth-stat-num">78K+</div>
              <div className="auth-stat-label">Trips Loaded</div>
            </div>
          </div>

          <div className="auth-route-dots" style={{ marginTop: '2rem' }}>
            <div className="auth-route-dot" />
            <div className="auth-route-line" />
            <div className="auth-route-dot" />
            <div className="auth-route-line" />
            <div className="auth-route-dot" />
          </div>
        </div>

        <div className="auth-brand-bottom">
          Schedule data: Delhi Transport Corporation GTFS
        </div>
      </div>

      {/* ── Right: form panel ── */}
      <div className="auth-form-panel">
        <div className="auth-form-box">

          {/* Mobile logo */}
          <div className="auth-mobile-logo">
            <div className="auth-mobile-logo-icon">
              <Bus size={20} color="#0f766e" />
            </div>
            <div>
              <h2>SafarSetu</h2>
              <span>Delhi / NCR Transit</span>
            </div>
          </div>

          <div className="auth-form-heading">
            <h2>Welcome back</h2>
            <p>Sign in to access your saved journeys and preferences.</p>
          </div>

          {error && (
            <div className="auth-error-msg" role="alert">
              <AlertCircle size={16} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <div className="auth-field">
              <label htmlFor="signin-email">Email address</label>
              <input
                id="signin-email"
                type="email"
                className={`auth-input${error ? ' error' : ''}`}
                placeholder="you@example.com"
                value={email}
                onChange={e => { setEmail(e.target.value); setError(null); }}
                autoComplete="email"
                autoFocus
                disabled={loading}
              />
            </div>

            <div className="auth-field">
              <label htmlFor="signin-password">Password</label>
              <div className="auth-password-wrapper">
                <input
                  id="signin-password"
                  type={showPw ? 'text' : 'password'}
                  className={`auth-input${error ? ' error' : ''}`}
                  placeholder="Enter your password"
                  value={password}
                  onChange={e => { setPassword(e.target.value); setError(null); }}
                  autoComplete="current-password"
                  disabled={loading}
                  style={{ paddingRight: '2.5rem' }}
                />
                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() => setShowPw(v => !v)}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                >
                  {showPw ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </div>

            <button type="submit" className="auth-btn-primary" disabled={loading}>
              {loading
                ? <><span className="auth-spinner" /> Signing in…</>
                : <><LogIn size={17} /> Sign In</>
              }
            </button>
          </form>

          <div className="auth-divider">or</div>

          <button type="button" className="auth-btn-secondary" onClick={handleDemo} disabled={loading}>
            <Zap size={16} color="#f59e0b" />
            Continue as Demo Commuter
          </button>

          <div className="auth-switch">
            Don't have an account?{' '}
            <Link to="/signup">Create one free</Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignInPage;

