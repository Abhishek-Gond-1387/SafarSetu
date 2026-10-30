import React from 'react';
import { X, Share, PlusSquare, Smartphone, Check } from 'lucide-react';

interface IOSInstallModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const IOSInstallModal: React.FC<IOSInstallModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="lost-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="lost-modal-card"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '440px' }}
      >
        <div className="lost-modal-header" style={{ borderBottomColor: '#0284c7' }}>
          <div className="lost-header-left">
            <div
              className="lost-header-icon-box"
              style={{ background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)' }}
            >
              <Smartphone size={22} />
            </div>
            <div className="lost-header-text">
              <h3 style={{ margin: 0, fontSize: '1.15rem', color: '#ffffff' }}>Install SafarSetu App</h3>
              <p className="lost-subtitle">Add to your iPhone or iPad Home Screen</p>
            </div>
          </div>
          <button type="button" className="lost-modal-close" onClick={onClose} aria-label="Close">
            <X size={20} />
          </button>
        </div>

        <div className="lost-modal-body" style={{ padding: '1.25rem 1.5rem' }}>
          <p style={{ margin: '0 0 1rem 0', fontSize: '0.88rem', color: '#334155', lineHeight: 1.5 }}>
            Install SafarSetu on iOS Safari for full-screen navigation, faster load times, and offline access without opening the browser:
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.85rem',
                background: '#ffffff',
                border: '1.5px solid #e2e8f0',
                borderRadius: '12px',
                padding: '0.75rem 1rem',
              }}
            >
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '10px',
                  background: '#f0f9ff',
                  color: '#0284c7',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <Share size={20} />
              </div>
              <div style={{ fontSize: '0.84rem', color: '#1e293b' }}>
                <strong>Step 1:</strong> Tap the <strong>Share</strong> button at the bottom of Safari.
              </div>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.85rem',
                background: '#ffffff',
                border: '1.5px solid #e2e8f0',
                borderRadius: '12px',
                padding: '0.75rem 1rem',
              }}
            >
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '10px',
                  background: '#f0fdf4',
                  color: '#16a34a',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <PlusSquare size={20} />
              </div>
              <div style={{ fontSize: '0.84rem', color: '#1e293b' }}>
                <strong>Step 2:</strong> Scroll down and select <strong>"Add to Home Screen"</strong>.
              </div>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.85rem',
                background: '#ffffff',
                border: '1.5px solid #e2e8f0',
                borderRadius: '12px',
                padding: '0.75rem 1rem',
              }}
            >
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '10px',
                  background: '#ecfdf5',
                  color: '#059669',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <Check size={20} />
              </div>
              <div style={{ fontSize: '0.84rem', color: '#1e293b' }}>
                <strong>Step 3:</strong> Tap <strong>Add</strong> in the top-right corner. Enjoy SafarSetu!
              </div>
            </div>
          </div>
        </div>

        <div className="lost-modal-footer">
          <button
            type="button"
            className="lost-btn-navigate"
            onClick={onClose}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            Got It
          </button>
        </div>
      </div>
    </div>
  );
};

