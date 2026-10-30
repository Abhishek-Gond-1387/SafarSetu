/**
 * AccountPage — Profile management and account deletion.
 * DELETE /api/v1/users/me is handled server-side using the Supabase service-role key.
 * The service-role key is NEVER sent to or exposed in the browser.
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  User, Settings, Trash2, LogOut, ArrowLeft,
  CheckCircle, AlertCircle, ShieldAlert,
} from 'lucide-react';
import { supabaseAuth, UserSession } from '../lib/supabase';
import { SafarSetuAPI } from '../lib/api';
import { LogoutConfirmModal } from '../components/LogoutConfirmModal';
import '../styles/auth.css';
import '../styles/app.css';

interface AccountPageProps {
  session: UserSession | null;
}

export const AccountPage: React.FC<AccountPageProps> = ({ session }) => {
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState(session?.user?.display_name || '');
  const [gender, setGender] = useState(session?.user?.gender || '');
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);

  useEffect(() => {
    if (!session) {
      navigate('/signin');
    } else {
      SafarSetuAPI.getCurrentUser()
        .then((res: any) => {
          if (res?.profile?.gender) setGender(res.profile.gender);
          if (res?.profile?.display_name && !displayName) setDisplayName(res.profile.display_name);
        })
        .catch(() => {});
    }
  }, [session, navigate]);

  if (!session) return null;

  const email = session.user?.email || '—';
  const userId = session.user?.id || '—';
  const initials = (displayName || email).slice(0, 2).toUpperCase();

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveMsg(null);
    setSaving(true);
    try {
      await SafarSetuAPI.updateProfile({
        display_name: displayName.trim() || undefined,
        gender: gender || undefined,
      });
      setSaveMsg({ type: 'success', text: 'Profile updated successfully.' });
    } catch (err: any) {
      setSaveMsg({ type: 'error', text: err.message || 'Failed to update profile.' });
    } finally {
      setSaving(false);
    }
  };

  const handleSignOutClick = () => {
    setShowLogoutConfirm(true);
  };

  const handleConfirmSignOut = async () => {
    setIsSigningOut(true);
    try {
      await supabaseAuth.signOut();
      setShowLogoutConfirm(false);
      navigate('/signin');
    } finally {
      setIsSigningOut(false);
    }
  };

  const handleDeleteAccount = async () => {
    setDeleting(true);
    setDeleteError(null);
    try {
      await SafarSetuAPI.deleteAccount();
      await supabaseAuth.signOut();
      navigate('/signin');
    } catch (err: any) {
      setDeleteError(err.message || 'Account deletion failed. Please try again.');
      setDeleting(false);
    }
  };

  return (
    <div className="account-page">
      {/* Hero */}
      <div className="account-hero">
        <button className="account-back-nav" onClick={() => navigate('/')} aria-label="Back to planner">
          <ArrowLeft size={16} />
          Back to Transit Planner
        </button>

        <div className="account-avatar" aria-hidden="true">{initials}</div>
        <h2>{displayName || 'Commuter'}</h2>
        <p>{email}</p>
      </div>

      <div className="account-cards">

        {/* Profile card */}
        <div className="account-card">
          <h3><User size={16} /> Profile</h3>
          {saveMsg && (
            <div className={saveMsg.type === 'success' ? 'auth-success-msg' : 'auth-error-msg'} style={{ marginBottom: '0.9rem' }}>
              {saveMsg.type === 'success'
                ? <CheckCircle size={15} style={{ flexShrink: 0 }} />
                : <AlertCircle size={15} style={{ flexShrink: 0 }} />
              }
              <span>{saveMsg.text}</span>
            </div>
          )}
          <form onSubmit={handleSaveProfile}>
            <div className="auth-field">
              <label htmlFor="acc-name">Display name</label>
              <input
                id="acc-name"
                type="text"
                className="auth-input"
                value={displayName}
                onChange={e => { setDisplayName(e.target.value); setSaveMsg(null); }}
                placeholder="Your name"
                disabled={saving}
              />
            </div>
            <div className="auth-field" style={{ marginBottom: '1.25rem' }}>
              <label>
                Gender <span style={{ color: '#94a3b8', fontWeight: 400 }}>(used for HerRoute women safety insights)</span>
              </label>
              <div className="gender-selector-grid" style={{ marginTop: '0.35rem' }}>
                <button
                  type="button"
                  className={`gender-option-btn ${gender === 'female' ? 'active' : ''}`}
                  onClick={() => { setGender(gender === 'female' ? '' : 'female'); setSaveMsg(null); }}
                  disabled={saving}
                >
                  <span className="gender-icon">👩</span>
                  <span>Female</span>
                </button>
                <button
                  type="button"
                  className={`gender-option-btn ${gender === 'male' ? 'active' : ''}`}
                  onClick={() => { setGender(gender === 'male' ? '' : 'male'); setSaveMsg(null); }}
                  disabled={saving}
                >
                  <span className="gender-icon">👨</span>
                  <span>Male</span>
                </button>
                <button
                  type="button"
                  className={`gender-option-btn ${gender === 'other' ? 'active' : ''}`}
                  onClick={() => { setGender(gender === 'other' ? '' : 'other'); setSaveMsg(null); }}
                  disabled={saving}
                >
                  <span className="gender-icon">⚧️</span>
                  <span>Other</span>
                </button>
                <button
                  type="button"
                  className={`gender-option-btn ${gender === 'prefer_not_to_say' ? 'active' : ''}`}
                  onClick={() => { setGender(gender === 'prefer_not_to_say' ? '' : 'prefer_not_to_say'); setSaveMsg(null); }}
                  disabled={saving}
                >
                  <span className="gender-icon">🔒</span>
                  <span>Prefer not to say</span>
                </button>
              </div>
            </div>
            <div className="account-info-row">
              <span className="account-info-label">Email</span>
              <span className="account-info-value">{email}</span>
            </div>
            <div className="account-info-row" style={{ marginBottom: '1rem' }}>
              <span className="account-info-label">User ID</span>
              <span className="account-info-value" style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: '#94a3b8' }}>
                {userId.slice(0, 16)}…
              </span>
            </div>
            <button type="submit" className="auth-btn-primary" disabled={saving}>
              {saving
                ? <><span className="auth-spinner" /> Saving…</>
                : <><Settings size={15} /> Save Changes</>
              }
            </button>
          </form>
        </div>

        {/* Account actions card */}
        <div className="account-card">
          <h3><Settings size={16} /> Account Actions</h3>
          <button
            type="button"
            className="auth-btn-secondary"
            style={{ marginBottom: '0.75rem' }}
            onClick={handleSignOutClick}
          >
            <LogOut size={16} />
            Sign Out
          </button>
        </div>

        {/* Danger zone */}
        <div className="account-danger-card">
          <h3><ShieldAlert size={16} /> Danger Zone</h3>
          <p>
            Deleting your account is permanent and cannot be undone. All saved journeys,
            preferences, and recent search history will be removed from our database.
            Your transit planning data will not be recoverable.
          </p>
          {deleteError && (
            <div className="auth-error-msg" style={{ marginBottom: '0.9rem' }}>
              <AlertCircle size={15} style={{ flexShrink: 0 }} />
              <span>{deleteError}</span>
            </div>
          )}
          <button
            type="button"
            className="auth-btn-danger"
            onClick={() => setShowConfirm(true)}
            disabled={deleting}
          >
            <Trash2 size={16} />
            Delete My Account
          </button>
        </div>
      </div>

      {/* Confirm logout dialog */}
      <LogoutConfirmModal
        isOpen={showLogoutConfirm}
        onClose={() => setShowLogoutConfirm(false)}
        onConfirm={handleConfirmSignOut}
        isLoggingOut={isSigningOut}
      />

      {/* Confirm delete dialog */}
      {showConfirm && (
        <div className="confirm-overlay" role="dialog" aria-modal="true" aria-labelledby="del-title">
          <div className="confirm-box">
            <h3 id="del-title">Delete account permanently?</h3>
            <p>
              This will remove your profile, all saved journeys, preferences, and search
              history from SafarSetu. This action <strong>cannot be reversed</strong>.
            </p>
            <div className="confirm-actions">
              <button
                className="confirm-cancel"
                onClick={() => { setShowConfirm(false); setDeleteError(null); }}
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                className="confirm-delete"
                onClick={handleDeleteAccount}
                disabled={deleting}
              >
                {deleting ? <><span className="auth-spinner" /> Deleting…</> : 'Yes, Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AccountPage;

