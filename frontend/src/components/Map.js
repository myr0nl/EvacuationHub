// Performance-optimized React imports: useMemo, useCallback, React.memo
import React, { useMemo, useEffect, useCallback, useState } from 'react';
import { MapContainer, Marker, Popup, Circle, Polyline, useMap, AttributionControl } from 'react-leaflet';
import TileLayerWithFallback from './TileLayerWithFallback';
import MarkerClusterGroup from 'react-leaflet-markercluster';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import './Map.css';
import LocationPicker from './LocationPicker';
import MapLoadingSkeleton from './MapLoadingSkeleton';
import DisasterBottomSheet from './DisasterBottomSheet';
import useDeviceDetection from '../hooks/useDeviceDetection';
// Security: Import Lucide React icons to replace dangerouslySetInnerHTML
import { Star, Award, CheckCircle, Circle as CircleIcon, AlertTriangle, XCircle } from 'lucide-react';

// Fix for default marker icons in react-leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

// ============================================================================
// CONSTANTS - Magic numbers extracted for maintainability and documentation
// ============================================================================

// Marker color constants
const MARKER_COLORS = {
  nasa_firms: '#ff6b00',
  noaa: '#FFA500'
};

// Zoom calculation and map animation constants
const MAP_CONSTANTS = {
  // Earth's circumference at the equator in kilometers
  // Used to calculate zoom level based on desired visible radius
  EARTH_CIRCUMFERENCE_KM: 40075,

  // Multiplier for visible area (shows context beyond the radius)
  // E.g., if user wants 20 miles visible, we show 20 * 2.5 = 50 miles
  ZOOM_RADIUS_MULTIPLIER: 2.5,

  // Zoom level bounds for auto-zoom functionality
  MIN_ZOOM_ABSOLUTE: 2,        // Minimum zoom (world view)
  MAX_ZOOM_ABSOLUTE: 18,       // Maximum zoom (street level)
  MIN_ZOOM_AUTO: 4,            // Minimum auto-zoom level (prevents too-far zoom out)
  MAX_ZOOM_AUTO: 15,           // Maximum auto-zoom level (prevents excessive zoom in)

  // Animation and animation thresholds to prevent jittery/excessive updates
  MARKER_SYNC_DELAY_MS: 100,         // Delay to prevent MarkerClusterGroup race conditions
  ZOOM_CHANGE_THRESHOLD: 0.5,        // Minimum zoom level change to trigger animation
  CENTER_CHANGE_THRESHOLD: 0.001,    // Minimum lat/lon change to trigger animation

  // Unit conversions
  MILES_TO_KM: 1.609,
  MILES_TO_METERS: 1609.34,

  // Haversine distance calculation
  // Earth's radius in miles (used for calculating distances between coordinates)
  EARTH_RADIUS_MILES: 3959
};

