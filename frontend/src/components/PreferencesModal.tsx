import React, { useState, useEffect } from 'react';
import { X, Settings, Check, Loader2 } from 'lucide-react';
import { SafarSetuAPI, UserPreferences } from '../lib/api';

interface PreferencesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const PreferencesModal: React.FC<PreferencesModalProps> = ({ isOpen, onClose }) => {
  const [preferences, setPreferences] = useState<UserPreferences>({
    default_ranking_criterion: 'fastest',
    preferred_language: 'en',
    max_walking_distance_meters: 800,
    wheelchair_accessible: false,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadPreferences();
    }
  }, [isOpen]);

  const loadPreferences = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await SafarSetuAPI.getPreferences();
      setPreferences(res);
    } catch (err: any) {
      // Non-fatal if newly created profile
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMsg(null);
    try {
      await SafarSetuAPI.updatePreferences(preferences);
      setSavedSuccess(true);
      setTimeout(() => {
        setSavedSuccess(false);
        onClose();
      }, 1000);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to save preferences.');
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Settings size={18} color="var(--primary)" />
            <h2>Commuter Preferences</h2>
          </div>
          <button onClick={onClose} aria-label="Close modal">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSave}>
          <div className="modal-body">
            {errorMsg && <div className="alert-box alert-danger">{errorMsg}</div>}
            {savedSuccess && (
              <div className="alert-box alert-success">
                <Check size={16} style={{ display: 'inline', marginRight: 6 }} />
                Preferences updated successfully!
              </div>
            )}

            {isLoading ? (
              <div style={{ textAlign: 'center', padding: '1.5rem 0' }}>
                <Loader2 size={24} className="animate-spin" color="var(--primary)" />
              </div>
            ) : (
              <>
                <div className="form-group">
                  <label className="form-label" htmlFor="pref-lang">
                    Preferred UI Language
                  </label>
                  <select
                    id="pref-lang"
                    className="form-input"
                    style={{ paddingLeft: '0.75rem' }}
                    value={preferences.preferred_language}
                    onChange={(e) =>
                      setPreferences({ ...preferences, preferred_language: e.target.value })
                    }
                  >
                    <option value="en">English</option>
                    <option value="hi">हिंदी (Hindi)</option>
                    <option value="pa">ਪੰਜਾਬੀ (Punjabi)</option>
                    <option value="ur">اردو (Urdu)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="pref-ranking">
                    Default Journey Ranking
                  </label>
                  <select
                    id="pref-ranking"
                    className="form-input"
                    style={{ paddingLeft: '0.75rem' }}
                    value={preferences.default_ranking_criterion}
                    onChange={(e) =>
                      setPreferences({
                        ...preferences,
                        default_ranking_criterion: e.target.value,
                      })
                    }
                  >
                    <option value="fastest">Fastest Total Duration</option>
                    <option value="cheapest">Lowest Known Fare</option>
                    <option value="balanced">Balanced (Transfers & Walking)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="pref-walk">
                    Maximum Walk Distance ({preferences.max_walking_distance_meters || 800} meters)
                  </label>
                  <input
                    id="pref-walk"
                    type="range"
                    min={200}
                    max={2500}
                    step={100}
                    value={preferences.max_walking_distance_meters || 800}
                    onChange={(e) =>
                      setPreferences({
                        ...preferences,
                        max_walking_distance_meters: parseInt(e.target.value, 10),
                      })
                    }
                    style={{ width: '100%' }}
                  />
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '0.75rem',
                      color: 'var(--text-muted)',
                    }}
                  >
                    <span>200m</span>
                    <span>800m (Standard)</span>
                    <span>2500m</span>
                  </div>
                </div>

                <div className="form-group" style={{ marginTop: '1rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={preferences.wheelchair_accessible}
                      onChange={(e) =>
                        setPreferences({
                          ...preferences,
                          wheelchair_accessible: e.target.checked,
                        })
                      }
                    />
                    <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>
                      Prefer wheelchair accessible stops / low-floor DTC buses
                    </span>
                  </label>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginTop: '2px' }}>
                    Filters stops based on GTFS wheelchair accessibility flags where available.
                  </span>
                </div>
              </>
            )}
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={isSaving || isLoading}>
              {isSaving ? 'Saving...' : 'Save Preferences'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

