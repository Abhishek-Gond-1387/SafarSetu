/**
 * SignUpPage — Full-page sign-up with SafarSetu branding.
 * Uses Supabase Auth via SupabaseAuthClient (anon key only; no service-role key exposed).
 */
import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Bus, Eye, EyeOff, AlertCircle, CheckCircle, UserPlus, Zap } from 'lucide-react';
import { supabaseAuth } from '../lib/supabase';
import heroBgImage from '../assets/hero-delhi-transit.jpg';
import '../styles/auth.css';

function getPasswordStrength(pw: string): { score: number; label: string } {
  let score = 0;
  if (pw.length >= 8)  score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  const labels = ['', 'Weak', 'Fair', 'Good', 'Strong', 'Very Strong'];
  return { score, label: pw.length ? (labels[Math.min(score, 5)] || 'Weak') : '' };
}

function barClass(barIdx: number, score: number): string {
  if (score === 0) return '';
  if (score <= 1) return barIdx <= 1 ? 'weak' : '';
  if (score <= 2) return barIdx <= 2 ? 'fair' : '';
  if (score <= 3) return barIdx <= 3 ? 'good' : '';
  return 'strong';
}

export const SignUpPage: React.FC = () => {
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const pwStrength = getPasswordStrength(password);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!email.trim()) { setError('Please enter your email address.'); return; }
    if (!password) { setError('Please enter a password.'); return; }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    if (password !== confirmPw) { setError('Passwords do not match.'); return; }
    if (!agreed) { setError('Please agree to the terms to continue.'); return; }

    setLoading(true);
    try {
      const { user, error: authError } = await supabaseAuth.signUp(
        email.trim(),
        password,
        displayName.trim() || undefined,
      );
      if (authError) {
        const msg = authError.message || authError.error_description || 'Registration failed.';
        setError(msg);
      } else if (user) {
        // If Supabase returned a session directly (email confirmations off), redirect
        const sess = supabaseAuth.getSession();
        if (sess) {
          navigate('/planner');
        } else {
          setSuccess(
            'Account created! Check your inbox for a confirmation email, then sign in.'
          );
        }
      }
    } catch (err: any) {
      setError(err.message || 'Unexpected error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = () => {
    supabaseAuth.signInDemo();
    navigate('/planner');
  };

  return (
    <div className="auth-page">
      {/* Background Illustration Canvas with Delhi Transit Artwork */}
      <div
        className="auth-bg-media"
        style={{ backgroundImage: `url(${heroBgImage})` }}
        role="img"
        aria-label="Delhi Transit Network illustration with Metro, DTC electric bus and India Gate at sunrise"
      />

      {/* 3-Layer Atmospheric Color Grading Scrims */}
      <div className="auth-scrim-primary" />
      <div className="auth-scrim-vertical" />
      <div className="auth-scrim-warmth" />

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
            Join thousands of<br />
            <em>Delhi commuters</em><br />
            navigating smarter.
          </div>
          <p className="auth-brand-sub">
            Save favourite routes, track your journey history,
            and get timetable-accurate plans across 2,964 bus routes.
          </p>
          <div className="auth-brand-stats">
            <div className="auth-stat">
              <div className="auth-stat-num">Free</div>
              <div className="auth-stat-label">Always</div>
            </div>
            <div className="auth-stat">
              <div className="auth-stat-num">Secure</div>
              <div className="auth-stat-label">Supabase Auth</div>
            </div>
            <div className="auth-stat">
              <div className="auth-stat-num">RLS</div>
              <div className="auth-stat-label">Row-Level Security</div>
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
          Your data is protected by Supabase Row Level Security. We never share or sell your information.
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
            <h2>Create your account</h2>
            <p>Start planning smarter journeys across Delhi &amp; NCR.</p>
          </div>

          {error && (
            <div className="auth-error-msg" role="alert">
              <AlertCircle size={16} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="auth-success-msg" role="status">
              <CheckCircle size={16} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{success}</span>
            </div>
          )}

          {!success && (
            <form onSubmit={handleSubmit} noValidate>
              <div className="auth-field">
                <label htmlFor="signup-name">Display name <span style={{ color: '#94a3b8', fontWeight: 400 }}>(optional)</span></label>
                <input
                  id="signup-name"
                  type="text"
                  className="auth-input"
                  placeholder="e.g. Aditya Kumar"
                  value={displayName}
                  onChange={e => setDisplayName(e.target.value)}
                  autoComplete="name"
                  disabled={loading}
                  autoFocus
                />
              </div>

              <div className="auth-field">
                <label htmlFor="signup-email">Email address</label>
                <input
                  id="signup-email"
                  type="email"
                  className="auth-input"
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => { setEmail(e.target.value); setError(null); }}
                  autoComplete="email"
                  disabled={loading}
                />
              </div>

              <div className="auth-field">
                <label htmlFor="signup-password">Password</label>
                <div className="auth-password-wrapper">
                  <input
                    id="signup-password"
                    type={showPw ? 'text' : 'password'}
                    className="auth-input"
                    placeholder="At least 8 characters"
                    value={password}
                    onChange={e => { setPassword(e.target.value); setError(null); }}
                    autoComplete="new-password"
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
                {password.length > 0 && (
                  <>
                    <div className="pw-strength" aria-label={`Password strength: ${pwStrength.label}`}>
                      {[1,2,3,4,5].map(i => (
                        <div key={i} className={`pw-strength-bar ${barClass(i, pwStrength.score)}`} />
                      ))}
                    </div>
                    <div className="pw-strength-label">{pwStrength.label}</div>
                  </>
                )}
              </div>

              <div className="auth-field">
                <label htmlFor="signup-confirm">Confirm password</label>
                <input
                  id="signup-confirm"
                  type={showPw ? 'text' : 'password'}
                  className={`auth-input${confirmPw && confirmPw !== password ? ' error' : ''}`}
                  placeholder="Re-enter your password"
                  value={confirmPw}
                  onChange={e => { setConfirmPw(e.target.value); setError(null); }}
                  autoComplete="new-password"
                  disabled={loading}
                />
              </div>

              <div className="auth-terms">
                <input
                  id="signup-terms"
                  type="checkbox"
                  checked={agreed}
                  onChange={e => setAgreed(e.target.checked)}
                  disabled={loading}
                />
                <label htmlFor="signup-terms">
                  I agree that my account data is stored securely in Supabase and subject to row-level security. This service provides Delhi bus schedule information for planning purposes only.
                </label>
              </div>

              <button type="submit" className="auth-btn-primary" disabled={loading}>
                {loading
                  ? <><span className="auth-spinner" /> Creating account…</>
                  : <><UserPlus size={17} /> Create Account</>
                }
              </button>
            </form>
          )}

          {!success && (
            <>
              <div className="auth-divider">or</div>
              <button type="button" className="auth-btn-secondary" onClick={handleDemo} disabled={loading}>
                <Zap size={16} color="#f59e0b" />
                Try Demo Commuter (no account needed)
              </button>
            </>
          )}

          <div className="auth-switch">
            Already have an account?{' '}
            <Link to="/signin">Sign in</Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignUpPage;

