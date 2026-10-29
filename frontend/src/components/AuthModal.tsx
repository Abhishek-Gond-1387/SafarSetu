import React, { useState } from 'react';
import { X, LogIn, UserPlus, UserCheck, AlertCircle } from 'lucide-react';
import { supabaseAuth, UserSession } from '../lib/supabase';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (session: UserSession) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [tab, setTab] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsLoading(true);

    try {
      if (tab === 'signin') {
        const { session, error } = await supabaseAuth.signIn(email, password);
        if (error) {
          setErrorMsg(error.message || 'Failed to sign in. Verify your credentials.');
        } else if (session) {
          onSuccess(session);
          onClose();
        }
      } else {
        const { user, error } = await supabaseAuth.signUp(email, password, displayName);
        if (error) {
          setErrorMsg(error.message || 'Failed to create account.');
        } else {
          // If auto sign-in happened
          const current = supabaseAuth.getSession();
          if (current) {
            onSuccess(current);
            onClose();
          } else {
            setErrorMsg('Account created! Please check your email to confirm registration or sign in.');
            setTab('signin');
          }
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'An unexpected error occurred.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoCommuter = () => {
    const session = supabaseAuth.signInDemo('commuter@delhitransit.gov.in', 'Delhi Commuter');
    onSuccess(session);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{tab === 'signin' ? 'Sign In to SafarSetu' : 'Create Commuter Account'}</h2>
          <button onClick={onClose} aria-label="Close modal">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <div className="tabs-nav">
            <button
              type="button"
              className={`tab-btn ${tab === 'signin' ? 'active' : ''}`}
              onClick={() => {
                setTab('signin');
                setErrorMsg(null);
              }}
            >
              Sign In
            </button>
            <button
              type="button"
              className={`tab-btn ${tab === 'signup' ? 'active' : ''}`}
              onClick={() => {
                setTab('signup');
                setErrorMsg(null);
              }}
            >
              Sign Up
            </button>
          </div>

          {errorMsg && (
            <div className="alert-box alert-danger">
              <AlertCircle size={16} style={{ display: 'inline', marginRight: 6 }} />
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {tab === 'signup' && (
              <div className="form-group">
                <label className="form-label" htmlFor="display-name">
                  Full Name / Display Name
                </label>
                <input
                  id="display-name"
                  type="text"
                  className="form-input"
                  style={{ paddingLeft: '0.75rem' }}
                  placeholder="e.g. Rahul Sharma"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label" htmlFor="auth-email">
                Email Address
              </label>
              <input
                id="auth-email"
                type="email"
                className="form-input"
                style={{ paddingLeft: '0.75rem' }}
                placeholder="commuter@example.com"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="auth-password">
                Password
              </label>
              <input
                id="auth-password"
                type="password"
                className="form-input"
                style={{ paddingLeft: '0.75rem' }}
                placeholder="••••••••"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <button
              type="submit"
              className="btn-primary"
              style={{ width: '100%', marginTop: '0.5rem' }}
              disabled={isLoading}
            >
              {tab === 'signin' ? <LogIn size={16} /> : <UserPlus size={16} />}
              <span>{isLoading ? 'Verifying...' : tab === 'signin' ? 'Sign In' : 'Sign Up'}</span>
            </button>
          </form>

          {/* Quick Demo Commuter Access */}
          <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--border)', textAlign: 'center' }}>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.65rem' }}>
              Testing without live Supabase cloud credentials?
            </p>
            <button
              type="button"
              className="btn-secondary"
              onClick={handleDemoCommuter}
              style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
            >
              <UserCheck size={16} color="var(--primary)" />
              <span>Sign In as Demo Commuter</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