// Custom icon configurations for different data sources and types
// NOTE: This function is called by Leaflet, not directly by React, so it doesn't need memoization.
// Icons are cached per marker in the createMarkers function via useMemo.
const getMarkerIcon = (item, isHovered = false, isSelected = false) => {
  const scale = isHovered ? 1.3 : isSelected ? 1.5 : 1;
  const extraShadow = isHovered || isSelected ? '; transform: scale(1.2);' : '';

  // Different styling based on data source
  if (item.source === 'nasa_firms') {
    return L.divIcon({
      className: 'custom-marker wildfire-marker',
      html: `<div style="background-color: ${MARKER_COLORS.nasa_firms}; width: ${20 * scale}px; height: ${20 * scale}px; border-radius: 50%; border: 2px solid #ff0000; box-shadow: 0 2px 8px rgba(255,107,0,0.5)${extraShadow}"></div>`,
      iconSize: [20 * scale, 20 * scale],
      iconAnchor: [10 * scale, 10 * scale],
      popupAnchor: [0, -10 * scale]
    });
  }

  if (item.source === 'noaa_weather' || item.source === 'noaa') {
    const severityColors = {
      'Extreme': '#8B0000',
      'Severe': '#FF0000',
      'Moderate': '#FFA500',
      'Minor': '#FFD700',
      'Unknown': '#808080'
    };
    const color = severityColors[item.severity] || severityColors.Unknown;

    return L.divIcon({
      className: 'custom-marker weather-marker',
      html: `<div style="background-color: ${color}; width: ${22 * scale}px; height: ${22 * scale}px; border-radius: 3px; border: 2px solid white; box-shadow: 0 2px 8px rgba(0,0,0,0.4)${extraShadow}"></div>`,
      iconSize: [22 * scale, 22 * scale],
      iconAnchor: [11 * scale, 11 * scale],
      popupAnchor: [0, -11 * scale]
    });
  }

  // User-submitted reports - Use emoji icons with blue outline circle
  const disasterEmojis = {
    earthquake: '🏚️',
    flood: '🌊',
    fire: '🔥',
    wildfire: '🔥',
    storm: '⛈️',
    hurricane: '🌀',
    tornado: '🌪️',
    landslide: '🏔️',
    tsunami: '🌊',
    volcano: '🌋',
    drought: '💧',
    other: '⚠️'
  };

  const type = item.disaster_type || item.type;
  const emoji = disasterEmojis[type?.toLowerCase()] || disasterEmojis.other;

  // Blue outline circle to differentiate from official sources (red for nasa_firms, square for noaa)
  const blueOutline = '#3B82F6'; // Tailwind blue-500
  const baseSize = 30;
  const size = baseSize * scale;

  return L.divIcon({
    className: 'custom-marker user-marker',
    html: `
      <div style="
        width: ${size}px;
        height: ${size}px;
        border-radius: 50%;
        border: 3px solid ${blueOutline};
        background-color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: ${size * 0.6}px;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4)${extraShadow};
      ">${emoji}</div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2]
  });
};

// Security: React component to replace HTML string generation (prevents XSS)
const SeverityBadge = ({ severity }) => {
  const badges = {
    low: { text: 'Low', color: '#27ae60' },
    medium: { text: 'Medium', color: '#f39c12' },
    high: { text: 'High', color: '#e74c3c' },
    critical: { text: 'Critical', color: '#c0392b' },
    extreme: { text: 'Extreme', color: '#8B0000' },
    severe: { text: 'Severe', color: '#FF0000' },
    moderate: { text: 'Moderate', color: '#FFA500' },
    minor: { text: 'Minor', color: '#FFD700' }
  };

  const badge = badges[severity?.toLowerCase()] || badges.low;

  return (
    <span style={{
      backgroundColor: badge.color,
      color: 'white',
      padding: '2px 8px',
      borderRadius: '4px',
      fontSize: '0.8rem',
      fontWeight: 600
    }}>
      {badge.text}
    </span>
  );
};

// Security: React component to replace HTML string generation (prevents XSS)
const ConfidenceBadge = ({ level, score }) => {
  const badges = {
    'High': { color: '#27ae60', Icon: CheckCircle },
    'Medium': { color: '#f39c12', Icon: AlertTriangle },
    'Low': { color: '#e74c3c', Icon: XCircle }
  };

  const badge = badges[level] || badges.Low;
  const percentage = Math.round(score * 100);
  const { Icon } = badge;

  return (
    <span style={{
      backgroundColor: badge.color,
      color: 'white',
      padding: '2px 8px',
      borderRadius: '4px',
      fontSize: '0.8rem',
      fontWeight: 600,
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px'
    }}>
      <Icon size={12} />
      {level} ({percentage}%)
    </span>
  );
};

// Get color for route polyline based on index and selection state
const getRouteColor = (route, index, isSelected) => {
  if (isSelected) return '#3B82F6'; // Blue for selected
  // Distinct, high-contrast colors for up to 6 routes
  // Uses maximum hue separation for easy differentiation
  const colors = [
    '#10b981', // Emerald Green
    '#ef4444', // Bright Red
    '#8b5cf6', // Vibrant Purple
    '#f59e0b', // Amber Orange
    '#06b6d4', // Cyan
    '#ec4899'  // Pink
  ];
  return colors[index % colors.length];
};

// Helper function to check if two items are equal
const isItemEqual = (item1, item2) => {
  if (!item1 || !item2) return false;
  return item1.id === item2.id ||
         (item1.latitude === item2.latitude && item1.longitude === item2.longitude);
};

// Shallow comparison helper for objects (replaces inefficient JSON.stringify)
const shallowEqual = (obj1, obj2) => {
  // Handle null/undefined cases
  if (obj1 === obj2) return true;
  if (!obj1 || !obj2) return false;
  if (typeof obj1 !== 'object' || typeof obj2 !== 'object') return obj1 === obj2;

  // Compare object keys
  const keys1 = Object.keys(obj1);
  const keys2 = Object.keys(obj2);

  if (keys1.length !== keys2.length) return false;

  // Compare values (shallow - only one level deep)
  for (let key of keys1) {
    if (obj1[key] !== obj2[key]) return false;
  }

  return true;
};

// Security: React component for user credibility badges (prevents XSS)
const UserCredibilityBadge = ({ item }) => {
  // Check if report has user credibility information
  if (item.user_credibility_level && item.user_credibility_score !== undefined) {
    const badges = {
      'Expert': { Icon: Star, color: '#FFD700' },
      'Veteran': { Icon: Award, color: '#C0C0C0' },
      'Trusted': { Icon: CheckCircle, color: '#27ae60' },
      'Neutral': { Icon: CircleIcon, color: '#95a5a6' },
      'Caution': { Icon: AlertTriangle, color: '#f39c12' },
      'Unreliable': { Icon: XCircle, color: '#e74c3c' }
    };

    const badge = badges[item.user_credibility_level] || badges.Neutral;
    const { Icon } = badge;

    return (
      <span style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.3rem',
        backgroundColor: badge.color,
        color: 'white',
        padding: '0.3rem 0.6rem',
        borderRadius: '10px',
        fontSize: '0.75rem',
        fontWeight: 600,
        marginLeft: '0.5rem'
      }}>
        <Icon size={14} />
        {item.user_credibility_level} ({item.user_credibility_score})
      </span>
    );
  }

  return (
    <span style={{
      color: '#999',
      fontSize: '0.8rem',
      marginLeft: '0.5rem'
    }}>
      (Anonymous)
    </span>
  );
};

// Performance-optimized PopupContent component - memoized to prevent unnecessary re-renders
// This component returns JSX directly instead of HTML strings for better React integration
const PopupContent = React.memo(({ item, isAdmin, currentUser, onEditReport, onDeleteReport }) => {
  // User-submitted report (check for user_report source or legacy disaster_type field)
  if (item.source === 'user_report' || item.source === 'user_report_authenticated' || item.disaster_type || (!item.source && !item.brightness)) {
    const disasterType = item.type || item.disaster_type || 'DISASTER';
    const isAuthenticated = item.source === 'user_report_authenticated' || item.user_id;

    return (
      <div className="popup-content">
        <h3 className="popup-title">
          👤 USER REPORT: {disasterType.toUpperCase()}
          <UserCredibilityBadge item={item} />
        </h3>

        {isAuthenticated && item.user_display_name && (
          <div className="popup-field">
            <strong>Reported by:</strong>
            <p style={{ fontWeight: '600', color: '#1e40af' }}>
              {item.user_display_name}
            </p>
          </div>
        )}

        {item.confidence_level && item.confidence_score !== undefined && (
          <div className="popup-field">
            <strong>Confidence:</strong>
            <ConfidenceBadge level={item.confidence_level} score={item.confidence_score} />

            {/* AI Analysis Loading State */}
            {(item.ai_analysis_status === 'pending' || item.ai_analysis_status === 'processing') && !item.confidence_breakdown?.ai_enhancement?.reasoning && (
              <div style={{
                marginTop: '8px',
                padding: '10px',
                backgroundColor: '#e3f2fd',
                border: '1px solid #90caf9',
                borderRadius: '6px',
                fontSize: '0.85rem',
                color: '#1565c0',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <div style={{
                  width: '16px',
                  height: '16px',
                  border: '2px solid #90caf9',
                  borderTopColor: '#1565c0',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite'
                }}>
                  <style>{`
                    @keyframes spin {
                      0% { transform: rotate(0deg); }
                      100% { transform: rotate(360deg); }
                    }
                  `}</style>
                </div>
                <div>
                  <strong>AI Analysis:</strong> Analyzing report with GPT-4o-mini...
                  <div style={{ fontSize: '0.75rem', marginTop: '4px', opacity: 0.8 }}>
                    Refresh page in ~20 seconds to see results
                  </div>
                </div>
              </div>
            )}

            {/* AI Analysis Failed */}
            {item.ai_analysis_status === 'failed' && !item.confidence_breakdown?.ai_enhancement?.reasoning && (
              <div style={{
                marginTop: '8px',
                padding: '8px',
                backgroundColor: '#ffebee',
                border: '1px solid #ef5350',
                borderRadius: '6px',
                fontSize: '0.85rem',
                color: '#c62828'
              }}>
                <strong>⚠️ AI Analysis:</strong> Analysis failed (rate limit or API error)
              </div>
            )}

            {/* AI Analysis Completed */}
            {item.confidence_breakdown?.ai_enhancement?.reasoning && (
              <div style={{
                marginTop: '8px',
                padding: '10px',
                backgroundColor: '#e8f5e9',
                border: '1px solid #66bb6a',
                borderRadius: '6px',
                fontSize: '0.85rem',
                color: '#2e7d32'
              }}>
                <strong>✅ AI Analysis:</strong> {item.confidence_breakdown.ai_enhancement.reasoning}
              </div>
            )}
          </div>
        )}

        <div className="popup-field">
          <strong>Severity:</strong>
          <SeverityBadge severity={item.severity} />
        </div>

        {item.description && (
          <div className="popup-field">
            <strong>Description:</strong>
            <p>{item.description}</p>
          </div>
        )}

        <div className="popup-field">
          <strong>Location:</strong>
          {item.location_name && (
            <p style={{ marginBottom: '4px', fontWeight: '500' }}>
              📍 {item.location_name}
            </p>
          )}
          {item.latitude && item.longitude && (
            <p style={{ color: '#666', fontSize: '0.9rem' }}>
              {item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}
            </p>
          )}
        </div>

        {(item.reported_at || item.timestamp) && (
          <div className="popup-field">
            <strong>Reported:</strong>
            <p>{new Date(item.reported_at || item.timestamp).toLocaleString()}</p>
          </div>
        )}

        {item.affected_population && (
          <div className="popup-field">
            <strong>Affected Population:</strong>
            <p>{item.affected_population.toLocaleString()} people</p>
          </div>
        )}

        {/* Admin controls: Show edit/delete buttons for admins or report owners */}
        {(isAdmin || (currentUser && item.user_id === currentUser.uid)) && (
          <div className="popup-field" style={{
            marginTop: '12px',
            paddingTop: '12px',
            borderTop: '1px solid #e5e7eb',
            display: 'flex',
            gap: '8px'
          }}>
            {onEditReport && (
              <button
                onClick={() => onEditReport(item)}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  backgroundColor: '#3b82f6',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '0.9rem',
                  fontWeight: '500',
                  transition: 'background-color 0.2s'
                }}
                onMouseOver={(e) => e.target.style.backgroundColor = '#2563eb'}
                onMouseOut={(e) => e.target.style.backgroundColor = '#3b82f6'}
              >
                ✏️ Edit
              </button>
            )}
            {onDeleteReport && (
              <button
                onClick={() => onDeleteReport(item.id)}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  backgroundColor: '#ef4444',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '0.9rem',
                  fontWeight: '500',
                  transition: 'background-color 0.2s'
                }}
                onMouseOver={(e) => e.target.style.backgroundColor = '#dc2626'}
                onMouseOut={(e) => e.target.style.backgroundColor = '#ef4444'}
              >
                🗑️ Delete
              </button>
            )}
          </div>
        )}
      </div>
    );
  }

  // NASA FIRMS wildfire
  if (item.source === 'nasa_firms') {
    return (
      <div className="popup-content">
        <h3 className="popup-title">
          🔥 WILDFIRE (NASA FIRMS)
        </h3>

        {item.confidence_level && item.confidence_score !== undefined && (
          <div className="popup-field">
            <strong>Confidence:</strong>
            <ConfidenceBadge level={item.confidence_level} score={item.confidence_score} />
          </div>
        )}

        <div className="popup-field">
          <strong>Severity:</strong>
          <SeverityBadge severity={item.severity} />
        </div>

        <div className="popup-field">
          <strong>Brightness:</strong>
          <p>{item.brightness}K</p>
        </div>

        <div className="popup-field">
          <strong>Fire Radiative Power:</strong>
          <p>{item.frp} MW</p>
        </div>

        <div className="popup-field">
          <strong>Location:</strong>
          {item.latitude && item.longitude && (
            <p>{item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}</p>
          )}
        </div>

        <div className="popup-field">
          <strong>Detected:</strong>
          <p>{item.timestamp ? new Date(item.timestamp).toLocaleString() : `${item.acquisition_date || ''} ${item.acquisition_time || ''}`.trim()}</p>
        </div>
      </div>
    );
  }

  // NOAA weather alert
  if (item.source === 'noaa') {
    return (
      <div className="popup-content">
        <h3 className="popup-title">
          ⚠️ {item.event?.toUpperCase() || 'WEATHER ALERT'}
        </h3>

        {item.confidence_level && item.confidence_score !== undefined && (
          <div className="popup-field">
            <strong>Confidence:</strong>
            <ConfidenceBadge level={item.confidence_level} score={item.confidence_score} />
          </div>
        )}

        <div className="popup-field">
          <strong>Severity:</strong>
          <SeverityBadge severity={item.severity} />
        </div>

        <div className="popup-field">
          <strong>Urgency:</strong>
          <p>{item.urgency}</p>
        </div>

        <div className="popup-field">
          <strong>Certainty:</strong>
          <p>{item.certainty}</p>
        </div>

        {item.headline && (
          <div className="popup-field">
            <strong>Headline:</strong>
            <p>{item.headline}</p>
          </div>
        )}

        {item.area_desc && (
          <div className="popup-field">
            <strong>Area:</strong>
            <p>{item.area_desc}</p>
          </div>
        )}

        <div className="popup-field">
          <strong>Location:</strong>
          {item.latitude && item.longitude && (
            <p>{item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}</p>
          )}
        </div>

        {item.onset && (
          <div className="popup-field">
            <strong>Onset:</strong>
            <p>{new Date(item.onset).toLocaleString()}</p>
          </div>
        )}

        {item.expires && (
          <div className="popup-field">
            <strong>Expires:</strong>
            <p>{new Date(item.expires).toLocaleString()}</p>
          </div>
        )}
      </div>
    );
  }

  return null;
});

// Component to handle sidebar state changes and update map controls
function SidebarStateHandler({ isSidebarOpen }) {
  const map = useMap();

  useEffect(() => {
    if (!map) return;

    // Immediately update map size when sidebar toggles (no animation)
    map.invalidateSize({ animate: false, pan: false });
  }, [map, isSidebarOpen]);

  return null;
}

// Component to handle map centering when mapCenter prop changes
// Auto-zoom controller based on map settings
function ZoomController({ userLocation, mapSettings }) {
  const map = useMap();

  // Extract specific values to use as dependencies (ensures React detects changes)
  const zoomRadius = mapSettings?.zoom_radius_mi || 20;
  const autoZoom = mapSettings?.auto_zoom ?? false;

  // Set minimum zoom level based on zoom_radius_mi (prevents zooming out too far)
  // This effect runs whenever the map or zoomRadius changes
  useEffect(() => {
    if (!map) return;

    try {
      // Calculate the minimum zoom level based on the desired visible radius
      // The zoom level determines how much area is visible on the map
      // Formula derived from: At zoom level Z, the visible width ≈ EARTH_CIRCUMFERENCE_KM / 2^Z
      // We want the radius to fit comfortably in view, so we use radius * ZOOM_RADIUS_MULTIPLIER as the target width
      const radiusKm = zoomRadius * MAP_CONSTANTS.MILES_TO_KM;
      const targetWidthKm = radiusKm * MAP_CONSTANTS.ZOOM_RADIUS_MULTIPLIER;
      const minZoom = Math.log2(MAP_CONSTANTS.EARTH_CIRCUMFERENCE_KM / targetWidthKm);
      const clampedMinZoom = Math.max(
        MAP_CONSTANTS.MIN_ZOOM_ABSOLUTE,
        Math.min(MAP_CONSTANTS.MAX_ZOOM_AUTO, Math.round(minZoom))
      );

      // Set the minimum zoom level (user can't zoom out farther than this)
      map.setMinZoom(clampedMinZoom);

      console.log(`Zoom restriction: ${zoomRadius} mi radius → minimum zoom level ${clampedMinZoom} (prevents zooming out beyond this)`);
    } catch (error) {
      console.debug('Map zoom restriction error (expected during transitions):', error.message);
    }
  }, [map, zoomRadius]); // Depend on the specific value, not the whole object

  // Auto-zoom to user location when enabled OR when zoom radius changes
  useEffect(() => {
    if (!map || !userLocation || !autoZoom) return;

    // Use a timeout to ensure DOM is ready and prevent race conditions with MarkerClusterGroup
    const timeoutId = setTimeout(() => {
      try {
        const mapPane = map.getPane('mapPane');
        if (!mapPane || !mapPane._leaflet_pos) {
          console.warn('Map pane not ready, skipping auto-zoom');
          return;
        }

        // Calculate the appropriate zoom level for the radius (same formula as minZoom)
        const radiusKm = zoomRadius * MAP_CONSTANTS.MILES_TO_KM;
        const targetWidthKm = radiusKm * MAP_CONSTANTS.ZOOM_RADIUS_MULTIPLIER;
        const zoom = Math.log2(MAP_CONSTANTS.EARTH_CIRCUMFERENCE_KM / targetWidthKm);
        const clampedZoom = Math.max(
          MAP_CONSTANTS.MIN_ZOOM_AUTO,
          Math.min(MAP_CONSTANTS.MAX_ZOOM_ABSOLUTE, Math.round(zoom))
        );

        // Get current view to check if we need to zoom
        const currentZoom = map.getZoom();
        const currentCenter = map.getCenter();

        // Only zoom if significantly different (prevents unnecessary animations)
        const zoomDiff = Math.abs(currentZoom - clampedZoom);
        const centerDiff = Math.abs(currentCenter.lat - userLocation.lat) + Math.abs(currentCenter.lng - userLocation.lon);

        if (zoomDiff > MAP_CONSTANTS.ZOOM_CHANGE_THRESHOLD || centerDiff > MAP_CONSTANTS.CENTER_CHANGE_THRESHOLD) {
          // Check if reduced motion is enabled (prevent jittery map movements during screen recording)
          const reducedMotion = document.documentElement.classList.contains('reduced-motion');
          map.setView([userLocation.lat, userLocation.lon], clampedZoom, {
            animate: !reducedMotion,
            duration: reducedMotion ? 0 : 1
          });
          console.log(`Auto-zoom: ${zoomRadius} mi radius → zoom level ${clampedZoom}`);
        }
      } catch (error) {
        console.debug('Map auto-zoom error (expected during transitions):', error.message);
      }
    }, MAP_CONSTANTS.MARKER_SYNC_DELAY_MS); // Delay to prevent MarkerClusterGroup race conditions

    return () => clearTimeout(timeoutId);
  }, [map, userLocation, zoomRadius, autoZoom]); // Depend on specific values (zoomRadius triggers re-zoom when settings change)

  return null;
}

function MapCenterController({ center }) {
  const map = useMap();

  useEffect(() => {
    if (!map || !center) return;

    // DEFENSIVE: Check if map is still mounted and panes exist before manipulating
    try {
      const mapPane = map.getPane('mapPane');
      if (!mapPane || !mapPane._leaflet_pos) {
        console.warn('Map pane not ready, skipping map operation');
        return;
      }

      // Check if reduced motion is enabled (prevent jittery map movements)
      const reducedMotion = document.documentElement.classList.contains('reduced-motion');

      // Handle fitBounds for route overview
      if (center.fitBounds && center.geometry && center.geometry.length > 0) {
        // Convert [lon, lat] to [lat, lon] for Leaflet bounds
        const bounds = center.geometry.map(coord => [coord[1], coord[0]]);
        map.fitBounds(bounds, {
          padding: [50, 50], // Add padding around route
          animate: !reducedMotion,
          duration: reducedMotion ? 0 : 0.5
        });
      }
      // Handle normal center + zoom
      else if (center.lat && center.lng) {
        const zoom = center.zoom || 12;
        map.setView([center.lat, center.lng], zoom, {
          animate: !reducedMotion,
          duration: reducedMotion ? 0 : 1
        });
      }
    } catch (error) {
      // Silently catch errors during zoom transitions
      console.debug('Map operation error (expected during transitions):', error.message);
    }
  }, [center, map]);

  return null;
}

function Map({
  dataPoints = [],
  hoveredItem = null,
  selectedItem = null,
  userLocation = null,
  proximityRadius = 50,
  proximityAlerts = [],
  onRadiusChange = null,
  mapCenter = null,
  showRadiusCircle = true,
  safeZones = [],
  selectedSafeZone = null, // NEW: Selected safe zone to highlight on map
  routes = [],
  selectedRoute = null,
  locationPickerEnabled = false,
  onLocationPicked = null,
  pickedLocation = null, // NEW: Location picked for report form
  loading = false, // PERFORMANCE: Show loading skeleton while data is being fetched
  mapSettings = null, // NEW: Map settings for zoom and filtering
  isSidebarOpen = false, // NEW: Sidebar state for zoom control positioning
  isAdmin = false, // NEW: Admin status for edit/delete buttons
  currentUser = null, // NEW: Current user for ownership checks
  onDeleteReport = null, // NEW: Handler for deleting reports
  onEditReport = null // NEW: Handler for editing reports
}) {
  const defaultZoom = 4;

  // Mobile detection for bottom sheet
  const { isMobile } = useDeviceDetection();

  // State for mobile bottom sheet
  const [selectedDisasterForSheet, setSelectedDisasterForSheet] = useState(null);

  // Cache safe zone icons to prevent recreation on every render
  const safeZoneIcons = useMemo(() => {
    const selectedIcon = L.divIcon({
      className: 'safe-zone-marker selected',
      html: `<div style="
        background: #3b82f6;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        border: 3px solid white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        color: white;
        font-weight: bold;
        position: relative;
      ">🛡️<div style="position: absolute; top: -6px; right: -6px; background: white; width: 18px; height: 18px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; color: #3b82f6; border: 2px solid #3b82f6; font-weight: bold;">✓</div></div>`,
      iconSize: [40, 40],
      iconAnchor: [20, 20],
      popupAnchor: [0, -20]
    });

    const unselectedIcon = L.divIcon({
      className: 'safe-zone-marker',
      html: `<div style="
        background: #10b981;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        border: 3px solid white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        color: white;
        font-weight: bold;
        position: relative;
      ">🛡️</div>`,
      iconSize: [40, 40],
      iconAnchor: [20, 20],
      popupAnchor: [0, -20]
    });

    return { selected: selectedIcon, unselected: unselectedIcon };
  }, []); // Empty deps - only create once

  // Filter data points based on map settings display radius
  const filteredByDistance = useMemo(() => {
    if (!mapSettings || !userLocation || mapSettings.show_all_disasters) {
      return dataPoints; // Show all disasters if no settings or show_all enabled
    }

    const displayRadius = mapSettings.display_radius_mi || 20;

    return dataPoints.filter(item => {
      if (!item.latitude || !item.longitude) return false;

      // Calculate distance from user location using Haversine formula
      const dLat = (item.latitude - userLocation.lat) * Math.PI / 180;
      const dLon = (item.longitude - userLocation.lon) * Math.PI / 180;
      const a =
        Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(userLocation.lat * Math.PI / 180) * Math.cos(item.latitude * Math.PI / 180) *
        Math.sin(dLon/2) * Math.sin(dLon/2);
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
      const distance = MAP_CONSTANTS.EARTH_RADIUS_MILES * c;

      return distance <= displayRadius;
    });
  }, [dataPoints, userLocation, mapSettings]);

  // Use the filtered data points
  const allDataPoints = filteredByDistance;

  // Calculate map center based on all data points (memoized)
  const center = useMemo(() => {
    const defaultCtr = [37.0902, -95.7129]; // Center of US
    if (allDataPoints.length === 0) return defaultCtr;

    const validPoints = allDataPoints.filter(p => p.latitude && p.longitude);
    if (validPoints.length === 0) return defaultCtr;

    const latSum = validPoints.reduce((sum, r) => sum + r.latitude, 0);
    const lngSum = validPoints.reduce((sum, r) => sum + r.longitude, 0);

    return [latSum / validPoints.length, lngSum / validPoints.length];
  }, [allDataPoints]);

  const zoom = allDataPoints.length > 0 ? 5 : defaultZoom;

  // Group data points by source for separate clustering
  const groupedData = useMemo(() => {
    const groups = {
      wildfires: [],
      weatherAlerts: [],
      userReports: []
    };

    allDataPoints
      .filter(item => item.latitude && item.longitude)
      .forEach(item => {
        if (item.source === 'nasa_firms') {
          groups.wildfires.push(item);
        } else if (item.source === 'noaa' || item.source === 'noaa_weather') {
          groups.weatherAlerts.push(item);
        } else {
          groups.userReports.push(item);
        }
      });

    return groups;
  }, [allDataPoints]);

  // Create custom cluster icon based on type and count
  const createClusterCustomIcon = (cluster, type) => {
    const count = cluster.getChildCount();
    let baseColor, borderColor, label, size;

    // Determine size based on count (smaller range to prevent overlap)
    if (count < 10) {
      size = 36;
    } else if (count < 50) {
      size = 42;
    } else if (count < 100) {
      size = 48;
    } else {
      size = 54;
    }

    // Get color intensity based on count for each type
    const getColorVariation = (baseColors, count) => {
      // Color variations from light to dark based on count ranges
      if (count < 10) {
        return baseColors.light;
      } else if (count < 50) {
        return baseColors.medium;
      } else if (count < 100) {
        return baseColors.dark;
      } else {
        return baseColors.darkest;
      }
    };

    switch (type) {
      case 'wildfires':
        const wildfireColors = {
          light: '#ff9d5c',      // Light orange
          medium: '#ff6b00',     // Base orange
          dark: '#e65100',       // Dark orange
          darkest: '#bf360c'     // Darkest orange/red
        };
        baseColor = getColorVariation(wildfireColors, count);
        borderColor = '#ff0000';
        label = '🔥';
        break;

      case 'weatherAlerts':
        const weatherColors = {
          light: '#FFD54F',      // Light yellow-orange
          medium: '#FFA500',     // Base orange
          dark: '#FF8C00',       // Dark orange
          darkest: '#FF6347'     // Red-orange (tomato)
        };
        baseColor = getColorVariation(weatherColors, count);
        borderColor = '#FF0000';
        label = '🌩️';
        break;

      case 'userReports':
        const userColors = {
          light: '#64B5F6',      // Light blue
          medium: '#3498db',     // Base blue
          dark: '#2980b9',       // Dark blue
          darkest: '#1565C0'     // Darkest blue
        };
        baseColor = getColorVariation(userColors, count);
        borderColor = '#1976D2';
        label = '👤';
        break;

      default:
        baseColor = '#808080';
        borderColor = '#606060';
        label = '📍';
    }

    // Check if reduced motion is enabled
    const reducedMotion = document.documentElement.classList.contains('reduced-motion');

    return L.divIcon({
      html: `<div style="
        background-color: ${baseColor};
        border: 3px solid ${borderColor};
        border-radius: 50%;
        width: ${size}px;
        height: ${size}px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        color: white;
        box-shadow: 0 3px 10px rgba(0,0,0,0.5);
        font-size: 11px;
        ${reducedMotion ? '' : 'transition: all 0.3s ease;'}
      ">
        <div style="text-align: center;">
          <div style="font-size: ${size * 0.4}px; line-height: 1;">${label}</div>
          <div style="font-size: ${size * 0.25}px; line-height: 1; font-weight: bold;">${count}</div>
        </div>
      </div>`,
      className: `custom-cluster-icon ${type}-cluster`,
      iconSize: L.point(size, size, true)
    });
  };

  // Performance-optimized marker creation with useCallback to prevent recreation on every render
  // Dependencies: hoveredItem, selectedItem, isMobile (only recreate when hover/selection/mobile state changes)
  const createMarkers = useCallback((items, type) => {
    return items.map((item, index) => {
      const isHovered = hoveredItem && isItemEqual(item, hoveredItem);
      const isSelected = selectedItem && isItemEqual(item, selectedItem);

      return (
        <Marker
          key={item.id || `${type}-marker-${index}`}
          position={[item.latitude, item.longitude]}
          icon={getMarkerIcon(item, isHovered, isSelected)}
          eventHandlers={{
            click: () => {
              if (isMobile) {
                setSelectedDisasterForSheet(item);
              }
              // Desktop: Let default Popup behavior work
            }
          }}
        >
          {!isMobile && (
            <Popup>
              <PopupContent
                item={item}
                isAdmin={isAdmin}
                currentUser={currentUser}
                onEditReport={onEditReport}
                onDeleteReport={onDeleteReport}
              />
            </Popup>
          )}
        </Marker>
      );
    });
  }, [hoveredItem, selectedItem, isMobile]);

  // Performance optimization: Memoize marker arrays to prevent recreation unless data or state changes
  // Only recalculate when groupedData changes or hover/selection state changes
  const wildfireMarkers = useMemo(
    () => createMarkers(groupedData.wildfires, 'wildfires'),
    [groupedData.wildfires, createMarkers]
  );

  const weatherAlertMarkers = useMemo(
    () => createMarkers(groupedData.weatherAlerts, 'weatherAlerts'),
    [groupedData.weatherAlerts, createMarkers]
  );

  const userReportMarkers = useMemo(
    () => createMarkers(groupedData.userReports, 'userReports'),
    [groupedData.userReports, createMarkers]
  );

  // Add global error handler for Leaflet initialization errors
  // MUST BE BEFORE ANY EARLY RETURNS (Rules of Hooks)
  useEffect(() => {
    const originalOnError = window.onerror;

    window.onerror = (msg, url, lineNo, columnNo, error) => {
      // Suppress _leaflet_pos errors (internal Leaflet timing issues during initialization)
      if (msg && typeof msg === 'string' && msg.includes('_leaflet_pos')) {
        console.debug('Suppressed Leaflet initialization error:', msg);
        return true; // Prevent error propagation
      }
      // Call original error handler for other errors
      return originalOnError ? originalOnError(msg, url, lineNo, columnNo, error) : false;
    };

    // Cleanup: restore original error handler when component unmounts
    return () => {
      window.onerror = originalOnError;
    };
  }, []); // Run once on mount

  // PERFORMANCE: Show loading skeleton instead of empty map (after all hooks)
  if (loading) {
    return <MapLoadingSkeleton />;
  }

  return (
    <div className={`map-wrapper ${isSidebarOpen ? 'sidebar-open' : ''}`}>
      <MapContainer
        center={center}
        zoom={zoom}
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom={true}
        attributionControl={false}
      >
        <TileLayerWithFallback />

        {/* Attribution control without Leaflet branding */}
        <AttributionControl position="topright" prefix="" />

        {/* Map center controller */}
        <MapCenterController center={mapCenter} />

        {/* Sidebar state handler for control positioning */}
        <SidebarStateHandler isSidebarOpen={isSidebarOpen} />

        {/* Zoom controller based on map settings */}
        <ZoomController userLocation={userLocation} mapSettings={mapSettings} />

        {/* Location picker for testing and report form */}
        {onLocationPicked && (
          <LocationPicker
            enabled={locationPickerEnabled}
            onLocationSet={onLocationPicked}
            pickedLocation={pickedLocation}
          />
        )}

        {/* Wildfire cluster group - using memoized markers */}
        {groupedData.wildfires.length > 0 && (
          <MarkerClusterGroup
            chunkedLoading
            maxClusterRadius={50}
            spiderfyOnMaxZoom={true}
            showCoverageOnHover={false}
            zoomToBoundsOnClick={true}
            removeOutsideVisibleBounds={true}
            iconCreateFunction={(cluster) => createClusterCustomIcon(cluster, 'wildfires')}
          >
            {wildfireMarkers}
          </MarkerClusterGroup>
        )}

        {/* Weather alerts cluster group - using memoized markers */}
        {groupedData.weatherAlerts.length > 0 && (
          <MarkerClusterGroup
            chunkedLoading
            maxClusterRadius={50}
            spiderfyOnMaxZoom={true}
            showCoverageOnHover={false}
            zoomToBoundsOnClick={true}
            removeOutsideVisibleBounds={true}
            iconCreateFunction={(cluster) => createClusterCustomIcon(cluster, 'weatherAlerts')}
          >
            {weatherAlertMarkers}
          </MarkerClusterGroup>
        )}

        {/* User reports cluster group - using memoized markers */}
        {groupedData.userReports.length > 0 && (
          <MarkerClusterGroup
            chunkedLoading
            maxClusterRadius={50}
            spiderfyOnMaxZoom={true}
            showCoverageOnHover={false}
            zoomToBoundsOnClick={true}
            removeOutsideVisibleBounds={true}
            iconCreateFunction={(cluster) => createClusterCustomIcon(cluster, 'userReports')}
          >
            {userReportMarkers}
          </MarkerClusterGroup>
        )}

        {/* Proximity radius circle */}
        {userLocation && showRadiusCircle && (
          <Circle
            center={[userLocation.lat, userLocation.lon]}
            radius={proximityRadius * MAP_CONSTANTS.MILES_TO_METERS} // Convert miles to meters
            pathOptions={{
              color: '#14b8a6',
              fillColor: '#14b8a6',
              fillOpacity: 0.1,
              opacity: 0.5,
              weight: 2
            }}
          />
        )}

        {/* User location marker */}
        {userLocation && (
          <Marker
            position={[userLocation.lat, userLocation.lon]}
            icon={L.divIcon({
              className: 'user-location-marker',
              html: `<div style="
                background: linear-gradient(135deg, #60a5fa 0%, #1e40af 100%);
                width: 20px;
                height: 20px;
                border-radius: 50%;
                border: 3px solid white;
                box-shadow: 0 0 10px rgba(30, 64, 175, 0.8), 0 0 20px rgba(30, 64, 175, 0.5);
                animation: pulse 2s infinite;
              "></div>
              <style>
                @keyframes pulse {
                  0%, 100% {
                    transform: scale(1);
                    opacity: 1;
                  }
                  50% {
                    transform: scale(1.2);
                    opacity: 0.8;
                  }
                }
              </style>`,
              iconSize: [20, 20],
              iconAnchor: [10, 10],
              popupAnchor: [0, -10]
            })}
          >
            <Popup>
              <div style={{ textAlign: 'center', padding: '5px' }}>
                <strong>📍 Your Location</strong>
                <br />
                {userLocation.lat && userLocation.lon && (
                  <span style={{ fontSize: '0.85em', color: '#666' }}>
                    {userLocation.lat.toFixed(4)}, {userLocation.lon.toFixed(4)}
                  </span>
                )}
              </div>
            </Popup>
          </Marker>
        )}

        {/* Route Polylines */}
        {routes && routes.length > 0 && routes.map((route, index) => {
          // Route geometry comes as [[lon, lat], ...] from backend, need to reverse to [[lat, lon], ...]
          const positions = route.geometry ? route.geometry.map(coord => [coord[1], coord[0]]) : [];
          const routeId = route.route_id || route.id || `route-${index}`;
          // Fix: Only compare route_id, not id (id is always undefined, causing all routes to match)
          const isSelected = selectedRoute && selectedRoute.route_id && route.route_id && selectedRoute.route_id === route.route_id;

          if (positions.length === 0) {
            return null;
          }

          // If a route is selected, ONLY show that route (hide alternatives)
          // Otherwise show all routes
          if (selectedRoute && !isSelected) {
            return null;
          }

          return (
            <Polyline
              key={routeId}
              positions={positions}
              pathOptions={{
                // Selected route: bright blue, thick
                // Unselected routes: muted colors, thinner, lower opacity
                color: isSelected ? '#3B82F6' : getRouteColor(route, index, false),
                weight: isSelected ? 6 : 4,
                opacity: isSelected ? 1.0 : 0.5,
                lineJoin: 'round',
                lineCap: 'round'
              }}
              eventHandlers={{
                click: () => {
                  // Optional: Add route selection handler here for future interactivity
                  console.log('Route clicked:', route);
                }
              }}
            />
          );
        })}

        {/* Safe Zone Markers */}
        {safeZones && safeZones.length > 0 && safeZones.map((zone) => {
          const isSelected = selectedSafeZone?.id === zone.id;

          // If a route is selected, only show the selected safe zone (destination)
          // Otherwise show all safe zones
          if (selectedRoute && !isSelected) {
            return null;
          }

          return (
            <Marker
              key={zone.id}
              position={[zone.location.latitude, zone.location.longitude]}
              icon={isSelected ? safeZoneIcons.selected : safeZoneIcons.unselected}
              zIndexOffset={isSelected ? 2000 : 1000}
            >
            <Popup>
              <div style={{ padding: '10px', minWidth: '250px' }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  marginBottom: '8px',
                  paddingBottom: '8px',
                  borderBottom: '2px solid #10b981'
                }}>
                  <span style={{ fontSize: '24px' }}>
                    {zone.type === 'evacuation_center' ? '🏛️' :
                     zone.type === 'hospital' ? '🏥' :
                     zone.type === 'fire_station' ? '🚒' :
                     zone.type === 'emergency_shelter' ? '⛺' : '📍'}
                  </span>
                  <strong style={{ fontSize: '16px', color: '#059669' }}>
                    Safe Zone
                  </strong>
                </div>

                <h4 style={{ margin: '0 0 8px 0', color: '#1f2937' }}>
                  {zone.name}
                </h4>

                <div style={{ fontSize: '14px', color: '#4b5563', lineHeight: '1.6' }}>
                  <p style={{ margin: '4px 0' }}>
                    <strong>Type:</strong> {zone.type.replace(/_/g, ' ')}
                  </p>
                  <p style={{ margin: '4px 0' }}>
                    <strong>Distance:</strong> {zone.distance_from_user_mi ? zone.distance_from_user_mi.toFixed(1) : 'N/A'} miles away
                  </p>
                  <p style={{ margin: '4px 0' }}>
                    <strong>Address:</strong> {zone.address}
                  </p>
                  <p style={{ margin: '4px 0' }}>
                    <strong>Capacity:</strong> {zone.capacity?.toLocaleString()} people
                  </p>
                  <p style={{ margin: '4px 0' }}>
                    <strong>Status:</strong>
                    <span style={{
                      marginLeft: '8px',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      backgroundColor: zone.operational_status === 'open' ? '#10b981' :
                                      zone.operational_status === 'closed' ? '#ef4444' :
                                      zone.operational_status === 'at_capacity' ? '#f59e0b' : '#9ca3af',
                      color: 'white',
                      fontSize: '12px',
                      fontWeight: 'bold'
                    }}>
                      {zone.operational_status?.toUpperCase()}
                    </span>
                  </p>

                  {zone.contact && zone.contact.phone && (
                    <p style={{ margin: '8px 0 4px 0', fontWeight: 'bold' }}>
                      ☎️ {zone.contact.phone}
                    </p>
                  )}
                </div>
              </div>
            </Popup>
          </Marker>
          );
        })}

      </MapContainer>

      {allDataPoints.length === 0 && (
        <div className="no-reports-overlay">
          <p>No disaster data to display</p>
          <p className="hint">Click "Report Disaster" to add a new report</p>
        </div>
      )}

      {/* Mobile bottom sheet for disaster details */}
      {isMobile && selectedDisasterForSheet && (
        <DisasterBottomSheet
          disaster={selectedDisasterForSheet}
          onClose={() => setSelectedDisasterForSheet(null)}
          isAdmin={isAdmin}
          currentUser={currentUser}
          onEditReport={onEditReport}
          onDeleteReport={onDeleteReport}
        />
      )}
    </div>
  );
}

