import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  Maximize2,
  Minimize2,
  Navigation,
  Layers,
  MapPin,
  TrainTrack,
  Bus,
  Footprints,
  RotateCcw,
} from 'lucide-react';
import { Journey, JourneyLeg, SafarSetuAPI } from '../lib/api';

interface RouteMapProps {
  journey: Journey | null;
  activeLegIndex?: number | null;
  onSelectLeg?: (index: number) => void;
  className?: string;
}

const getLineColor = (leg: JourneyLeg): { color: string; dashArray?: string; weight: number } => {
  if (leg.mode === 'walking' || leg.mode === 'walk') {
    return { color: '#64748b', dashArray: '6, 8', weight: 4 };
  }
  if (leg.mode === 'metro') {
    const text = (leg.route_short_name || leg.route_long_name || '').toUpperCase();
    if (text.includes('YELLOW')) return { color: '#eab308', weight: 6 };
    if (text.includes('BLUE')) return { color: '#2563eb', weight: 6 };
    if (text.includes('RED')) return { color: '#dc2626', weight: 6 };
    if (text.includes('VIOLET')) return { color: '#7c3aed', weight: 6 };
    if (text.includes('PINK')) return { color: '#ec4899', weight: 6 };
    if (text.includes('MAGENTA')) return { color: '#d946ef', weight: 6 };
    if (text.includes('GREEN')) return { color: '#16a34a', weight: 6 };
    if (text.includes('AIRPORT') || text.includes('ORANGE')) return { color: '#ea580c', weight: 6 };
    if (text.includes('AQUA')) return { color: '#0284c7', weight: 6 };
    if (text.includes('RAPID')) return { color: '#06b6d4', weight: 6 };
    if (text.includes('GRAY') || text.includes('GREY')) return { color: '#64748b', weight: 6 };
    return { color: '#7c3aed', weight: 6 };
  }
  return { color: '#0f766e', weight: 5 }; // DTC Bus
};

