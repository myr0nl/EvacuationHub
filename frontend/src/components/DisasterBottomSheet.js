import React from 'react';
import { X } from 'lucide-react';
import BottomSheet from './BottomSheet';
import './DisasterBottomSheet.css';

// Import the same components used in Map.js popups
import { Star, Award, CheckCircle, Circle as CircleIcon, AlertTriangle, XCircle } from 'lucide-react';

// Reuse the same helper components from Map.js
const SeverityBadge = ({ severity }) => {
  const severityConfig = {
    critical: { icon: XCircle, color: '#dc2626', bg: '#fee2e2', label: 'Critical' },
    high: { icon: AlertTriangle, color: '#f59e0b', bg: '#fef3c7', label: 'High' },
    medium: { icon: CircleIcon, color: '#eab308', bg: '#fef9c3', label: 'Medium' },
    low: { icon: CheckCircle, color: '#10b981', bg: '#d1fae5', label: 'Low' }
  };

  const config = severityConfig[severity?.toLowerCase()] || severityConfig.low;
  const Icon = config.icon;

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px',
      padding: '4px 8px',
      borderRadius: '6px',
      backgroundColor: config.bg,
      color: config.color,
      fontWeight: '600',
      fontSize: '0.875rem'
    }}>
      <Icon size={14} />
      {config.label}
    </span>
  );
};

const ConfidenceBadge = ({ level, score }) => {
  const scorePercent = Math.round((score || 0) * 100);
  const config = {
    High: { icon: Star, color: '#10b981', bg: '#d1fae5' },
    Medium: { icon: Award, color: '#eab308', bg: '#fef9c3' },
    Low: { icon: AlertTriangle, color: '#f59e0b', bg: '#fef3c7' }
  };

  const badgeConfig = config[level] || config.Low;
  const Icon = badgeConfig.icon;

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      padding: '6px 10px',
      borderRadius: '8px',
      backgroundColor: badgeConfig.bg,
      color: badgeConfig.color,
      fontWeight: '600',
      fontSize: '0.9rem'
    }}>
      <Icon size={16} />
      {level} ({scorePercent}%)
    </span>
  );
};

const UserCredibilityBadge = ({ item }) => {
  if (!item.user_credibility_at_submission) {
    return <span style={{ fontSize: '0.9rem', color: '#6b7280', fontStyle: 'italic' }}>(Anonymous)</span>;
  }

  const credibility = item.user_credibility_at_submission;
  const level = item.user_credibility_level_at_submission || 'Neutral';

  const config = {
    Elite: { icon: Star, color: '#8b5cf6', bg: '#f3e8ff' },
    Expert: { icon: Award, color: '#3b82f6', bg: '#dbeafe' },
    Trusted: { icon: CheckCircle, color: '#10b981', bg: '#d1fae5' },
    Neutral: { icon: CircleIcon, color: '#6b7280', bg: '#f3f4f6' },
    Flagged: { icon: AlertTriangle, color: '#f59e0b', bg: '#fef3c7' },
    Banned: { icon: XCircle, color: '#dc2626', bg: '#fee2e2' }
  };

  const badgeConfig = config[level] || config.Neutral;
  const Icon = badgeConfig.icon;

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px',
      padding: '3px 8px',
      borderRadius: '6px',
      backgroundColor: badgeConfig.bg,
      color: badgeConfig.color,
      fontWeight: '600',
      fontSize: '0.85rem',
      marginLeft: '8px'
    }}>
      <Icon size={12} />
      {level} ({credibility})
    </span>
  );
};

