import React, { useState, useEffect } from 'react';
import { X, MapPin, Bell } from 'lucide-react';
import { getDisasterIcon } from '../config/icons';
import './AlertSettingsModal.css';

const AlertSettingsModal = ({
  isOpen,
  onClose,
  onSave,
  initialPreferences = null,
  userLocation = null,
  onEnableLocation = null,
  onSetTestLocation = null,
  locationError = null,
  isLoadingLocation = false
}) => {
  const [preferences, setPreferences] = useState(getDefaultPreferences());
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [errors, setErrors] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  // Load initial preferences when modal opens
  useEffect(() => {
    if (isOpen && initialPreferences) {
      setPreferences(initialPreferences);
      setHasUnsavedChanges(false);
    } else if (isOpen && !initialPreferences) {
      setPreferences(getDefaultPreferences());
      setHasUnsavedChanges(false);
    }
  }, [isOpen, initialPreferences]);

  // Prevent body scroll when modal is open (iOS Safari compatible)
  useEffect(() => {
    if (isOpen) {
      // Save current scroll position
      const scrollY = window.scrollY;
      // Lock scroll - iOS Safari compatible approach
      document.body.style.position = 'fixed';
      document.body.style.top = `-${scrollY}px`;
      document.body.style.width = '100%';
      document.body.style.overflowY = 'scroll'; // Prevent layout shift
    } else {
      // Restore scroll position
      const scrollY = document.body.style.top;
      document.body.style.position = '';
      document.body.style.top = '';
      document.body.style.width = '';
      document.body.style.overflowY = '';
      window.scrollTo(0, parseInt(scrollY || '0') * -1);
    }

    return () => {
      // Cleanup on unmount
      document.body.style.position = '';
      document.body.style.top = '';
      document.body.style.width = '';
      document.body.style.overflowY = '';
    };
  }, [isOpen]);

  // Handle escape key to close modal
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        handleClose();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, hasUnsavedChanges]);

  const handleClose = () => {
    if (hasUnsavedChanges) {
      const confirmClose = window.confirm('You have unsaved changes. Are you sure you want to close?');
      if (!confirmClose) {
        return;
      }
    }
    setErrors([]);
    setShowSuccess(false);
    onClose();
  };

  const handleSeverityToggle = (severity) => {
    setHasUnsavedChanges(true);
    setPreferences(prev => ({
      ...prev,
      severity_filter: prev.severity_filter.includes(severity)
        ? prev.severity_filter.filter(s => s !== severity)
        : [...prev.severity_filter, severity]
    }));
  };

  const handleDisasterTypeToggle = (type) => {
    setHasUnsavedChanges(true);
    setPreferences(prev => ({
      ...prev,
      disaster_types: prev.disaster_types.includes(type)
        ? prev.disaster_types.filter(t => t !== type)
        : [...prev.disaster_types, type]
    }));
  };


  const handleSelectAllSeverities = () => {
    setHasUnsavedChanges(true);
    setPreferences(prev => ({
      ...prev,
      severity_filter: ['critical', 'high', 'medium', 'low']
    }));
  };

  const handleDeselectAllSeverities = () => {
    setHasUnsavedChanges(true);
    setPreferences(prev => ({
      ...prev,
      severity_filter: []
    }));
  };

  const handleSelectAllDisasterTypes = () => {
    setHasUnsavedChanges(true);
    setPreferences(prev => ({
      ...prev,
      disaster_types: ['earthquake', 'flood', 'wildfire', 'hurricane', 'tornado', 'volcano', 'drought']
    }));
  };

  const handleDeselectAllDisasterTypes = () => {
    setHasUnsavedChanges(true);
    setPreferences(prev => ({
      ...prev,
      disaster_types: []
    }));
  };

  const handleResetToDefaults = () => {
    const confirmReset = window.confirm('Reset all settings to default values?');
    if (confirmReset) {
      setHasUnsavedChanges(true);
      setPreferences(getDefaultPreferences());
      setErrors([]);
    }
  };

  const handleTestAlert = () => {
    console.log('Test alert triggered with preferences:', preferences);
    alert('Test notification sent! Check your notification settings.');
  };

  const validatePreferences = (prefs) => {
    const validationErrors = [];

    // Severity filter validation
    if (prefs.severity_filter.length === 0) {
      validationErrors.push('Select at least one severity level');
    }

    // Disaster types validation
    if (prefs.disaster_types.length === 0) {
      validationErrors.push('Select at least one disaster type');
    }

    return validationErrors;
  };

  const handleSave = async () => {
    const validationErrors = validatePreferences(preferences);
    if (validationErrors.length > 0) {
      setErrors(validationErrors);
      return;
    }

    setIsLoading(true);
    setErrors([]);

    try {
      await onSave(preferences);
      setHasUnsavedChanges(false);
      setShowSuccess(true);

      // Auto-hide success message and close modal after 1.5s
      setTimeout(() => {
        setShowSuccess(false);
        onClose();
      }, 1500);
    } catch (error) {
      console.error('Error saving preferences:', error);
      setErrors(['Failed to save preferences. Please try again.']);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="modal-title"
        aria-modal="true"
      >
        {/* Header */}
        <div className="modal-header">
          <h2 id="modal-title">Alert Settings</h2>
          <button
            className="close-button"
            onClick={handleClose}
            aria-label="Close modal"
          >
            <X size={20} strokeWidth={2} />
          </button>
        </div>

        {/* Error Display */}
        {errors.length > 0 && (
          <div className="error-banner" role="alert">
            <strong>Please fix the following errors:</strong>
            <ul>
              {errors.map((error, index) => (
                <li key={index}>{error}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Success Message */}
        {showSuccess && (
          <div className="success-banner" role="alert">
            Settings saved successfully!
          </div>
        )}

        <div className="modal-body">
          {/* Location Settings Section */}
          <div className="settings-section">
            <h3>Location Settings</h3>

            <div className="location-controls">
              <button
                className="location-button enable-location-btn"
                onClick={onEnableLocation}
                disabled={isLoadingLocation || !onEnableLocation}
                aria-label="Enable location access"
              >
                {isLoadingLocation ? 'Getting location...' : 'Enable Location'}
              </button>

              <button
                className="location-button test-location-btn"
                onClick={onSetTestLocation}
                disabled={!onSetTestLocation}
                aria-label="Set test location for development"
              >
                Set Test Location
              </button>

              {locationError && (
                <div className="location-error" role="alert">
                  {locationError}
                </div>
              )}

              {userLocation && (
                <div className="current-location-display">
                  <MapPin size={18} strokeWidth={2} className="location-icon" />
                  <span className="location-coords">
                    Current: {userLocation.lat.toFixed(4)}, {userLocation.lon.toFixed(4)}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* General Settings */}
          <div className="settings-section">
            <h3>General Settings</h3>
            <div className="setting-item">
              <label className="toggle-label">
                <input
                  type="checkbox"
                  checked={preferences.enabled}
                  onChange={(e) => {
                    setHasUnsavedChanges(true);
                    setPreferences(prev => ({ ...prev, enabled: e.target.checked }));
                  }}
                />
                <span className="toggle-text">Enable Proximity Alerts</span>
              </label>
            </div>

            <div className="setting-item">
              <label className="toggle-label">
                <input
                  type="checkbox"
                  checked={preferences.show_radius_circle || false}
                  onChange={(e) => {
                    setHasUnsavedChanges(true);
                    setPreferences(prev => ({ ...prev, show_radius_circle: e.target.checked }));
                  }}
                />
                <span className="toggle-text">Show Radius Circle on Map</span>
              </label>
              <p className="setting-description">Display proximity radius as circle on map. Radius is controlled in Map Settings.</p>
            </div>
          </div>

          {/* Severity Filter */}
          <div className="settings-section">
            <div className="section-header">
              <h3>Severity Filter</h3>
              <div className="select-buttons">
                <button
                  type="button"
                  onClick={handleSelectAllSeverities}
                  className="select-all-button"
                >
                  Select All
                </button>
                <button
                  type="button"
                  onClick={handleDeselectAllSeverities}
                  className="select-all-button"
                >
                  Deselect All
                </button>
              </div>
            </div>
            <div className="checkbox-grid">
              {[
                { value: 'critical', label: 'Critical', color: '#dc2626' },
                { value: 'high', label: 'High', color: '#ea580c' },
                { value: 'medium', label: 'Medium', color: '#f59e0b' },
                { value: 'low', label: 'Low', color: '#84cc16' }
              ].map(severity => (
                <label key={severity.value} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={preferences.severity_filter.includes(severity.value)}
                    onChange={() => handleSeverityToggle(severity.value)}
                  />
                  <span
                    className="severity-badge"
                    style={{ backgroundColor: severity.color }}
                  >
                    {severity.label}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Disaster Types */}
          <div className="settings-section">
            <div className="section-header">
              <h3>Disaster Types</h3>
              <div className="select-buttons">
                <button
                  type="button"
                  onClick={handleSelectAllDisasterTypes}
                  className="select-all-button"
                >
                  Select All
                </button>
                <button
                  type="button"
                  onClick={handleDeselectAllDisasterTypes}
                  className="select-all-button"
                >
                  Deselect All
                </button>
              </div>
            </div>
            <div className="checkbox-grid">
              {[
                { value: 'earthquake', label: 'Earthquake' },
                { value: 'flood', label: 'Flood' },
                { value: 'wildfire', label: 'Wildfire' },
                { value: 'hurricane', label: 'Hurricane' },
                { value: 'tornado', label: 'Tornado' },
                { value: 'volcano', label: 'Volcano' },
                { value: 'drought', label: 'Drought' }
              ].map(type => {
                const IconComponent = getDisasterIcon(type.value);
                return (
                  <label key={type.value} className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={preferences.disaster_types.includes(type.value)}
                      onChange={() => handleDisasterTypeToggle(type.value)}
                    />
                    <span className="disaster-type-label">
                      <IconComponent size={18} strokeWidth={2} className="disaster-icon" style={{ marginRight: '6px' }} />
                      {type.label}
                    </span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Test Alert Button */}
          <div className="settings-section">
            <button
              type="button"
              onClick={handleTestAlert}
              className="test-alert-button"
              disabled={!preferences.enabled}
            >
              Send Test Alert
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button
            type="button"
            onClick={handleResetToDefaults}
            className="reset-button"
            disabled={isLoading}
          >
            Reset to Defaults
          </button>
          <div className="modal-buttons">
            <button
              type="button"
              onClick={handleClose}
              className="cancel-button"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="save-button"
              disabled={isLoading}
            >
              {isLoading ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Helper function to get default preferences
function getDefaultPreferences() {
  return {
    enabled: true,
    show_radius_circle: true, // Show circle by default
    severity_filter: ['critical', 'high', 'medium', 'low'],
    disaster_types: ['earthquake', 'flood', 'wildfire', 'hurricane', 'tornado', 'volcano', 'drought']
  };
}

export default AlertSettingsModal;
