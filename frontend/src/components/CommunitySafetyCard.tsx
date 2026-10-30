import React, { useState, useEffect } from 'react';
import {
  Shield,
  Sun,
  Moon,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  MessageSquareHeart,
  Info,
  Clock,
  Sparkles,
} from 'lucide-react';
import {
  SafarSetuAPI,
  Journey,
  RouteSafetyInsightsResponse,
  SafetyInsightsSummary,
} from '../lib/api';

export interface CommunitySafetyCardProps {
  journey: Journey;
  onOpenFeedback: () => void;
}

export const CommunitySafetyCard: React.FC<CommunitySafetyCardProps> = ({
  journey,
  onOpenFeedback,
}) => {
  const [timeFilter, setTimeFilter] = useState<'all' | 'daytime' | 'nighttime'>('all');
  const [loading, setLoading] = useState(false);
  const [insights, setInsights] = useState<RouteSafetyInsightsResponse | null>(null);
  const [expandedSegments, setExpandedSegments] = useState(false);

  // Derive route ID and segments
  const originStopId = journey.legs?.[0]?.from_stop_id || 'origin';
  const destStopId = journey.legs?.[journey.legs.length - 1]?.to_stop_id || 'destination';
  const routeId = `route_${originStopId}_${destStopId}`;

  const segmentIds = journey.legs
    ? journey.legs.map((l) => l.from_stop_id).filter(Boolean) as string[]
    : [];

  useEffect(() => {
    fetchInsights();
  }, [routeId, timeFilter]);

  const fetchInsights = async () => {
    try {
      setLoading(true);
      const res = await SafarSetuAPI.getRouteSafetyInsights(routeId, segmentIds, timeFilter);
      setInsights(res);
    } catch (e) {
      console.warn('[HerRoute] Could not fetch route safety insights:', e);
    } finally {
      setLoading(false);
    }
  };

  const overall = insights?.overall;
  const segments = insights?.segments || {};
  const segmentKeys = Object.keys(segments);

  return (
    <div className="herroute-safety-card">
      {/* Header */}
      <div className="herroute-card-header">
        <div className="herroute-title-group">
          <div className="herroute-shield-icon">
            <Shield size={16} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
              <strong className="herroute-title-text">Community Safety Insights</strong>
              <span className="herroute-brand-pill">HerRoute</span>
            </div>
            <span className="herroute-subtitle-text">
              Real self-reported experiences by women travelers
            </span>
          </div>
        </div>

        {/* Time Filter Toggle */}
        <div className="herroute-time-pill-group">
          <button
            type="button"
            className={`herroute-pill-btn ${timeFilter === 'all' ? 'active' : ''}`}
            onClick={() => setTimeFilter('all')}
            title="All community feedback"
          >
            All
          </button>
          <button
            type="button"
            className={`herroute-pill-btn ${timeFilter === 'daytime' ? 'active' : ''}`}
            onClick={() => setTimeFilter('daytime')}
            title="Filter by daytime reports"
          >
            <Sun size={12} />
            <span className="time-btn-label">Day</span>
          </button>
          <button
            type="button"
            className={`herroute-pill-btn ${timeFilter === 'nighttime' ? 'active' : ''}`}
            onClick={() => setTimeFilter('nighttime')}
            title="Filter by nighttime reports"
          >
            <Moon size={12} />
            <span className="time-btn-label">Night</span>
          </button>
        </div>
      </div>

      {/* Body: State Handling */}
      <div className="herroute-card-body">
        {loading ? (
          <div className="herroute-loading-strip">
            <span className="herroute-pulse-dot" />
            <span>Loading community reports...</span>
          </div>
        ) : !overall || !overall.has_sufficient_data ? (
          /* Empty / Insufficient Data State */
          <div className="herroute-empty-state">
            <div className="herroute-empty-content">
              <Info size={16} color="#6366f1" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <strong>Not enough community feedback available for this route.</strong>
                <p>
                  Help fellow women commuters by sharing your experience after completing this journey.
                </p>
              </div>
            </div>
            <button
              type="button"
              className="herroute-feedback-trigger-btn"
              onClick={onOpenFeedback}
            >
              <MessageSquareHeart size={14} />
              <span>Share Journey Feedback</span>
            </button>
          </div>
        ) : (
          /* Verified Community Feedback State */
          <div className="herroute-insights-content">
            {/* Counts Row */}
            <div className="herroute-counts-row">
              <div className="experience-metric positive">
                <span className="metric-dot green" />
                <span className="metric-number">{overall.comfortable_count}</span>
                <span className="metric-label">positive experiences</span>
              </div>

              {overall.uncomfortable_count > 0 && (
                <div className="experience-metric uncomfortable">
                  <span className="metric-dot amber" />
                  <span className="metric-number">{overall.uncomfortable_count}</span>
                  <span className="metric-label">uncomfortable</span>
                </div>
              )}

              {overall.unsafe_count > 0 && (
                <div className="experience-metric unsafe">
                  <span className="metric-dot red" />
                  <span className="metric-number">{overall.unsafe_count}</span>
                  <span className="metric-label">unsafe reports</span>
                </div>
              )}

              <span className="total-reports-tag">
                Based on {overall.total_reports} report{overall.total_reports > 1 ? 's' : ''}
              </span>
            </div>

            {/* Time Context Notice (e.g. Limited Nighttime feedback) */}
            {overall.time_context_notice && (
              <div className="herroute-time-notice">
                <Clock size={13} />
                <span>{overall.time_context_notice}</span>
              </div>
            )}

            {/* Top Influencing Factors / Reported Concerns */}
            {overall.frequent_concerns && overall.frequent_concerns.length > 0 && (
              <div className="herroute-concerns-row">
                <span className="concerns-prefix">Key observations:</span>
                <div className="concerns-chips-wrap">
                  {overall.frequent_concerns.map((c, i) => (
                    <span key={i} className="concern-pill">
                      {c.label} ({c.count})
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Segment Breakdown Accordion */}
            {segmentKeys.length > 0 && (
              <div className="herroute-segments-accordion">
                <button
                  type="button"
                  className="herroute-toggle-segments-btn"
                  onClick={() => setExpandedSegments(!expandedSegments)}
                >
                  <span>
                    {expandedSegments ? 'Hide' : 'View'} Segment Safety Breakdown ({segmentKeys.length} stops)
                  </span>
                  {expandedSegments ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </button>

                {expandedSegments && (
                  <div className="herroute-segments-list">
                    {segmentKeys.map((sid) => {
                      const seg = segments[sid];
                      if (!seg || !seg.has_sufficient_data) return null;
                      return (
                        <div key={sid} className="herroute-segment-row">
                          <span className="segment-row-title">{sid}</span>
                          <div className="segment-row-badges">
                            <span className="badge-pos">+{seg.comfortable_count}</span>
                            {seg.uncomfortable_count > 0 && (
                              <span className="badge-neg">⚠️ {seg.uncomfortable_count}</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Footer with Share Feedback Action */}
            <div className="herroute-card-footer">
              <span className="herroute-disclaimer">
                Self-reported community feedback. Does not guarantee safety.
              </span>

              <button
                type="button"
                className="herroute-feedback-trigger-btn"
                onClick={onOpenFeedback}
              >
                <MessageSquareHeart size={14} />
                <span>Share Experience</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CommunitySafetyCard;
