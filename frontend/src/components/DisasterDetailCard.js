import React, { useState, useMemo } from 'react';
import { getDisasterIcon, getSourceIcon } from '../config/icons';
import { Star, Award, CheckCircle, Circle, AlertTriangle, XCircle } from 'lucide-react';
import './DisasterDetailCard.css';

const DisasterDetailCard = ({
  disaster,
  onGetRoute,
  onMarkAddressed,
  onShare,
  currentUser
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showFullDescription, setShowFullDescription] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [imageLoading, setImageLoading] = useState(true);

  // Get disaster icon component from centralized config
  const DisasterIconComponent = getDisasterIcon(disaster.disaster_type || disaster.type || 'other');

  // Get disaster type color (consistent with Map.js)
  const getDisasterColor = (type) => {
    const colors = {
      earthquake: '#e74c3c',
      flood: '#3498db',
      fire: '#e67e22',
      wildfire: '#e67e22',
      storm: '#9b59b6',
      hurricane: '#9b59b6',
      tornado: '#9b59b6',
      landslide: '#95a5a6',
      tsunami: '#1abc9c',
      volcano: '#e74c3c',
      drought: '#d68910',
      other: '#34495e'
    };
    if (!type) return colors.other;
    return colors[type.toLowerCase()] || colors.other;
  };

  // Get severity badge styling
  const getSeverityBadge = (severity) => {
    const badges = {
      low: { text: 'Low', color: '#27ae60', bg: '#d5f4e6' },
      medium: { text: 'Medium', color: '#f39c12', bg: '#fef5e7' },
      high: { text: 'High', color: '#e74c3c', bg: '#fadbd8' },
      critical: { text: 'Critical', color: '#c0392b', bg: '#f5b7b1' },
      extreme: { text: 'Extreme', color: '#8B0000', bg: '#f1948a' },
      severe: { text: 'Severe', color: '#FF0000', bg: '#f5b7b1' },
      moderate: { text: 'Moderate', color: '#FFA500', bg: '#fef5e7' },
      minor: { text: 'Minor', color: '#FFD700', bg: '#fcf3cf' }
    };
    return badges[severity?.toLowerCase()] || badges.low;
  };

  // Get confidence badge
  const getConfidenceBadge = (level, score) => {
    const badges = {
      'High': { color: '#27ae60', bg: '#d5f4e6', icon: '✓' },
      'Medium': { color: '#f39c12', bg: '#fef5e7', icon: '~' },
      'Low': { color: '#e74c3c', bg: '#fadbd8', icon: '!' }
    };
    const badge = badges[level] || badges.Low;
    const percentage = score !== undefined ? Math.round(score * 100) : 0;
    return { ...badge, percentage };
  };

  // Get time decay info from backend-calculated values
  const getTimeDecayInfo = () => {
    // Use backend-calculated time_decay if available (preferred for consistency)
    if (disaster.time_decay) {
      const { age_category, decay_score, age_hours } = disaster.time_decay;

      // Map backend categories to display info
      const categoryMap = {
        'fresh': { label: 'Fresh', color: '#27ae60', icon: '✓' },
        'recent': { label: 'Recent', color: '#f39c12', icon: '~' },
        'old': { label: 'Old', color: '#e67e22', icon: '⚠' },
        'stale': { label: 'Stale', color: '#e74c3c', icon: '!' },
        'very_stale': { label: 'Very Stale', color: '#8B0000', icon: '✗' },
        'unknown': { label: 'Unknown', color: '#95a5a6', icon: '?' }
      };

      const info = categoryMap[age_category] || categoryMap['unknown'];
      return {
        ...info,
        opacity: decay_score || 0.5,  // Use backend decay_score for opacity
        hours: age_hours
      };
    }

    // Fallback: calculate client-side if time_decay not available
    const timestamp = disaster.timestamp || disaster.reported_at || disaster.acquisition_date;
    if (!timestamp) return { label: 'Unknown', color: '#95a5a6', icon: '?', opacity: 1 };

    try {
      const now = new Date();
      const then = new Date(timestamp);
      const diffHours = (now - then) / (1000 * 60 * 60);

      // Use backend-consistent opacity values (1.0, 0.8, 0.6, 0.4, 0.2)
      if (diffHours < 1) {
        return { label: 'Fresh', color: '#27ae60', icon: '✓', opacity: 1.0, hours: diffHours };
      } else if (diffHours < 6) {
        return { label: 'Recent', color: '#f39c12', icon: '~', opacity: 0.8, hours: diffHours };
      } else if (diffHours < 24) {
        return { label: 'Old', color: '#e67e22', icon: '⚠', opacity: 0.6, hours: diffHours };
      } else if (diffHours < 48) {
        return { label: 'Stale', color: '#e74c3c', icon: '!', opacity: 0.4, hours: diffHours };
      } else {
        return { label: 'Very Stale', color: '#8B0000', icon: '✗', opacity: 0.2, hours: diffHours };
      }
    } catch (error) {
      console.error('Error calculating time decay:', error);
      return { label: 'Unknown', color: '#95a5a6', icon: '?', opacity: 1 };
    }
  };

  // Format time ago
  const formatTimeAgo = (timestamp) => {
    if (!timestamp) return 'N/A';
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

  // Get source display name, credibility, and icon component
  const getSourceInfo = () => {
    const source = disaster.source || 'unknown';
    const sourceMap = {
      'nasa_firms': { name: 'NASA FIRMS', credibility: 95, IconComponent: getSourceIcon('nasa_firms') },
      'noaa': { name: 'NOAA', credibility: 95, IconComponent: getSourceIcon('noaa') },
      'noaa_weather': { name: 'NOAA Weather', credibility: 95, IconComponent: getSourceIcon('noaa_weather') },
      'fema': { name: 'FEMA', credibility: 95, IconComponent: getSourceIcon('fema') },
      'usgs': { name: 'USGS', credibility: 95, IconComponent: getSourceIcon('usgs') },
      'gdacs': { name: 'GDACS', credibility: 95, IconComponent: getSourceIcon('gdacs') },
      'cal_fire': { name: 'Cal Fire', credibility: 95, IconComponent: getSourceIcon('cal_fire') },
      'cal_oes': { name: 'Cal OES', credibility: 95, IconComponent: getSourceIcon('cal_oes') },
      'user_report': { name: 'User Report', credibility: disaster.recaptcha_score ? disaster.recaptcha_score * 100 : 70, IconComponent: getSourceIcon('user_report') },
      'user_report_authenticated': { name: 'User Report', credibility: disaster.recaptcha_score ? disaster.recaptcha_score * 100 : 70, IconComponent: getSourceIcon('user_report_authenticated') }
    };
    return sourceMap[source] || { name: source, credibility: 50, IconComponent: null };
  };

  // Memoize calculations
  const timeDecayInfo = useMemo(() => getTimeDecayInfo(), [disaster.time_decay, disaster.timestamp, disaster.reported_at, disaster.acquisition_date]);
  const severityBadge = useMemo(() => getSeverityBadge(disaster.severity), [disaster.severity]);
  const confidenceBadge = useMemo(() => getConfidenceBadge(disaster.confidence_level, disaster.confidence_score), [disaster.confidence_level, disaster.confidence_score]);
  const sourceInfo = useMemo(() => getSourceInfo(), [disaster.source, disaster.recaptcha_score]);
  const disasterType = disaster.type || disaster.disaster_type || disaster.event || 'Unknown';
  const disasterColor = getDisasterColor(disasterType);

  // Format location
  const formatLocation = () => {
    if (disaster.location_name) {
      return disaster.location_name;
    }
    if (disaster.area_desc) {
      return disaster.area_desc;
    }
    if (disaster.latitude && disaster.longitude) {
      return `${disaster.latitude.toFixed(4)}, ${disaster.longitude.toFixed(4)}`;
    }
    return 'N/A';
  };

  // Check if description is long
  const isLongDescription = disaster.description && disaster.description.length > 150;
  const displayDescription = showFullDescription || !isLongDescription
    ? disaster.description
    : disaster.description.substring(0, 150) + '...';

  // Handle image loading
  const handleImageLoad = () => {
    setImageLoading(false);
  };

  const handleImageError = () => {
    setImageError(true);
    setImageLoading(false);
  };

  // Check if user can mark as addressed (only for user reports and authenticated)
  const canMarkAddressed = currentUser && (disaster.source === 'user_report' || disaster.source === 'user_report_authenticated');

  return (
    <div
      className={`disaster-detail-card ${isExpanded ? 'expanded' : ''}`}
      style={{
        opacity: timeDecayInfo.opacity,
        borderLeftColor: disasterColor
      }}
    >
      {/* Card Header */}
      <div className="disaster-card-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="header-main">
          <span className="disaster-icon">
            <DisasterIconComponent size={24} strokeWidth={2} />
          </span>
          <div className="header-text">
            <h3 className="disaster-title">
              {disasterType.toUpperCase()}
            </h3>
            <p className="disaster-location">{formatLocation()}</p>
          </div>
        </div>
        <div className="header-badges">
          <span
            className="severity-badge-compact"
            style={{
              backgroundColor: severityBadge.bg,
              color: severityBadge.color
            }}
          >
            {severityBadge.text}
          </span>
          <span className="expand-icon">{isExpanded ? '▼' : '▶'}</span>
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="disaster-card-content">
          {/* Time Decay Indicator */}
          <div className="info-row time-decay-row">
            <span className="info-label">Freshness:</span>
            <span
              className="time-decay-badge"
              style={{
                backgroundColor: timeDecayInfo.color,
                color: 'white'
              }}
            >
              {timeDecayInfo.icon} {timeDecayInfo.label}
            </span>
            <span className="info-value-secondary">
              ({formatTimeAgo(disaster.timestamp || disaster.reported_at || disaster.acquisition_date)})
            </span>
          </div>

          {/* Source Information */}
          <div className="info-row">
            <span className="info-label">Source:</span>
            <div className="source-info">
              <span className="source-badge">
                {sourceInfo.IconComponent && <sourceInfo.IconComponent size={16} strokeWidth={2} />}
                {sourceInfo.name}
              </span>
              <span className="credibility-indicator">
                Credibility: {Math.round(sourceInfo.credibility)}%
              </span>
            </div>
          </div>

          {/* User Credibility Badge (if applicable) */}
          {disaster.user_credibility_level && (
            <div className="info-row">
              <span className="info-label">Reporter:</span>
              <div className="user-credibility-info">
                {disaster.user_display_name && (
                  <span className="user-display-name">
                    {disaster.user_display_name}
                  </span>
                )}
                <span
                  className="user-credibility-badge"
                  style={{
                    backgroundColor: disaster.user_credibility_level === 'Expert' ? '#FFD700' :
                                     disaster.user_credibility_level === 'Veteran' ? '#C0C0C0' :
                                     disaster.user_credibility_level === 'Trusted' ? '#27ae60' :
                                     disaster.user_credibility_level === 'Neutral' ? '#95a5a6' :
                                     disaster.user_credibility_level === 'Caution' ? '#f39c12' :
                                     disaster.user_credibility_level === 'Unreliable' ? '#e74c3c' : '#95a5a6'
                  }}
                >
                  {disaster.user_credibility_level === 'Expert' && <Star size={14} strokeWidth={2} />}
                  {disaster.user_credibility_level === 'Veteran' && <Award size={14} strokeWidth={2} />}
                  {disaster.user_credibility_level === 'Trusted' && <CheckCircle size={14} strokeWidth={2} />}
                  {disaster.user_credibility_level === 'Neutral' && <Circle size={14} strokeWidth={2} />}
                  {disaster.user_credibility_level === 'Caution' && <AlertTriangle size={14} strokeWidth={2} />}
                  {disaster.user_credibility_level === 'Unreliable' && <XCircle size={14} strokeWidth={2} />}
                  {' '}{disaster.user_credibility_level} ({disaster.user_credibility_score})
                </span>
              </div>
            </div>
          )}

          {/* Confidence Score */}
          {disaster.confidence_level && disaster.confidence_score !== undefined && (
            <div className="info-row">
              <span className="info-label">Confidence:</span>
              <span
                className="confidence-badge"
                style={{
                  backgroundColor: confidenceBadge.bg,
                  color: confidenceBadge.color
                }}
              >
                {confidenceBadge.icon} {disaster.confidence_level} ({confidenceBadge.percentage}%)
              </span>
            </div>
          )}

          {/* AI Reasoning */}
          {disaster.confidence_breakdown?.ai_enhancement?.reasoning && (
            <div className="info-row ai-reasoning-row">
              <span className="info-label">AI Analysis:</span>
              <div className="ai-reasoning-box">
                {disaster.confidence_breakdown.ai_enhancement.reasoning}
              </div>
            </div>
          )}

          {/* Severity */}
          <div className="info-row">
            <span className="info-label">Severity:</span>
            <span
              className="severity-badge"
              style={{
                backgroundColor: severityBadge.bg,
                color: severityBadge.color
              }}
            >
              {severityBadge.text}
            </span>
          </div>

          {/* Coordinates */}
          {disaster.latitude && disaster.longitude && (
            <div className="info-row">
              <span className="info-label">Coordinates:</span>
              <span className="info-value">
                {disaster.latitude.toFixed(4)}, {disaster.longitude.toFixed(4)}
              </span>
            </div>
          )}

          {/* Timestamp */}
          <div className="info-row">
            <span className="info-label">Timestamp:</span>
            <span className="info-value">
              {disaster.timestamp ? new Date(disaster.timestamp).toLocaleString() :
               disaster.reported_at ? new Date(disaster.reported_at).toLocaleString() :
               disaster.acquisition_date ? `${disaster.acquisition_date} ${disaster.acquisition_time || ''}` :
               'N/A'}
            </span>
          </div>

          {/* Affected Population */}
          {disaster.affected_population && (
            <div className="info-row">
              <span className="info-label">Affected Population:</span>
              <span className="info-value-highlight">
                {disaster.affected_population.toLocaleString()} people
              </span>
            </div>
          )}

          {/* Description */}
          {disaster.description && (
            <div className="info-row description-row">
              <span className="info-label">Description:</span>
              <div className="description-content">
                <p>{displayDescription}</p>
                {isLongDescription && (
                  <button
                    className="read-more-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowFullDescription(!showFullDescription);
                    }}
                  >
                    {showFullDescription ? 'Read less' : 'Read more'}
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Image */}
          {disaster.image_url && !imageError && (
            <div className="info-row image-row">
              <span className="info-label">Image:</span>
              <div className="image-container">
                {imageLoading && (
                  <div className="image-loading">Loading image...</div>
                )}
                <img
                  src={disaster.image_url}
                  alt={`${disasterType} disaster`}
                  className="disaster-image"
                  onLoad={handleImageLoad}
                  onError={handleImageError}
                  style={{ display: imageLoading ? 'none' : 'block' }}
                />
              </div>
            </div>
          )}

          {/* Additional NASA FIRMS fields */}
          {disaster.source === 'nasa_firms' && (
            <>
              {disaster.brightness && (
                <div className="info-row">
                  <span className="info-label">Brightness:</span>
                  <span className="info-value">{disaster.brightness}K</span>
                </div>
              )}
              {disaster.frp && (
                <div className="info-row">
                  <span className="info-label">Fire Radiative Power:</span>
                  <span className="info-value">{disaster.frp} MW</span>
                </div>
              )}
            </>
          )}

          {/* Additional NOAA fields */}
          {(disaster.source === 'noaa' || disaster.source === 'noaa_weather') && (
            <>
              {disaster.urgency && (
                <div className="info-row">
                  <span className="info-label">Urgency:</span>
                  <span className="info-value">{disaster.urgency}</span>
                </div>
              )}
              {disaster.certainty && (
                <div className="info-row">
                  <span className="info-label">Certainty:</span>
                  <span className="info-value">{disaster.certainty}</span>
                </div>
              )}
              {disaster.headline && (
                <div className="info-row">
                  <span className="info-label">Headline:</span>
                  <span className="info-value">{disaster.headline}</span>
                </div>
              )}
              {disaster.expires && (
                <div className="info-row">
                  <span className="info-label">Expires:</span>
                  <span className="info-value">{new Date(disaster.expires).toLocaleString()}</span>
                </div>
              )}
            </>
          )}

          {/* Action Buttons */}
          <div className="action-buttons">
            <button
              className="action-btn primary-btn"
              onClick={(e) => {
                e.stopPropagation();
                onGetRoute && onGetRoute(disaster);
              }}
              title="Get a safe route away from this disaster"
            >
              🛣️ Get Safe Route
            </button>

            {canMarkAddressed && (
              <button
                className="action-btn secondary-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  onMarkAddressed && onMarkAddressed(disaster);
                }}
                title="Mark this disaster as addressed"
              >
                ✓ Mark as Addressed
              </button>
            )}

            {!currentUser && (disaster.source === 'user_report' || disaster.source === 'user_report_authenticated') && (
              <button
                className="action-btn secondary-btn disabled"
                disabled
                title="You must be logged in to mark disasters as addressed"
              >
                ✓ Mark as Addressed (Login Required)
              </button>
            )}

            <button
              className="action-btn tertiary-btn"
              onClick={(e) => {
                e.stopPropagation();
                onShare && onShare(disaster);
              }}
              title="Share this disaster information"
            >
              📤 Share
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default DisasterDetailCard;
