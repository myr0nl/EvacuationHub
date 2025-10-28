import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Bell, X, Volume2, VolumeX, Settings, MapPin, Clock, MapPinned, CheckCircle } from 'lucide-react';
import { getDisasterIcon, getSourceIcon } from '../config/icons';
import './AlertNotificationPanel.css';

// ============================================================================
// PURE HELPER FUNCTIONS (moved outside component to prevent recreation on every render)
// ============================================================================

// Helper function: Get severity color
const getSeverityColor = (severity) => {
  const colors = {
    critical: '#dc2626',  // red
    high: '#f59e0b',      // orange
    medium: '#eab308',    // yellow
    low: '#6b7280'        // gray
  };
  if (!severity) return colors.low;
  return colors[severity.toLowerCase()] || colors.low;
};

// Helper function: Format distance
const formatDistance = (mi) => {
  if (mi === undefined || mi === null) return 'Distance unknown';
  if (mi < 0.1) return `${Math.round(mi * 5280)} ft away`;
  return `${mi.toFixed(1)} mi away`;
};

// Helper function: Format time ago
const formatTimeAgo = (timestamp) => {
  try {
    const now = new Date();
    const then = new Date(timestamp);
    const diffMs = now - then;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  } catch (error) {
    console.error('Error formatting timestamp:', error);
    return 'Unknown time';
  }
};

// Helper function: Get highest severity level
const getHighestSeverity = (alerts) => {
  const severityOrder = ['critical', 'high', 'medium', 'low'];
  for (const severity of severityOrder) {
    if (alerts.some(a => a.severity && a.severity.toLowerCase() === severity)) {
      return severity;
    }
  }
  return 'low';
};

// Helper function: Sort alerts by distance
const sortAlertsByDistance = (alerts) => {
  return [...alerts].sort((a, b) => a.distance_mi - b.distance_mi);
};

// Helper function: Group alerts by severity
const groupAlertsBySeverity = (alerts) => {
  const severityOrder = ['critical', 'high', 'medium', 'low'];
  const grouped = {};

  severityOrder.forEach(severity => {
    grouped[severity] = alerts.filter(
      a => a.severity && a.severity.toLowerCase() === severity
    ).sort((a, b) => a.distance_mi - b.distance_mi);
  });

  return grouped;
};

// ============================================================================
// COMPONENT
// ============================================================================

