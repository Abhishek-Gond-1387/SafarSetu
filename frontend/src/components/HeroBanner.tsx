import React from 'react';
import { ArrowDown, Navigation, Compass, MapPin, Bus, TrainTrack, Sparkles } from 'lucide-react';
import heroBg from '../assets/hero-delhi-transit.jpg';

interface HeroBannerProps {
  onExploreClick?: () => void;
}

export const HeroBanner: React.FC<HeroBannerProps> = ({ onExploreClick }) => {
  const handleScrollToSearch = () => {
    if (onExploreClick) {
      onExploreClick();
      return;
    }
    const searchSection = document.getElementById('planner-explorer-section');
    if (searchSection) {
      searchSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <section className="delhi-transit-hero">
      {/* Atmospheric Background & Color-Grading Overlays */}
      <div className="hero-bg-media" style={{ backgroundImage: `url(${heroBg})` }}>
        {/* Color Grading: Left-to-Right Deep Atmospheric Contrast Scrim */}
        <div className="hero-scrim-primary" />
        {/* Color Grading: Subtle Top & Bottom Vignette for Seamless Blending */}
        <div className="hero-scrim-vertical" />
        {/* Color Grading: Ambient Horizon Warm Glow */}
        <div className="hero-scrim-warmth" />
      </div>

      <div className="container hero-inner-container">
        <div className="hero-content-column">
          {/* Official NCR Badge */}
          <div className="hero-badge-pill">
            <span className="hero-badge-dot" />
            <span className="hero-badge-text">Delhi / NCR Multimodal Transit Engine</span>
            <span className="hero-badge-devanagari">सफ़रसेतु</span>
          </div>

          {/* Core 3-Line Punchy Headline */}
          <h1 className="hero-main-title">
            <span className="title-line">Your city.</span>
            <span className="title-line">Every route.</span>
            <span className="title-line title-highlight">One tap.</span>
          </h1>

          {/* Exact Subtitle Requested */}
          <p className="hero-subtitle">
            Real-time bus positions, timetable-accurate journey planning, and transfer guidance across Delhi's 6,342 stops.
          </p>

          {/* Quick CTA to jump right into search */}
          <div className="hero-cta-group">
            <button
              type="button"
              className="hero-primary-btn"
              onClick={handleScrollToSearch}
              title="Start exploring routes across Delhi"
            >
              <Compass size={18} />
              <span>Explore Routes &amp; Live Buses</span>
              <ArrowDown size={16} className="btn-bounce-arrow" />
            </button>

            <div className="hero-live-indicator">
              <span className="live-ping-dot" />
              <span>DTC Bus &amp; DMRC Metro Network Active</span>
            </div>
          </div>

          {/* Exact 3 Metrics Requested */}
          <div className="hero-stats-deck">
            {/* Stat 1 */}
            <div className="hero-stat-card">
              <div className="stat-card-glow cyan-glow" />
              <div className="stat-icon-wrapper cyan">
                <MapPin size={18} />
              </div>
              <div className="stat-card-text">
                <span className="stat-card-number">6,342</span>
                <span className="stat-card-label">Bus Stops</span>
              </div>
            </div>

            {/* Stat 2 */}
            <div className="hero-stat-card">
              <div className="stat-card-glow emerald-glow" />
              <div className="stat-icon-wrapper emerald">
                <Bus size={18} />
              </div>
              <div className="stat-card-text">
                <span className="stat-card-number">2,964</span>
                <span className="stat-card-label">Routes</span>
              </div>
            </div>

            {/* Stat 3 */}
            <div className="hero-stat-card">
              <div className="stat-card-glow amber-glow" />
              <div className="stat-icon-wrapper amber">
                <TrainTrack size={18} />
              </div>
              <div className="stat-card-text">
                <span className="stat-card-number">78K+</span>
                <span className="stat-card-label">Trips Loaded</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

