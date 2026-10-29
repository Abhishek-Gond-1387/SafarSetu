import React, { useState } from 'react';
import { AlertTriangle, Info, X } from 'lucide-react';
import { HealthResponse } from '../lib/api';

interface DataFreshnessBannerProps {
  health: HealthResponse | null;
}

export const DataFreshnessBanner: React.FC<DataFreshnessBannerProps> = ({ health }) => {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const primarySource = health?.data_sources?.[0] || health?.sources?.[0];
  const isHistorical =
    primarySource?.status === 'expired' ||
    (primarySource?.warnings &&
      primarySource.warnings.some((w) => w.toLowerCase().includes('expired')));

  const endDate = primarySource?.feed_end_date || '2024-03-31';

  return (
    <div className="freshness-banner" role="status" aria-live="polite">
      <div className="container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
        <div className="freshness-banner-content">
          {isHistorical ? (
            <AlertTriangle size={18} color="#b45309" aria-hidden="true" />
          ) : (
            <Info size={18} color="#0f766e" aria-hidden="true" />
          )}
          <div>
            <strong>Data Integrity Advisory:</strong>{' '}
            {isHistorical ? (
              <span>
                Timetables are based on official Delhi DTC/DIMTS GTFS records (service validity ended {endDate}). Scheduled departures are indicative and real-world delays are not verified. Live vehicle positions are displayed strictly as GPS coordinates when available, never as synthetic arrival times.
              </span>
            ) : (
              <span>
                Official Delhi DTC/DIMTS GTFS network. Live tracking active when vehicle telemetry is verified. Missing fares are denoted as unknown.
              </span>
            )}
          </div>
        </div>

        <button
          onClick={() => setDismissed(true)}
          title="Dismiss advisory"
          style={{ padding: '4px', color: '#92400e', display: 'flex', alignItems: 'center' }}
          aria-label="Dismiss banner"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
};