const AlertNotificationPanel = ({
  alerts = [],
  onViewOnMap,
  onDismiss,
  onOpenSettings,
  userLocation
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isMuted, setIsMuted] = useState(() => {
    // Persist mute state in localStorage
    return localStorage.getItem('alertsMuted') === 'true';
  });
  const [dismissedAlertIds, setDismissedAlertIds] = useState(new Set());
  const audioContextRef = useRef(null);
  const previousAlertCount = useRef(0);

  // ============================================================================
  // MEMOIZED COMPUTED VALUES (prevent recalculation on every render)
  // ============================================================================

  // Memoize activeAlerts - only recalculate when alerts or dismissedAlertIds change
  const activeAlerts = useMemo(() => {
    return alerts.filter(alert => !dismissedAlertIds.has(alert.id));
  }, [alerts, dismissedAlertIds]);

  // Memoize highestSeverity - only recalculate when activeAlerts change
  const highestSeverity = useMemo(() => {
    return getHighestSeverity(activeAlerts);
  }, [activeAlerts]);

  // Memoize groupedAlerts - only recalculate when activeAlerts change
  const groupedAlerts = useMemo(() => {
    return groupAlertsBySeverity(activeAlerts);
  }, [activeAlerts]);

  // ============================================================================
  // MEMOIZED EVENT HANDLERS (prevent recreation on every render)
  // ============================================================================

  // Play alert sound using Web Audio API (no dependencies - stable reference)
  const playAlertSound = useCallback(() => {
    try {
      // Reuse existing AudioContext or create new one
      if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      }

      const audioContext = audioContextRef.current;
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      oscillator.frequency.value = 800; // Frequency in Hz
      oscillator.type = 'sine';

      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);

      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.5);
    } catch (error) {
      console.error('Error playing alert sound:', error);
    }
  }, []); // No dependencies - function is stable

  // Handle mute toggle (depends on isMuted state)
  const handleMuteToggle = useCallback(() => {
    const newMutedState = !isMuted;
    setIsMuted(newMutedState);
    localStorage.setItem('alertsMuted', newMutedState.toString());
  }, [isMuted]);

  // Handle dismiss individual alert (depends on onDismiss prop)
  const handleDismiss = useCallback((alertId, event) => {
    event.stopPropagation(); // Prevent triggering other click handlers
    setDismissedAlertIds(prev => new Set([...prev, alertId]));
    if (onDismiss) {
      onDismiss(alertId);
    }
  }, [onDismiss]);

  // Handle dismiss all alerts (depends on activeAlerts for mapping IDs)
  const handleDismissAll = useCallback(() => {
    setDismissedAlertIds(prev => new Set([...prev, ...activeAlerts.map(a => a.id)]));
  }, [activeAlerts]);

  // Handle view on map (depends on onViewOnMap prop)
  const handleViewOnMap = useCallback((alert, event) => {
    event.stopPropagation();
    if (onViewOnMap) {
      onViewOnMap(alert);
    }
    setIsExpanded(false); // Collapse panel after viewing
  }, [onViewOnMap]);

  // Handle settings click (depends on onOpenSettings prop)
  const handleSettingsClick = useCallback((event) => {
    event.stopPropagation();
    if (onOpenSettings) {
      onOpenSettings();
    }
  }, [onOpenSettings]);

  // Toggle panel expansion (no dependencies - uses updater function)
  const toggleExpanded = useCallback(() => {
    setIsExpanded(prev => !prev);
  }, []);

  // ============================================================================
  // EFFECTS
  // ============================================================================

  // Play sound for critical alerts
  useEffect(() => {
    if (isMuted || activeAlerts.length === 0) return;

    const criticalAlerts = activeAlerts.filter(
      a => a.severity && (a.severity.toLowerCase() === 'critical' || a.severity.toLowerCase() === 'high')
    );

    // Play sound only when new critical/high alerts appear
    if (criticalAlerts.length > 0 && activeAlerts.length > previousAlertCount.current) {
      playAlertSound();
    }

    previousAlertCount.current = activeAlerts.length;
  }, [activeAlerts.length, isMuted, playAlertSound]);

  // Cleanup AudioContext on unmount
  useEffect(() => {
    return () => {
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close();
      }
    };
  }, []);

  // ============================================================================
  // RENDER HELPERS
  // ============================================================================

  // Determine if badge should flash based on severity
  const shouldFlash = ['critical', 'high'].includes(highestSeverity);

  return (
    <div className="alert-notification-panel">
      {/* Bell Icon with Badge */}
      <div
        className="alert-icon-container"
        onClick={toggleExpanded}
        role="button"
        tabIndex={0}
        aria-label={`${activeAlerts.length} active alerts. Click to ${isExpanded ? 'collapse' : 'expand'} alert panel`}
        onKeyPress={(e) => e.key === 'Enter' && toggleExpanded()}
      >
        <div className="bell-icon">
          <Bell size={24} strokeWidth={2} />
        </div>
        {activeAlerts.length > 0 && (
          <div
            className={`alert-badge ${shouldFlash ? 'flashing' : ''}`}
            style={{ backgroundColor: getSeverityColor(highestSeverity) }}
          >
            {activeAlerts.length}
          </div>
        )}
      </div>

      {/* Expanded Panel */}
      {isExpanded && (
        <div className="alert-panel-expanded">
          {/* Header */}
          <div className="alert-panel-header">
            <h3 className="alert-panel-title">
              Active Alerts {activeAlerts.length > 0 && `(${activeAlerts.length})`}
            </h3>
            <div className="alert-panel-controls">
              {/* Mute/Unmute Button */}
              <button
                className="control-button"
                onClick={handleMuteToggle}
                aria-label={isMuted ? 'Unmute alerts' : 'Mute alerts'}
                title={isMuted ? 'Unmute alerts' : 'Mute alerts'}
              >
                {isMuted ? <VolumeX size={18} strokeWidth={2} /> : <Volume2 size={18} strokeWidth={2} />}
              </button>

              {/* Settings Button */}
              <button
                className="control-button"
                onClick={handleSettingsClick}
                aria-label="Open settings"
                title="Alert settings"
              >
                <Settings size={18} strokeWidth={2} />
              </button>

              {/* Collapse Button */}
              <button
                className="control-button"
                onClick={toggleExpanded}
                aria-label="Collapse panel"
                title="Collapse"
              >
                <X size={18} strokeWidth={2} />
              </button>
            </div>
          </div>

          {/* Alert List */}
          <div className="alert-list">
            {activeAlerts.length === 0 ? (
              // Empty State
              <div className="alert-empty-state">
                <div className="empty-state-icon">
                  <CheckCircle size={48} strokeWidth={2} color="#10b981" />
                </div>
                <p className="empty-state-message">No active alerts nearby</p>
                <p className="empty-state-submessage">You'll be notified of disasters in your area</p>
              </div>
            ) : (
              <>
                {/* Dismiss All Button */}
                {activeAlerts.length > 1 && (
                  <button
                    className="dismiss-all-button"
                    onClick={handleDismissAll}
                    aria-label="Dismiss all alerts"
                  >
                    Dismiss All
                  </button>
                )}

                {/* Alert Cards Grouped by Severity */}
                {['critical', 'high', 'medium', 'low'].map(severity => (
                  groupedAlerts[severity].length > 0 && (
                    <div key={severity} className="alert-severity-group">
                      <div className="severity-group-header">
                        <span
                          className="severity-badge"
                          style={{ backgroundColor: getSeverityColor(severity) }}
                        >
                          {severity.toUpperCase()}
                        </span>
                      </div>
                      {groupedAlerts[severity].map(alert => {
                        const DisasterIcon = getDisasterIcon(alert.disaster_type || alert.type);
                        return (
                        <div
                          key={alert.id}
                          className="alert-card"
                          style={{ borderLeftColor: getSeverityColor(alert.severity) }}
                        >
                          {/* Alert Header */}
                          <div className="alert-card-header">
                            <div className="alert-type-info">
                              <span className="disaster-icon">
                                <DisasterIcon size={20} strokeWidth={2} />
                              </span>
                              <span className="disaster-type-name">
                                {(alert.disaster_type || alert.type || 'Alert').charAt(0).toUpperCase() + (alert.disaster_type || alert.type || 'Alert').slice(1)}
                              </span>
                            </div>
                            <button
                              className="dismiss-button"
                              onClick={(e) => handleDismiss(alert.id, e)}
                              aria-label="Dismiss alert"
                              title="Dismiss"
                            >
                              <X size={16} strokeWidth={2} />
                            </button>
                          </div>

                          {/* Alert Details */}
                          <div className="alert-card-details">
                            <div className="detail-row">
                              <span className="detail-icon">
                                <MapPin size={16} strokeWidth={2} />
                              </span>
                              <span className="detail-text">
                                {formatDistance(alert.distance_mi)}
                              </span>
                            </div>
                            <div className="detail-row">
                              <span className="detail-icon">
                                <MapPinned size={16} strokeWidth={2} />
                              </span>
                              <span className="detail-text">
                                {alert.location_name || `${alert.latitude.toFixed(4)}, ${alert.longitude.toFixed(4)}`}
                              </span>
                            </div>
                            <div className="detail-row">
                              <span className="detail-icon">
                                <Clock size={16} strokeWidth={2} />
                              </span>
                              <span className="detail-text">
                                {formatTimeAgo(alert.timestamp)}
                              </span>
                            </div>
                            {alert.source && (() => {
                              const SourceIcon = getSourceIcon(alert.source);
                              const sourceLabels = {
                                'nasa_firms': 'NASA FIRMS',
                                'noaa_weather': 'NOAA',
                                'user_report': 'User Report',
                                'fema': 'FEMA',
                                'usgs': 'USGS',
                                'gdacs': 'GDACS',
                                'cal_fire': 'Cal Fire',
                                'cal_oes': 'Cal OES'
                              };
                              const sourceLabel = sourceLabels[alert.source] || alert.source;

                              return (
                                <div className="detail-row">
                                  <span className="source-badge">
                                    <SourceIcon size={14} strokeWidth={2} />
                                    <span>{sourceLabel}</span>
                                  </span>
                                </div>
                              );
                            })()}
                          </div>

                          {/* View on Map Button */}
                          <button
                            className="view-map-button"
                            onClick={(e) => handleViewOnMap(alert, e)}
                            aria-label={`View ${alert.disaster_type || alert.type || 'alert'} on map`}
                          >
                            <MapPin size={16} strokeWidth={2} />
                            <span>View on Map</span>
                          </button>
                        </div>
                        );
                      })}
                    </div>
                  )
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// PERFORMANCE OPTIMIZATION: Memoize component to prevent unnecessary re-renders
// ============================================================================

// Custom comparison function for React.memo - only re-render if these props actually change
const arePropsEqual = (prevProps, nextProps) => {
  // Compare alerts array by reference and length (deep equality check would be expensive)
  const alertsEqual = prevProps.alerts === nextProps.alerts ||
    (prevProps.alerts.length === nextProps.alerts.length &&
     prevProps.alerts.every((alert, idx) => alert === nextProps.alerts[idx]));

  // Compare callback functions by reference
  const callbacksEqual =
    prevProps.onViewOnMap === nextProps.onViewOnMap &&
    prevProps.onDismiss === nextProps.onDismiss &&
    prevProps.onOpenSettings === nextProps.onOpenSettings;

  // Compare userLocation by reference (if it changes frequently, consider deep equality)
  const locationEqual = prevProps.userLocation === nextProps.userLocation;

  // Return true if all props are equal (prevents re-render)
  return alertsEqual && callbacksEqual && locationEqual;
};

// Export memoized component for optimal performance
export default React.memo(AlertNotificationPanel, arePropsEqual);
