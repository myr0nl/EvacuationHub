import React from 'react';
import PropTypes from 'prop-types';
import './RouteComparisonCard.css';
import NavigationInstructions from './NavigationInstructions';
import { UI_ICONS } from '../config/icons';

/**
 * RouteComparisonCard - Displays a single route option with safety metrics and details
 *
 * @param {Object} route - Route data object
 * @param {number} index - Route number (0-based)
 * @param {Function} onSelect - Callback when route is selected
 * @param {boolean} isSelected - Whether this route is currently selected
 */
const RouteComparisonCard = ({ route, index, onSelect, isSelected = false }) => {
  /**
   * Get the color for the route polyline on the map.
   * This matches the getRouteColor function in Map.js to ensure visual consistency.
   *
   * @param {number} index - Route index (0-based)
   * @param {boolean} isSelected - Whether the route is currently selected
   * @returns {string} Hex color code for the route
   */
  const getRouteColor = (index, isSelected) => {
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

  // Helper: Format duration from seconds to human-readable format
  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes} min`;
  };

  // Helper: Format ISO timestamp to local time
  const formatTime = (isoString) => {
    if (!isoString) return 'N/A';

    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
      });
    } catch (error) {
      return 'N/A';
    }
  };

  // Helper: Get color for safety score
  const getSafetyColor = (score) => {
    if (score >= 80) return 'green';
    if (score >= 60) return 'orange';
    return 'red';
  };

  // Extract route properties with defaults
  const {
    // route_id is defined in PropTypes but not used in render
    distance_mi = 0,
    duration_seconds = 0,
    safety_score = 0,
    heatmap_score = 5, // Default to 5 for Phase 2
    intersects_disasters = [],
    estimated_arrival,
    disasters_nearby = 0,
    min_disaster_distance_mi,
    is_fastest = false,
    is_safest = false,
    waypoints = []  // Turn-by-turn navigation instructions
    // Note: warning prop is displayed at panel level, not on individual cards
  } = route;

  const routeNumber = index + 1;
  const safetyColor = getSafetyColor(safety_score);
  const hasWarning = intersects_disasters && intersects_disasters.length > 0;
  const routeColor = getRouteColor(index, isSelected);

  // Icon components
  const FastestIcon = UI_ICONS.fastest;
  const SafestIcon = UI_ICONS.safest;
  const ClockIcon = UI_ICONS.clock;
  const DistanceIcon = UI_ICONS.distance;
  const WarningIcon = UI_ICONS.warning;
  const CheckIcon = UI_ICONS.check;

  // Helper: Get color name for tooltip
  const getColorName = (index) => {
    const colorNames = ['green', 'red', 'purple', 'orange', 'cyan', 'pink'];
    return colorNames[index % colorNames.length];
  };

  return (
    <div
      className={`route-comparison-card ${is_fastest ? 'fastest' : ''} ${is_safest ? 'safest' : ''} ${isSelected ? 'selected' : ''}`}
      role="article"
      aria-label={`Route ${routeNumber} option`}
    >
      {/* Header */}
      <div className="route-header">
        <div className="route-title-container">
          <div
            className="route-color-indicator"
            style={{ backgroundColor: routeColor }}
            title={`Route ${routeNumber} is displayed in ${isSelected ? 'blue' : getColorName(index)} on the map`}
            aria-label={`Route color indicator`}
          />
          <h3 className="route-title">Route {routeNumber}</h3>
        </div>
        <div className="route-badges">
          {is_fastest && (
            <span className="badge badge-fastest" aria-label="Fastest route" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <FastestIcon size={16} strokeWidth={2} />
              <span>Fastest</span>
            </span>
          )}
          {is_safest && (
            <span className="badge badge-safest" aria-label="Safest route" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <SafestIcon size={16} strokeWidth={2} />
              <span>Safest</span>
            </span>
          )}
        </div>
      </div>

      {/* Key Metrics Grid */}
      <div className="metrics-grid">
        <div className="metric">
          <div className="metric-icon" aria-hidden="true">
            <ClockIcon size={24} strokeWidth={2} />
          </div>
          <div className="metric-label">Duration</div>
          <div className="metric-value">{formatDuration(duration_seconds)}</div>
        </div>

        <div className="metric">
          <div className="metric-icon" aria-hidden="true">
            <DistanceIcon size={24} strokeWidth={2} />
          </div>
          <div className="metric-label">Distance</div>
          <div className="metric-value">{distance_mi.toFixed(1)} mi</div>
        </div>

        <div className="metric">
          <div className="metric-icon" aria-hidden="true">
            <SafestIcon size={24} strokeWidth={2} />
          </div>
          <div className="metric-label">Safety</div>
          <div className="metric-value">{safety_score}/100</div>
        </div>
      </div>

      {/* Safety Details */}
      <div className="safety-details">
        <div className="safety-header">
          <span className="safety-label">Safety Score</span>
          <span className="safety-score-text">{safety_score}/100</span>
        </div>

        {/* Safety Progress Bar */}
        <div
          className="progress-bar-container"
          role="progressbar"
          aria-valuenow={safety_score}
          aria-valuemin="0"
          aria-valuemax="100"
          aria-label={`Safety score ${safety_score} out of 100`}
        >
          <div
            className={`progress-bar progress-bar-${safetyColor}`}
            style={{ width: `${safety_score}%` }}
          />
        </div>

        {/* Warning Messages */}
        {hasWarning && (
          <div className="warning-message" role="alert" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <WarningIcon size={18} strokeWidth={2} />
            <span>Passes near {intersects_disasters.length} disaster(s)</span>
          </div>
        )}

        {/* Always show disaster count if there are any nearby disasters */}
        {disasters_nearby > 0 && (
          <div className={hasWarning ? "warning-message" : "info-message"}>
            {disasters_nearby} disaster{disasters_nearby !== 1 ? 's' : ''} within 10 mi
          </div>
        )}

        {/* Always show closest disaster distance if available */}
        {min_disaster_distance_mi !== undefined && min_disaster_distance_mi !== null && (
          <div className="distance-info">
            Closest disaster: {min_disaster_distance_mi.toFixed(1)} mi away
          </div>
        )}
      </div>

      {/* ETA Display */}
      {estimated_arrival && (
        <div className="eta-display">
          <span className="eta-label">Estimated Arrival:</span>
          <span className="eta-time">{formatTime(estimated_arrival)}</span>
        </div>
      )}

      {/* Heatmap Indicator */}
      <div className="heatmap-section">
        <div className="heatmap-header">
          <span className="heatmap-label">Route Popularity</span>
          <span className="heatmap-score-text">{heatmap_score.toFixed(1)}/10</span>
        </div>

        {/* Heatmap Progress Bar */}
        <div
          className="progress-bar-container"
          role="progressbar"
          aria-valuenow={heatmap_score}
          aria-valuemin="0"
          aria-valuemax="10"
          aria-label={`Popularity score ${heatmap_score.toFixed(1)} out of 10`}
        >
          <div
            className="progress-bar progress-bar-heatmap"
            style={{ width: `${(heatmap_score / 10) * 100}%` }}
          />
        </div>
      </div>

      {/* Turn-by-Turn Navigation Instructions */}
      <NavigationInstructions waypoints={waypoints} isExpanded={false} />

      {/* Select Button */}
      <button
        className={`select-button ${isSelected ? 'selected' : ''}`}
        onClick={() => onSelect(route)}
        aria-label={`${isSelected ? 'Selected' : 'Select'} route ${routeNumber}`}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
      >
        {isSelected ? (
          <>
            <CheckIcon size={18} strokeWidth={2} />
            <span>Selected</span>
          </>
        ) : (
          <>
            <span>Select This Route</span>
            <UI_ICONS.arrowRight size={18} strokeWidth={2} />
          </>
        )}
      </button>
    </div>
  );
};

RouteComparisonCard.propTypes = {
  route: PropTypes.shape({
    route_id: PropTypes.string.isRequired,
    distance_mi: PropTypes.number.isRequired,
    duration_seconds: PropTypes.number.isRequired,
    safety_score: PropTypes.number.isRequired,
    heatmap_score: PropTypes.number,
    intersects_disasters: PropTypes.array,
    estimated_arrival: PropTypes.string,
    disasters_nearby: PropTypes.number,
    min_disaster_distance_mi: PropTypes.number,
    is_fastest: PropTypes.bool,
    is_safest: PropTypes.bool,
    waypoints: PropTypes.arrayOf(
      PropTypes.shape({
        instruction: PropTypes.string,
        distance_mi: PropTypes.number,
        duration_seconds: PropTypes.number,
        type: PropTypes.string
      })
    ),
    warning: PropTypes.string  // Optional warning message from backend
  }).isRequired,
  index: PropTypes.number.isRequired,
  onSelect: PropTypes.func.isRequired
};

export default RouteComparisonCard;
