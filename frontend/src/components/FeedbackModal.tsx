import React, { useState } from 'react';
import { X, MessageSquare, Check, AlertCircle, Info } from 'lucide-react';
import { SafarSetuAPI } from '../lib/api';

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const FeedbackModal: React.FC<FeedbackModalProps> = ({ isOpen, onClose }) => {
  const [category, setCategory] = useState('routing_issue');
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (description.trim().length < 5) {
      setErrorMsg('Please describe the issue in at least 5 characters.');
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const res = await SafarSetuAPI.submitFeedback({
        category,
        description: description.trim(),
      });
      setSuccessMsg(res.message || 'Feedback submitted for review. Thank you!');
      setTimeout(() => {
        setSuccessMsg(null);
        setDescription('');
        onClose();
      }, 1500);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to submit feedback.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <MessageSquare size={18} color="var(--primary)" />
            <h2>Commuter Feedback & Transit Reporting</h2>
          </div>
          <button onClick={onClose} aria-label="Close modal">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div
              style={{
                background: '#f8fafc',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                padding: '0.65rem 0.85rem',
                fontSize: '0.8rem',
                color: 'var(--text-muted)',
                marginBottom: '1rem',
                display: 'flex',
                gap: '0.5rem',
              }}
            >
              <Info size={16} color="var(--primary)" style={{ flexShrink: 0, marginTop: 2 }} />
              <span>
                <strong>Commuter Transparency Policy:</strong> Reports are reviewed by operators. Feedback does not automatically overwrite official DTC GTFS schedule files or live vehicle positions.
              </span>
            </div>

            {errorMsg && <div className="alert-box alert-danger">{errorMsg}</div>}
            {successMsg && (
              <div className="alert-box alert-success">
                <Check size={16} style={{ display: 'inline', marginRight: 6 }} />
                {successMsg}
              </div>
            )}

            <div className="form-group">
              <label className="form-label" htmlFor="feedback-cat">
                Report Category
              </label>
              <select
                id="feedback-cat"
                className="form-input"
                style={{ paddingLeft: '0.75rem' }}
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="routing_issue">Routing Issue / Infeasible Transfer</option>
                <option value="missing_stop">Missing or Inaccurate Stop Name</option>
                <option value="live_feed_discrepancy">Live Bus Position Discrepancy</option>
                <option value="general">General Suggestion</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="feedback-desc">
                Description ({description.length} / 2000 chars)
              </label>
              <textarea
                id="feedback-desc"
                className="form-input"
                style={{ minHeight: '110px', padding: '0.65rem', resize: 'vertical' }}
                placeholder="Describe your observation with stop names, bus route numbers, or approximate times..."
                maxLength={2000}
                required
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Submitting...' : 'Submit Report'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

