import React, { useEffect } from 'react';
import { LogOut, X } from 'lucide-react';

interface LogoutConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isLoggingOut?: boolean;
}

export const LogoutConfirmModal: React.FC<LogoutConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  isLoggingOut = false,
}) => {
  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isLoggingOut) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isLoggingOut, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="modal-overlay logout-modal-overlay"
      onClick={() => {
        if (!isLoggingOut) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="logout-confirm-title"
    >
      <div
        className="modal-card logout-modal-card"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: '440px',
          borderRadius: '18px',
          overflow: 'hidden',
          boxShadow: '0 20px 48px rgba(0, 0, 0, 0.28), 0 0 0 1px rgba(0, 0, 0, 0.05)',
        }}
      >
        <div
          className="modal-header"
          style={{
            borderBottom: '1px solid #f1f5f9',
            padding: '1.2rem 1.4rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: '10px',
                background: '#fee2e2',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#dc2626',
              }}
            >
              <LogOut size={18} />
            </div>
            <h2
              id="logout-confirm-title"
              style={{ fontSize: '1.15rem', fontWeight: 800, margin: 0, color: '#0f172a' }}
            >
              Sign Out Confirmation
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isLoggingOut}
            aria-label="Close"
            style={{
              background: 'none',
              border: 'none',
              cursor: isLoggingOut ? 'not-allowed' : 'pointer',
              color: '#64748b',
              padding: '0.25rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={20} />
          </button>
        </div>

        <div className="modal-body" style={{ padding: '1.4rem 1.5rem' }}>
          <p
            style={{
              margin: 0,
              fontSize: '1.08rem',
              fontWeight: 750,
              color: '#0f172a',
              lineHeight: 1.4,
            }}
          >
            Are you sure you want to log out?
          </p>
          <p
            style={{
              margin: '0.65rem 0 0 0',
              fontSize: '0.88rem',
              color: '#64748b',
              lineHeight: 1.55,
            }}
          >
            You will be signed out of your SafarSetu session. You'll need to sign back in to access your saved journeys, real-time alerts, and personalized commuter preferences.
          </p>
        </div>

        <div
          className="modal-footer"
          style={{
            background: '#f8fafc',
            padding: '1.1rem 1.5rem',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '0.75rem',
            borderTop: '1px solid #f1f5f9',
          }}
        >
          <button
            type="button"
            className="btn-secondary"
            onClick={onClose}
            disabled={isLoggingOut}
            style={{
              padding: '0.6rem 1.15rem',
              borderRadius: '9px',
              border: '1.5px solid #cbd5e1',
              background: '#ffffff',
              fontWeight: 650,
              fontSize: '0.88rem',
              color: '#334155',
              cursor: isLoggingOut ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn-danger-logout"
            onClick={onConfirm}
            disabled={isLoggingOut}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.45rem',
              padding: '0.6rem 1.35rem',
              borderRadius: '9px',
              border: 'none',
              background: '#dc2626',
              color: '#ffffff',
              fontWeight: 750,
              fontSize: '0.88rem',
              cursor: isLoggingOut ? 'not-allowed' : 'pointer',
              boxShadow: '0 2px 10px rgba(220, 38, 38, 0.35)',
              transition: 'all 0.15s ease',
            }}
          >
            <LogOut size={16} />
            <span>{isLoggingOut ? 'Signing out...' : 'Yes, Log Out'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default LogoutConfirmModal;

