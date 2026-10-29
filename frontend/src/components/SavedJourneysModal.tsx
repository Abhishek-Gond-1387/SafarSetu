import React, { useState, useEffect } from 'react';
import { X, Bookmark, Trash2, ArrowRight, Loader2, Navigation } from 'lucide-react';
import { SafarSetuAPI, SavedJourney } from '../lib/api';

interface SavedJourneysModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectJourney: (originId: string, destId: string) => void;
}

export const SavedJourneysModal: React.FC<SavedJourneysModalProps> = ({
  isOpen,
  onClose,
  onSelectJourney,
}) => {
  const [journeys, setJourneys] = useState<SavedJourney[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadSavedJourneys();
    }
  }, [isOpen]);

  const loadSavedJourneys = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await SafarSetuAPI.getSavedJourneys(50);
      setJourneys(res.results || []);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to fetch saved journeys.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await SafarSetuAPI.deleteSavedJourney(id);
      setJourneys((prev) => prev.filter((j) => j.id !== id));
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to delete saved journey.');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Bookmark size={18} color="var(--primary)" />
            <h2>My Saved Journeys</h2>
          </div>
          <button onClick={onClose} aria-label="Close modal">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {errorMsg && (
            <div className="alert-box alert-danger">
              {errorMsg}
            </div>
          )}

          {isLoading ? (
            <div style={{ textAlign: 'center', padding: '2rem 0' }}>
              <Loader2 size={24} className="animate-spin" color="var(--primary)" />
              <p style={{ marginTop: '0.5rem', color: 'var(--text-muted)' }}>Loading saved journeys...</p>
            </div>
          ) : journeys.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2.5rem 1rem', color: 'var(--text-muted)' }}>
              <Bookmark size={36} color="var(--text-light)" style={{ margin: '0 auto 0.75rem' }} />
              <h3 style={{ fontSize: '1rem', color: 'var(--text-main)', marginBottom: '0.25rem' }}>
                No saved journeys yet
              </h3>
              <p style={{ fontSize: '0.85rem' }}>
                Search for a route and click the "Save" bookmark button on any result card to access it quickly here.
              </p>
            </div>
          ) : (
            <div>
              {journeys.map((j) => (
                <div key={j.id} className="saved-item">
                  <div style={{ flex: 1 }}>
                    <div className="saved-item-title">{j.journey_name}</div>
                    <div className="saved-item-sub">
                      <span>{j.origin_stop_id}</span>
                      <ArrowRight size={12} style={{ display: 'inline', margin: '0 4px' }} />
                      <span>{j.destination_stop_id}</span>
                      {j.ranking_criterion_preference && (
                        <span style={{ marginLeft: '6px', color: 'var(--primary)', fontWeight: 600 }}>
                          ({j.ranking_criterion_preference})
                        </span>
                      )}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <button
                      className="btn-primary"
                      style={{ padding: '0.35rem 0.65rem', fontSize: '0.8rem' }}
                      onClick={() => {
                        onSelectJourney(j.origin_stop_id, j.destination_stop_id);
                        onClose();
                      }}
                      title="Load and plan this route"
                    >
                      <Navigation size={13} />
                      <span>Plan</span>
                    </button>

                    <button
                      className="btn-icon"
                      style={{ padding: '0.35rem 0.5rem', color: 'var(--danger)' }}
                      onClick={(e) => handleDelete(j.id, e)}
                      title="Delete saved journey"
                      aria-label="Delete"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