export const RouteMap: React.FC<RouteMapProps> = ({
  journey,
  activeLegIndex = null,
  onSelectLeg,
  className = '',
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const layerGroupRef = useRef<L.LayerGroup | null>(null);
  const busLayerRef = useRef<L.LayerGroup | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showLiveBuses, setShowLiveBuses] = useState(false);
  const [liveBusCount, setLiveBusCount] = useState<number>(0);

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Default center on Delhi: Connaught Place
    const map = L.map(mapContainerRef.current, {
      center: [28.6139, 77.2090],
      zoom: 11,
      zoomControl: false,
    });

    // Tile provider: Mapbox (if VITE_MAPBOX_TOKEN is configured) or CartoDB Voyager
    const mapboxToken = ((import.meta as any).env?.VITE_MAPBOX_TOKEN || '').trim();
    if (mapboxToken) {
      L.tileLayer(
        `https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/{z}/{x}/{y}?access_token=${mapboxToken}`,
        {
          attribution: '&copy; <a href="https://www.mapbox.com/">Mapbox</a> &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a>',
          tileSize: 512,
          zoomOffset: -1,
          maxZoom: 19,
        }
      ).addTo(map);
    } else {
      L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
        maxZoom: 19,
      }).addTo(map);
    }

    // Zoom control at bottom right
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    const layerGroup = L.layerGroup().addTo(map);
    layerGroupRef.current = layerGroup;
    mapInstanceRef.current = map;

    // Ensure tiles render cleanly after layout paints
    setTimeout(() => {
      map.invalidateSize();
    }, 200);

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Invalidate map size on fullscreen toggle
  useEffect(() => {
    if (mapInstanceRef.current) {
      setTimeout(() => {
        mapInstanceRef.current?.invalidateSize();
      }, 150);
    }
  }, [isFullscreen]);

  // Real-time Delhi OTD live bus positions overlay
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (!busLayerRef.current) {
      busLayerRef.current = L.layerGroup().addTo(map);
    }
    const busLayer = busLayerRef.current;
    busLayer.clearLayers();

    if (!showLiveBuses) {
      setLiveBusCount(0);
      return;
    }

    let isMounted = true;
    const fetchLiveBuses = async () => {
      try {
        const res = await SafarSetuAPI.getVehicles({ limit: 120 });
        if (!isMounted || !busLayerRef.current) return;
        busLayer.clearLayers();
        const vehicles = res.results || [];
        setLiveBusCount(vehicles.length);

        vehicles.forEach((v: any) => {
          if (!v.latitude || !v.longitude) return;
          const marker = L.marker([v.latitude, v.longitude], {
            icon: L.divIcon({
              html: `<div style="background: #0f766e; color: white; width: 22px; height: 22px; border-radius: 50%; border: 2px solid #ffffff; display: flex; align-items: center; justify-content: center; font-size: 11px; box-shadow: 0 2px 5px rgba(0,0,0,0.35);">🚌</div>`,
              className: 'custom-bus-marker',
              iconSize: [22, 22],
              iconAnchor: [11, 11],
            }),
          });
          marker.bindPopup(`
            <div style="font-family: inherit; font-size: 12.5px; line-height: 1.45;">
              <strong style="color: #0f766e;">🚌 Live DTC Bus: ${v.vehicle_id}</strong><br/>
              <span>Route: <b>${v.route_long_name || v.route_id || 'Delhi Transit'}</b></span><br/>
              <span>Speed: <b>${v.speed_kmh ? `${v.speed_kmh.toFixed(1)} km/h` : '0 km/h (At Stop)'}</b></span><br/>
              <span style="font-size: 10.5px; color: #64748b;">Source: Delhi OTD GTFS-RT (${res.feed_freshness})</span>
            </div>
          `);
          marker.addTo(busLayer);
        });
      } catch (err) {
        console.warn('Realtime bus fetch error:', err);
      }
    };

    fetchLiveBuses();
    const interval = setInterval(fetchLiveBuses, 15000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [showLiveBuses]);

  // Update route polyline and stop pins dynamically whenever journey changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layerGroup = layerGroupRef.current;
    if (!map || !layerGroup) return;

    layerGroup.clearLayers();

    if (!journey || !journey.legs || journey.legs.length === 0) {
      return;
    }

    const allCoords: [number, number][] = [];

    journey.legs.forEach((leg, legIdx) => {
      const lineStyle = getLineColor(leg);
      const isMetro = leg.mode === 'metro';
      const isWalking = leg.mode === 'walking' || leg.mode === 'walk';

      // 1. Determine polyline coordinates for this leg
      let legCoords: [number, number][] = [];
      if (leg.path_coordinates && leg.path_coordinates.length > 0) {
        legCoords = leg.path_coordinates as [number, number][];
      } else {
        if (leg.from_stop_lat && leg.from_stop_lon && leg.to_stop_lat && leg.to_stop_lon) {
          legCoords = [
            [leg.from_stop_lat, leg.from_stop_lon],
            [leg.to_stop_lat, leg.to_stop_lon],
          ];
        }
      }

      if (legCoords.length >= 2) {
        allCoords.push(...legCoords);

        // Polyline
        const polyline = L.polyline(legCoords, {
          color: lineStyle.color,
          weight: activeLegIndex === legIdx ? lineStyle.weight + 3 : lineStyle.weight,
          opacity: 0.9,
          dashArray: lineStyle.dashArray,
          lineCap: 'round',
          lineJoin: 'round',
        });

        const legTitle = isWalking
          ? `Walk (~${Math.round(leg.distance_meters || 0)}m)`
          : isMetro
          ? `Metro ${leg.route_short_name || ''} towards ${leg.headsign || leg.to_stop_name}`
          : `Bus ${leg.route_short_name || leg.route_id || ''} towards ${leg.headsign || leg.to_stop_name}`;

        polyline.bindPopup(`
          <div style="font-family: inherit; font-size: 13px; line-height: 1.4;">
            <strong style="color: ${lineStyle.color};">${legTitle}</strong><br/>
            <span>From: <b>${leg.from_stop_name}</b></span><br/>
            <span>To: <b>${leg.to_stop_name}</b></span><br/>
            <span>Duration: <b>${Math.round(leg.duration_minutes)} mins</b></span>
            ${leg.fare_inr ? `<br/><span style="color: #166534; font-weight: 700;">Fare: ₹${leg.fare_inr.toFixed(0)}</span>` : ''}
          </div>
        `);

        if (onSelectLeg) {
          polyline.on('click', () => onSelectLeg(legIdx));
        }

        polyline.addTo(layerGroup);
      }

      // 2. Add Stop Pins and Intermediate Station Nodes
      const stopsToRender = leg.stops_detail && leg.stops_detail.length > 0
        ? leg.stops_detail
        : [
            ...(leg.from_stop_lat && leg.from_stop_lon
              ? [{ stop_id: leg.from_stop_id, stop_name: leg.from_stop_name, lat: leg.from_stop_lat, lon: leg.from_stop_lon, is_board: true, is_alight: false, mode: leg.mode }]
              : []),
            ...(leg.to_stop_lat && leg.to_stop_lon
              ? [{ stop_id: leg.to_stop_id, stop_name: leg.to_stop_name, lat: leg.to_stop_lat, lon: leg.to_stop_lon, is_board: false, is_alight: true, mode: leg.mode }]
              : []),
          ];

      stopsToRender.forEach((stop, sIdx) => {
        const isJourneyStart = legIdx === 0 && sIdx === 0;
        const isJourneyEnd = legIdx === journey.legs.length - 1 && sIdx === stopsToRender.length - 1;
        const isInterchange = !isJourneyStart && !isJourneyEnd && (stop.is_board || stop.is_alight);

        let iconHtml = '';
        let iconSize: [number, number] = [14, 14];
        let iconAnchor: [number, number] = [7, 7];

        if (isJourneyStart) {
          // Green Boarding Pin
          iconHtml = `
            <div style="background: #16a34a; border: 2.5px solid #ffffff; width: 26px; height: 26px; border-radius: 50%; box-shadow: 0 2px 5px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; color: white; font-size: 13px; font-weight: bold;">
              A
            </div>
          `;
          iconSize = [26, 26];
          iconAnchor = [13, 13];
        } else if (isJourneyEnd) {
          // Red Alighting Pin
          iconHtml = `
            <div style="background: #dc2626; border: 2.5px solid #ffffff; width: 26px; height: 26px; border-radius: 50%; box-shadow: 0 2px 5px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; color: white; font-size: 13px; font-weight: bold;">
              B
            </div>
          `;
          iconSize = [26, 26];
          iconAnchor = [13, 13];
        } else if (isInterchange) {
          // Blue Transfer Pin
          iconHtml = `
            <div style="background: #2563eb; border: 2px solid #ffffff; width: 18px; height: 18px; border-radius: 50%; box-shadow: 0 1px 4px rgba(0,0,0,0.25); display: flex; align-items: center; justify-content: center; color: white; font-size: 10px;">
              🔄
            </div>
          `;
          iconSize = [18, 18];
          iconAnchor = [9, 9];
        } else {
          // Intermediate Stop Dot
          iconHtml = `
            <div style="background: #ffffff; border: 2px solid ${lineStyle.color}; width: 10px; height: 10px; border-radius: 50%; box-shadow: 0 1px 3px rgba(0,0,0,0.2);"></div>
          `;
          iconSize = [10, 10];
          iconAnchor = [5, 5];
        }

        const marker = L.marker([stop.lat, stop.lon], {
          icon: L.divIcon({
            html: iconHtml,
            className: 'custom-route-marker',
            iconSize,
            iconAnchor,
          }),
        });

        marker.bindPopup(`
          <div style="font-family: inherit; font-size: 12.5px; line-height: 1.4;">
            <strong>${stop.stop_name}</strong><br/>
            <span style="color: #64748b;">
              ${isJourneyStart ? '🟢 Origin Boarding Station' : isJourneyEnd ? '🔴 Final Destination' : isInterchange ? '🔄 Transfer Interchange' : '🚆 Intermediate Station'}
            </span>
          </div>
        `);

        marker.addTo(layerGroup);
      });
    });

    // Auto-fit bounds to show the entire route with padding
    if (allCoords.length > 0) {
      const bounds = L.latLngBounds(allCoords);
      map.fitBounds(bounds, { padding: [35, 35], maxZoom: 15, animate: true });
    }
  }, [journey, activeLegIndex]);

  const handleRecenter = () => {
    if (!mapInstanceRef.current || !journey) return;
    const allCoords: [number, number][] = [];
    journey.legs.forEach((leg) => {
      if (leg.path_coordinates) allCoords.push(...leg.path_coordinates as [number, number][]);
      else if (leg.from_stop_lat && leg.from_stop_lon) allCoords.push([leg.from_stop_lat, leg.from_stop_lon]);
    });
    if (allCoords.length > 0) {
      mapInstanceRef.current.fitBounds(L.latLngBounds(allCoords), { padding: [35, 35], animate: true });
    }
  };

  return (
    <div className={`route-map-wrapper ${isFullscreen ? 'fullscreen' : ''} ${className}`}>
      {/* Map Header Overlay */}
      <div className="route-map-overlay-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.82rem', fontWeight: 700 }}>
          <Navigation size={14} color="var(--primary)" />
          <span>Interactive Route Map</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          {/* Live Buses Toggle */}
          <button
            type="button"
            className="map-control-btn"
            onClick={() => setShowLiveBuses(!showLiveBuses)}
            title={showLiveBuses ? 'Hide Live Buses' : 'Show Live Delhi Buses from OTD'}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
              fontSize: '0.74rem',
              fontWeight: 700,
              background: showLiveBuses ? '#0f766e' : '#f8fafc',
              color: showLiveBuses ? '#ffffff' : 'var(--text-main)',
              borderColor: showLiveBuses ? '#0f766e' : '#cbd5e1',
            }}
          >
            <Bus size={12} />
            <span>{showLiveBuses ? `Buses (${liveBusCount})` : 'Live Buses'}</span>
          </button>

          {journey && (
            <button
              type="button"
              className="map-control-btn"
              onClick={handleRecenter}
              title="Recenter on Route"
            >
              <RotateCcw size={13} />
            </button>
          )}
          <button
            type="button"
            className="map-control-btn"
            onClick={() => setIsFullscreen(!isFullscreen)}
            title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Map'}
          >
            {isFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>
        </div>
      </div>

      {/* Leaflet Map Div */}
      <div ref={mapContainerRef} className="route-map-container" />

      {/* Map Legend Overlay */}
      {journey && (
        <div className="route-map-legend">
          <div className="legend-item">
            <span className="legend-dot" style={{ background: '#16a34a' }} />
            <span>Origin (A)</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot" style={{ background: '#2563eb' }} />
            <span>Interchange</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot" style={{ background: '#dc2626' }} />
            <span>Destination (B)</span>
          </div>
          <div className="legend-item">
            <span className="legend-line" style={{ borderBottom: '2px dashed #64748b' }} />
            <span>Walking</span>
          </div>
          {showLiveBuses && (
            <div className="legend-item">
              <span style={{ fontSize: '11px' }}>🚌</span>
              <span style={{ color: '#0f766e', fontWeight: 700 }}>Live Buses ({liveBusCount})</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