// Performance optimization: Wrap Map component with React.memo to prevent unnecessary re-renders
// Custom comparison function checks if dataPoints array has actually changed
export default React.memo(Map, (prevProps, nextProps) => {
  // Return true if props are equal (component should NOT re-render)
  // Return false if props are different (component should re-render)

  // Check if dataPoints array length or content changed
  if (prevProps.dataPoints.length !== nextProps.dataPoints.length) {
    return false; // Re-render needed
  }

  // Check if hovered/selected items changed
  if (prevProps.hoveredItem !== nextProps.hoveredItem) {
    return false;
  }

  if (prevProps.selectedItem !== nextProps.selectedItem) {
    return false;
  }

  // Check if user location changed (shallow comparison)
  if (!shallowEqual(prevProps.userLocation, nextProps.userLocation)) {
    return false;
  }

  // Check if map center changed (shallow comparison)
  if (!shallowEqual(prevProps.mapCenter, nextProps.mapCenter)) {
    return false;
  }

  // Check if routes changed
  if (prevProps.routes?.length !== nextProps.routes?.length) {
    return false;
  }

  // Check if selected route changed
  if (prevProps.selectedRoute !== nextProps.selectedRoute) {
    return false;
  }

  // Check if safe zones changed
  if (prevProps.safeZones?.length !== nextProps.safeZones?.length) {
    return false;
  }

  // Check if proximity radius changed
  if (prevProps.proximityRadius !== nextProps.proximityRadius) {
    return false;
  }

  // Check if radius circle visibility changed
  if (prevProps.showRadiusCircle !== nextProps.showRadiusCircle) {
    return false;
  }

  // Check if location picker state changed
  if (prevProps.locationPickerEnabled !== nextProps.locationPickerEnabled) {
    return false;
  }

  // Check if map settings changed (shallow comparison)
  if (!shallowEqual(prevProps.mapSettings, nextProps.mapSettings)) {
    return false;
  }

  // Check if selected safe zone changed
  if (prevProps.selectedSafeZone?.id !== nextProps.selectedSafeZone?.id) {
    return false;
  }

  // Check if sidebar state changed (for zoom control positioning)
  if (prevProps.isSidebarOpen !== nextProps.isSidebarOpen) {
    return false;
  }

  // Check if picked location changed (for report form marker)
  if (prevProps.pickedLocation !== nextProps.pickedLocation) {
    return false;
  }

  // All relevant props are equal - skip re-render
  return true;
});