const DisasterBottomSheet = ({ disaster, onClose, isAdmin, currentUser, onEditReport, onDeleteReport }) => {
  if (!disaster) return null;

  // TODO: Add admin edit/delete buttons for mobile bottom sheet (similar to desktop popup)

  const renderContent = () => {
    // User-submitted report
    if (disaster.source === 'user_report' || disaster.source === 'user_report_authenticated' || disaster.disaster_type || (!disaster.source && !disaster.brightness)) {
      const disasterType = disaster.type || disaster.disaster_type || 'DISASTER';
      const isAuthenticated = disaster.source === 'user_report_authenticated' || disaster.user_id;

      return (
        <div className="disaster-bottom-sheet-content">
          <div className="disaster-bottom-sheet-header">
            <h2 className="disaster-bottom-sheet-title">
              👤 USER REPORT: {disasterType.toUpperCase()}
              <UserCredibilityBadge item={disaster} />
            </h2>
            <button className="disaster-bottom-sheet-close" onClick={onClose} aria-label="Close">
              <X size={24} />
            </button>
          </div>

          <div className="disaster-bottom-sheet-body">
            {isAuthenticated && disaster.user_display_name && (
              <div className="disaster-field">
                <strong>Reported by:</strong>
                <p style={{ fontWeight: '600', color: '#1e40af' }}>
                  {disaster.user_display_name}
                </p>
              </div>
            )}

            {disaster.confidence_level && disaster.confidence_score !== undefined && (
              <div className="disaster-field">
                <strong>Confidence:</strong>
                <ConfidenceBadge level={disaster.confidence_level} score={disaster.confidence_score} />
                {disaster.confidence_breakdown?.ai_enhancement?.reasoning && (
                  <div style={{
                    marginTop: '8px',
                    padding: '8px',
                    backgroundColor: '#f0f0f0',
                    borderRadius: '4px',
                    fontSize: '0.85rem',
                    fontStyle: 'italic'
                  }}>
                    <strong>AI Analysis:</strong> {disaster.confidence_breakdown.ai_enhancement.reasoning}
                  </div>
                )}
              </div>
            )}

            <div className="disaster-field">
              <strong>Severity:</strong>
              <SeverityBadge severity={disaster.severity} />
            </div>

            {disaster.description && (
              <div className="disaster-field">
                <strong>Description:</strong>
                <p>{disaster.description}</p>
              </div>
            )}

            <div className="disaster-field">
              <strong>Location:</strong>
              {disaster.location_name && (
                <p style={{ marginBottom: '4px', fontWeight: '500' }}>
                  📍 {disaster.location_name}
                </p>
              )}
              {disaster.latitude && disaster.longitude && (
                <p style={{ fontSize: '0.9rem', color: '#6b7280' }}>
                  {disaster.latitude.toFixed(4)}, {disaster.longitude.toFixed(4)}
                </p>
              )}
            </div>

            {(disaster.reported_at || disaster.timestamp) && (
              <div className="disaster-field">
                <strong>Reported:</strong>
                <p>{new Date(disaster.reported_at || disaster.timestamp).toLocaleString()}</p>
              </div>
            )}

            {disaster.affected_population && (
              <div className="disaster-field">
                <strong>Affected Population:</strong>
                <p>{disaster.affected_population.toLocaleString()} people</p>
              </div>
            )}
          </div>
        </div>
      );
    }

    // NASA FIRMS wildfire
    if (disaster.source === 'nasa_firms') {
      return (
        <div className="disaster-bottom-sheet-content">
          <div className="disaster-bottom-sheet-header">
            <h2 className="disaster-bottom-sheet-title">
              🔥 WILDFIRE (NASA FIRMS)
            </h2>
            <button className="disaster-bottom-sheet-close" onClick={onClose} aria-label="Close">
              <X size={24} />
            </button>
          </div>

          <div className="disaster-bottom-sheet-body">
            {disaster.confidence_level && disaster.confidence_score !== undefined && (
              <div className="disaster-field">
                <strong>Confidence:</strong>
                <ConfidenceBadge level={disaster.confidence_level} score={disaster.confidence_score} />
              </div>
            )}

            <div className="disaster-field">
              <strong>Severity:</strong>
              <SeverityBadge severity={disaster.severity} />
            </div>

            <div className="disaster-field">
              <strong>Brightness:</strong>
              <p>{disaster.brightness}K</p>
            </div>

            <div className="disaster-field">
              <strong>Fire Radiative Power:</strong>
              <p>{disaster.frp} MW</p>
            </div>

            <div className="disaster-field">
              <strong>Location:</strong>
              {disaster.latitude && disaster.longitude && (
                <p>{disaster.latitude.toFixed(4)}, {disaster.longitude.toFixed(4)}</p>
              )}
            </div>

            <div className="disaster-field">
              <strong>Detected:</strong>
              <p>{disaster.timestamp ? new Date(disaster.timestamp).toLocaleString() : `${disaster.acquisition_date || ''} ${disaster.acquisition_time || ''}`.trim()}</p>
            </div>
          </div>
        </div>
      );
    }

    // NOAA weather alert
    if (disaster.source === 'noaa') {
      return (
        <div className="disaster-bottom-sheet-content">
          <div className="disaster-bottom-sheet-header">
            <h2 className="disaster-bottom-sheet-title">
              ⚠️ {disaster.event?.toUpperCase() || 'WEATHER ALERT'}
            </h2>
            <button className="disaster-bottom-sheet-close" onClick={onClose} aria-label="Close">
              <X size={24} />
            </button>
          </div>

          <div className="disaster-bottom-sheet-body">
            {disaster.confidence_level && disaster.confidence_score !== undefined && (
              <div className="disaster-field">
                <strong>Confidence:</strong>
                <ConfidenceBadge level={disaster.confidence_level} score={disaster.confidence_score} />
              </div>
            )}

            <div className="disaster-field">
              <strong>Severity:</strong>
              <SeverityBadge severity={disaster.severity} />
            </div>

            <div className="disaster-field">
              <strong>Urgency:</strong>
              <p>{disaster.urgency}</p>
            </div>

            <div className="disaster-field">
              <strong>Certainty:</strong>
              <p>{disaster.certainty}</p>
            </div>

            {disaster.headline && (
              <div className="disaster-field">
                <strong>Headline:</strong>
                <p>{disaster.headline}</p>
              </div>
            )}

            {disaster.area_desc && (
              <div className="disaster-field">
                <strong>Area:</strong>
                <p>{disaster.area_desc}</p>
              </div>
            )}

            <div className="disaster-field">
              <strong>Location:</strong>
              {disaster.latitude && disaster.longitude && (
                <p>{disaster.latitude.toFixed(4)}, {disaster.longitude.toFixed(4)}</p>
              )}
            </div>

            {disaster.onset && (
              <div className="disaster-field">
                <strong>Onset:</strong>
                <p>{new Date(disaster.onset).toLocaleString()}</p>
              </div>
            )}

            {disaster.expires && (
              <div className="disaster-field">
                <strong>Expires:</strong>
                <p>{new Date(disaster.expires).toLocaleString()}</p>
              </div>
            )}
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <BottomSheet defaultState="anchor" onClose={onClose}>
      {renderContent()}
    </BottomSheet>
  );
};

export default DisasterBottomSheet;
