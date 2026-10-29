import React, { useState, useEffect } from 'react';
import { X, TrainTrack, Radio, CheckCircle, Clock, ArrowRight, RefreshCw, AlertCircle } from 'lucide-react';
import { SafarSetuAPI, MetroNetworkStatusResponse, MetroLineStatus } from '../lib/api';

interface MetroStatusModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const MetroStatusModal: React.FC<MetroStatusModalProps> = ({ isOpen, onClose }) => {
  const [data, setData] = useState<MetroNetworkStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFilter, setSelectedFilter] = useState<'all' | 'interchanges'>('all');

  useEffect(() => {
    if (isOpen) {
      fetchStatus();
    }
  }, [isOpen]);

  const fetchStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await SafarSetuAPI.getMetroRealtimeStatus();
      setData(res);
    } catch (e: any) {
      setError(e.message || 'Failed to load DMRC real-time line telemetry.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="metro-status-title">
      <div className="modal-content" style={{ maxWidth: '680px', maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div style={{ background: '#0f766e', color: '#fff', padding: '0.4rem', borderRadius: '8px', display: 'flex' }}>
              <TrainTrack size={20} />
            </div>
            <div>
              <h2 id="metro-status-title" style={{ fontSize: '1.2rem', fontWeight: 800 }}>
                Delhi Metro (DMRC) Live Operations
              </h2>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Real-time line headway, terminal corridors &amp; interchange telemetry
              </span>
            </div>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close modal">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body" style={{ padding: '1.25rem' }}>
          {/* Top Live Banner */}
          <div
            style={{
              background: 'linear-gradient(135deg, #0a1628 0%, #0f4c3a 100%)',
              color: '#fff',
              borderRadius: '10px',
              padding: '1rem',
              marginBottom: '1.25rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                <span className="live-dot" />
                <strong style={{ fontSize: '0.95rem' }}>DMRC Network Status: Normal Operations</strong>
              </div>
              <p style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.75)', margin: 0 }}>
                Trains operating with peak frequency across all 11 active metro corridors (262 stations).
              </p>
            </div>
            <button
              onClick={fetchStatus}
              disabled={loading}
              className="btn-icon"
              style={{ color: '#fff', background: 'rgba(255,255,255,0.15)', padding: '0.5rem', borderRadius: '8px' }}
              title="Refresh live telemetry"
            >
              <RefreshCw size={16} className={loading ? 'spin' : ''} />
            </button>
          </div>

          {error && (
            <div className="alert-box alert-danger" style={{ marginBottom: '1rem' }}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {/* Line Corridor Cards Grid */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {data?.lines.map((line: MetroLineStatus) => (
              <div
                key={line.line_code}
                style={{
                  background: 'var(--bg-app)',
                  border: '1px solid var(--border)',
                  borderLeft: `5px solid ${line.color_hex}`,
                  borderRadius: '8px',
                  padding: '0.85rem 1rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.5rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <span
                      style={{
                        backgroundColor: line.color_hex,
                        color: line.text_color_hex,
                        fontWeight: 700,
                        fontSize: '0.82rem',
                        padding: '0.2rem 0.55rem',
                        borderRadius: '4px',
                        letterSpacing: '0.2px',
                      }}
                    >
                      {line.line_name}
                    </span>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      ({line.total_stations} Stations)
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem' }}>
                    <span className="badge badge-success" style={{ padding: '0.15rem 0.5rem', fontSize: '0.75rem' }}>
                      <CheckCircle size={11} style={{ marginRight: 3, verticalAlign: 'middle' }} />
                      {line.status}
                    </span>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                      Headway: <strong>{line.headway_peak}</strong>
                    </span>
                  </div>
                </div>

                <div style={{ fontSize: '0.84rem', color: 'var(--text-main)', fontWeight: 500 }}>
                  {line.terminals}
                </div>

                {line.interchanges && line.interchanges.length > 0 && (
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
                    <strong style={{ color: 'var(--text-main)' }}>Key Interchanges:</strong>
                    {line.interchanges.map((ic, idx) => (
                      <span
                        key={idx}
                        style={{
                          background: 'rgba(0,0,0,0.04)',
                          padding: '0.1rem 0.4rem',
                          borderRadius: '3px',
                          border: '1px solid rgba(0,0,0,0.06)',
                        }}
                      >
                        {ic}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div
            style={{
              marginTop: '1.25rem',
              padding: '0.75rem',
              background: '#f0fdf4',
              border: '1px solid #bbf7d0',
              borderRadius: '8px',
              fontSize: '0.78rem',
              color: '#166534',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <Clock size={15} style={{ flexShrink: 0 }} />
            <span>
              DMRC operational hours: 05:30 to 23:30 IST. Standard fare tier: ₹10 (0-2km), ₹20 (2-5km), ₹30 (5-12km), ₹40 (12-21km), ₹50 (21-32km), ₹60 (&gt;32km).
            </span>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

