import React, { useState } from 'react';
import PropTypes from 'prop-types';
import './NavigationInstructions.css';

/**
 * NavigationInstructions - Display turn-by-turn navigation directions for a route
 *
 * Shows detailed step-by-step instructions retrieved from ORS/HERE routing APIs
 * with expandable/collapsible UI for better space management.
 *
 * @param {Array} waypoints - Array of waypoint objects with instructions
 * @param {boolean} isExpanded - Initial expanded state (default: false)
 */
const NavigationInstructions = ({ waypoints = [], isExpanded = false }) => {
  const [expanded, setExpanded] = useState(isExpanded);

  // Return null if no waypoints provided
  if (!waypoints || waypoints.length === 0) {
    return null;
  }

  /**
   * Get icon for instruction type
   * Maps ORS/HERE instruction types to intuitive navigation icons
   */
  const getInstructionIcon = (type, instruction = '') => {
    const lowerType = (type || '').toLowerCase();
    const lowerInstruction = (instruction || '').toLowerCase();

    // Departure
    if (lowerType === 'depart' || lowerInstruction.includes('depart') || lowerInstruction.includes('start')) {
      return '🚗';
    }
    // Arrival
    if (lowerType === 'arrive' || lowerInstruction.includes('arrive') || lowerInstruction.includes('destination')) {
      return '🏁';
    }
    // Turns
    if (lowerInstruction.includes('turn left') || lowerInstruction.includes('left onto')) {
      return '↰';
    }
    if (lowerInstruction.includes('turn right') || lowerInstruction.includes('right onto')) {
      return '↱';
    }
    if (lowerInstruction.includes('u-turn') || lowerInstruction.includes('uturn')) {
      return '↶';
    }
    // Straight/Continue
    if (lowerInstruction.includes('continue') || lowerInstruction.includes('straight') || lowerInstruction.includes('keep')) {
      return '↑';
    }
    // Roundabout
    if (lowerInstruction.includes('roundabout') || lowerInstruction.includes('circle')) {
      return '⟳';
    }
    // Merge/Ramp
    if (lowerInstruction.includes('merge') || lowerInstruction.includes('ramp') || lowerInstruction.includes('exit')) {
      return '↗';
    }
    // Default
    return '→';
  };

  /**
   * Format distance for display
   * Shows feet for short distances, miles for longer ones
   */
  const formatDistance = (distanceMi) => {
    if (!distanceMi || distanceMi === 0) return '';

    if (distanceMi < 0.1) {
      // Show feet for very short distances
      const feet = Math.round(distanceMi * 5280);
      return `${feet} ft`;
    }

    return `${distanceMi.toFixed(1)} mi`;
  };

  /**
   * Format duration for display
   */
  const formatDuration = (seconds) => {
    if (!seconds || seconds === 0) return '';

    if (seconds < 60) {
      return `${seconds}s`;
    }

    const minutes = Math.floor(seconds / 60);
    return `${minutes} min`;
  };

  /**
   * Calculate total statistics
   */
  const totalDistance = waypoints.reduce((sum, wp) => sum + (wp.distance_mi || 0), 0);
  const totalDuration = waypoints.reduce((sum, wp) => sum + (wp.duration_seconds || 0), 0);

  return (
    <div className="navigation-instructions">
      {/* Header with expand/collapse toggle */}
      <div className="instructions-header" onClick={() => setExpanded(!expanded)}>
        <div className="instructions-title">
          <span className="instructions-icon">🧭</span>
          <h4>Turn-by-Turn Directions</h4>
          <span className="instructions-count">({waypoints.length} steps)</span>
        </div>
        <button
          className="toggle-button"
          aria-label={expanded ? 'Collapse instructions' : 'Expand instructions'}
          aria-expanded={expanded}
        >
          {expanded ? '▼' : '▶'}
        </button>
      </div>

      {/* Summary stats */}
      {expanded && (
        <div className="instructions-summary">
          <span className="summary-item">
            📍 {totalDistance.toFixed(1)} mi
          </span>
          <span className="summary-item">
            🕐 {Math.floor(totalDuration / 60)} min
          </span>
        </div>
      )}

      {/* Instruction list */}
      {expanded && (
        <div className="instructions-list">
          {waypoints.map((waypoint, index) => (
            <div key={index} className="instruction-item">
              <div className="instruction-step-number">{index + 1}</div>
              <div className="instruction-icon">
                {getInstructionIcon(waypoint.type, waypoint.instruction)}
              </div>
              <div className="instruction-content">
                <div className="instruction-text">
                  {waypoint.instruction || 'Continue on route'}
                </div>
                {(waypoint.distance_mi > 0 || waypoint.duration_seconds > 0) && (
                  <div className="instruction-details">
                    {waypoint.distance_mi > 0 && (
                      <span className="detail-distance">
                        {formatDistance(waypoint.distance_mi)}
                      </span>
                    )}
                    {waypoint.duration_seconds > 0 && (
                      <span className="detail-duration">
                        {formatDuration(waypoint.duration_seconds)}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

NavigationInstructions.propTypes = {
  waypoints: PropTypes.arrayOf(
    PropTypes.shape({
      instruction: PropTypes.string,
      distance_mi: PropTypes.number,
      duration_seconds: PropTypes.number,
      type: PropTypes.string
    })
  ),
  isExpanded: PropTypes.bool
};

export default NavigationInstructions;
