import React, { useState, useEffect } from 'react';
import { Circle, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import './ProximityRangeControl.css';

/**
 * ProximityRangeControl - Displays a proximity radius circle on the map centered at user location
 *
 * Features:
 * - Visual proximity circle with color-coded severity alerts
 * - Adjustable radius slider (5-50 miles)
 * - Alert count and severity breakdown display
 * - Pulsing user location marker
 * - Collapsible control panel
 *
 * @param {Object} userLocation - User's current position {lat, lon}
 * @param {Number} radius - Current radius in miles (5-50)
 * @param {Function} onRadiusChange - Callback when radius changes: (newRadius) => {}
 * @param {Array} alerts - Array of alerts within the proximity range
 * @param {Boolean} visible - Show/hide the proximity circle
 */
const ProximityRangeControl = ({
  userLocation,
  radius = 25,
  onRadiusChange,
  alerts = [],
  visible = true
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [showCircle, setShowCircle] = useState(visible);
  const panelRef = React.useRef(null);

  // Custom user location icon with pulsing animation
  const userLocationIcon = L.divIcon({
    className: 'user-location-marker',
    html: `
      <div class="user-location-pulse">
        <div class="user-location-dot"></div>
      </div>
    `,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -15]
  });

  /**
   * Determines circle color based on highest severity alert within range
   * Priority: critical > high > medium > low > safe (green)
   */
  const getCircleColor = (alerts) => {
    if (!alerts || alerts.length === 0) return '#10b981'; // green (safe)

    const severities = alerts.map(a => a.severity?.toLowerCase());
    if (severities.includes('critical')) return '#dc2626'; // red
    if (severities.includes('high')) return '#f59e0b'; // orange
    if (severities.includes('medium')) return '#eab308'; // yellow
    return '#10b981'; // green (low or safe)
  };

  /**
   * Calculates breakdown of alerts by severity level
   */
  const getSeverityBreakdown = (alerts) => {
    if (!alerts || alerts.length === 0) {
      return { critical: 0, high: 0, medium: 0, low: 0 };
    }

    return {
      critical: alerts.filter(a => a.severity?.toLowerCase() === 'critical').length,
      high: alerts.filter(a => a.severity?.toLowerCase() === 'high').length,
      medium: alerts.filter(a => a.severity?.toLowerCase() === 'medium').length,
      low: alerts.filter(a => a.severity?.toLowerCase() === 'low').length
    };
  };

  // Persist radius to localStorage
  useEffect(() => {
    if (radius) {
      localStorage.setItem('proximityRadius', radius.toString());
    }
  }, [radius]);

  // Sync showCircle with visible prop
  useEffect(() => {
    setShowCircle(visible);
  }, [visible]);

  // Disable Leaflet map events on the panel to prevent click-through
  useEffect(() => {
    if (panelRef.current) {
      // Disable all map interactions on the panel
      L.DomEvent.disableClickPropagation(panelRef.current);
      L.DomEvent.disableScrollPropagation(panelRef.current);
    }
  }, []);

  // Handle radius change from slider
  const handleRadiusChange = (e) => {
    const newRadius = parseInt(e.target.value, 10);
    if (onRadiusChange) {
      onRadiusChange(newRadius);
    }
  };

  // Toggle circle visibility
  const toggleCircleVisibility = () => {
    setShowCircle(!showCircle);
  };

  // Toggle panel expansion
  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  // Prevent click events from propagating to the map
  const handlePanelClick = (e) => {
    e.stopPropagation();
  };

  const handlePanelMouseDown = (e) => {
    e.stopPropagation();
  };

  // Return null if no user location
  if (!userLocation || !userLocation.lat || !userLocation.lon) {
    return null;
  }

  const position = [userLocation.lat, userLocation.lon];
  const radiusInMeters = radius * 1609.34; // Convert miles to meters
  const circleColor = getCircleColor(alerts);
  const breakdown = getSeverityBreakdown(alerts);
  const totalAlerts = alerts.length;

  return (
    <>
      {/* User Location Marker */}
      <Marker position={position} icon={userLocationIcon}>
        <Popup>
          <div className="user-location-popup">
            <strong>📍 Your Location</strong>
            <p className="coordinates">
              {userLocation.lat.toFixed(6)}, {userLocation.lon.toFixed(6)}
            </p>
          </div>
        </Popup>
      </Marker>

      {/* Proximity Circle */}
      {showCircle && (
        <Circle
          center={position}
          radius={radiusInMeters}
          pathOptions={{
            color: circleColor,
            fillColor: circleColor,
            fillOpacity: 0.1,
            opacity: 0.5,
            weight: 2
          }}
        />
      )}

      {/* Range Control Panel */}
      <div
        ref={panelRef}
        className={`proximity-range-control ${!isExpanded ? 'collapsed' : ''}`}
        onClick={handlePanelClick}
        onMouseDown={handlePanelMouseDown}
        onDoubleClick={handlePanelClick}
      >
        {/* Header with toggle buttons */}
        <div className="control-header">
          <h3 className="control-title">
            {isExpanded ? '🎯 Proximity Range' : '🎯'}
          </h3>
          <div className="control-buttons">
            <button
              className="icon-button"
              onClick={toggleCircleVisibility}
              title={showCircle ? 'Hide circle' : 'Show circle'}
              aria-label={showCircle ? 'Hide proximity circle' : 'Show proximity circle'}
            >
              {showCircle ? '👁️' : '👁️‍🗨️'}
            </button>
            <button
              className="icon-button"
              onClick={toggleExpanded}
              title={isExpanded ? 'Collapse' : 'Expand'}
              aria-label={isExpanded ? 'Collapse panel' : 'Expand panel'}
            >
              {isExpanded ? '▼' : '▶'}
            </button>
          </div>
        </div>

        {/* Expanded content */}
        {isExpanded && (
          <div className="control-content">
            {/* Radius display */}
            <div className="radius-display">
              <span className="radius-label">Radius:</span>
              <span className="radius-value">{radius} mi</span>
            </div>

            {/* Radius slider */}
            <input
              type="range"
              className="range-slider"
              min="5"
              max="50"
              step="5"
              value={radius}
              onChange={handleRadiusChange}
              aria-label="Proximity radius in miles"
            />
            <div className="range-labels">
              <span>5 mi</span>
              <span>50 mi</span>
            </div>

            {/* Alert count */}
            <div className="alert-count">
              <span className="alert-count-number">{totalAlerts}</span>
              <span className="alert-count-label">
                {totalAlerts === 1 ? 'alert found' : 'alerts found'}
              </span>
            </div>

            {/* Severity breakdown */}
            {totalAlerts > 0 && (
              <div className="severity-breakdown">
                {breakdown.critical > 0 && (
                  <span className="severity-badge critical">
                    Critical: {breakdown.critical}
                  </span>
                )}
                {breakdown.high > 0 && (
                  <span className="severity-badge high">
                    High: {breakdown.high}
                  </span>
                )}
                {breakdown.medium > 0 && (
                  <span className="severity-badge medium">
                    Medium: {breakdown.medium}
                  </span>
                )}
                {breakdown.low > 0 && (
                  <span className="severity-badge low">
                    Low: {breakdown.low}
                  </span>
                )}
              </div>
            )}

            {/* Safe zone indicator */}
            {totalAlerts === 0 && (
              <div className="safe-zone">
                <span className="safe-icon">✓</span>
                <span className="safe-text">No alerts in this area</span>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
};

export default ProximityRangeControl;
