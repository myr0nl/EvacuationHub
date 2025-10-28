import React, { useState, useEffect } from 'react';
import { X, Settings, Map, ZoomIn, Check, Globe } from 'lucide-react';
import './MapSettingsModal.css';

/**
 * Default map settings
 */
function getDefaultSettings() {
  return {
    zoom_radius_mi: 20,      // Default 20 miles zoom radius
    display_radius_mi: 20,   // Default 20 miles display radius
    auto_zoom: false,        // Auto-zoom to fit user location radius
    show_all_disasters: false, // Show all disasters regardless of distance
    reduced_motion: false    // Disable animations (for screen recording)
  };
}

const MapSettingsModal = ({
  isOpen,
  onClose,
  onSave,
  initialSettings = null
}) => {
  const [settings, setSettings] = useState(getDefaultSettings());
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [errors, setErrors] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  // Load initial settings when modal opens
  useEffect(() => {
    if (isOpen && initialSettings) {
      setSettings(initialSettings);
      setHasUnsavedChanges(false);
    } else if (isOpen && !initialSettings) {
      // Try loading from localStorage for guest users
      try {
        const saved = localStorage.getItem('mapSettings');
        if (saved) {
          setSettings(JSON.parse(saved));
        } else {
          setSettings(getDefaultSettings());
        }
      } catch (error) {
        console.error('Error loading map settings:', error);
        setSettings(getDefaultSettings());
      }
      setHasUnsavedChanges(false);
    }
  }, [isOpen, initialSettings]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  // Apply reduced motion class to document root
  useEffect(() => {
    if (settings.reduced_motion) {
      document.documentElement.classList.add('reduced-motion');
    } else {
      document.documentElement.classList.remove('reduced-motion');
    }
  }, [settings.reduced_motion]);

  // Handle escape key to close modal
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        handleClose();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, hasUnsavedChanges]); // handleClose intentionally excluded to avoid recreating listener

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

  const handleZoomRadiusChange = (e) => {
    setHasUnsavedChanges(true);
    setSettings(prev => ({
      ...prev,
      zoom_radius_mi: parseInt(e.target.value, 10)
    }));
  };

  const handleDisplayRadiusChange = (e) => {
    setHasUnsavedChanges(true);
    setSettings(prev => ({
      ...prev,
      display_radius_mi: parseInt(e.target.value, 10)
    }));
  };

  const handleAutoZoomToggle = () => {
    setHasUnsavedChanges(true);
    setSettings(prev => ({
      ...prev,
      auto_zoom: !prev.auto_zoom
    }));
  };

  const handleShowAllDisastersToggle = () => {
    setHasUnsavedChanges(true);
    setSettings(prev => ({
      ...prev,
      show_all_disasters: !prev.show_all_disasters
    }));
  };

  const handleReducedMotionToggle = () => {
    setHasUnsavedChanges(true);
    setSettings(prev => ({
      ...prev,
      reduced_motion: !prev.reduced_motion
    }));
  };

  const validateSettings = () => {
    const validationErrors = [];

    // Validate zoom radius (must match backend validation: 1-100 miles)
    if (settings.zoom_radius_mi < 1 || settings.zoom_radius_mi > 100) {
      validationErrors.push('Zoom radius must be between 1 and 100 miles');
    }

    // Validate display radius (must match backend validation: 1-100 miles)
    if (settings.display_radius_mi < 1 || settings.display_radius_mi > 100) {
      validationErrors.push('Display radius must be between 1 and 100 miles');
    }

    setErrors(validationErrors);
    return validationErrors.length === 0;
  };

  const handleSave = async () => {
    // Validate settings
    if (!validateSettings()) {
      return;
    }

    setIsLoading(true);
    setErrors([]);

    try {
      // Save to localStorage for guest users
      localStorage.setItem('mapSettings', JSON.stringify(settings));

      // Call parent save handler (could save to backend for authenticated users)
      await onSave(settings);

      setShowSuccess(true);
      setHasUnsavedChanges(false);

      // Hide success message and close after 2 seconds
      setTimeout(() => {
        setShowSuccess(false);
        onClose();
      }, 2000);
    } catch (error) {
      console.error('Error saving map settings:', error);
      setErrors([error.message || 'Failed to save settings. Please try again.']);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    const confirmReset = window.confirm('Reset all settings to defaults?');
    if (confirmReset) {
      setSettings(getDefaultSettings());
      setHasUnsavedChanges(true);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="map-settings-modal-overlay" onClick={handleClose}>
      <div className="map-settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Settings size={20} strokeWidth={2} />
            Map Settings
          </h2>
          <button className="close-button" onClick={handleClose} aria-label="Close">
            <X size={20} strokeWidth={2} />
          </button>
        </div>

        <div className="modal-body">
          {errors.length > 0 && (
            <div className="error-banner">
              {errors.map((error, index) => (
                <p key={index}>{error}</p>
              ))}
            </div>
          )}

          {showSuccess && (
            <div className="success-banner" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Check size={18} strokeWidth={2} />
              Settings saved successfully!
            </div>
          )}

          {/* Map Zoom Radius Setting */}
          <div className="settings-section">
            <div className="section-header">
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <ZoomIn size={18} strokeWidth={2} />
                Map Zoom Range
              </h3>
              <p className="section-description">
                Sets the maximum viewing area around your location. Smaller radius = closer zoom, larger radius = wider view. When auto-zoom is enabled, the map will automatically zoom to show this entire radius.
              </p>
            </div>

            <div className="slider-container">
              <label htmlFor="zoom-radius-slider">
                Zoom Radius: <strong>{settings.zoom_radius_mi} miles</strong>
              </label>
              <input
                id="zoom-radius-slider"
                type="range"
                min="1"
                max="100"
                value={settings.zoom_radius_mi}
                onChange={handleZoomRadiusChange}
                className="radius-slider"
              />
              <div className="slider-labels">
                <span>1 mi</span>
                <span>50 mi</span>
                <span>100 mi</span>
              </div>
            </div>

            <div className="checkbox-container">
              <label>
                <input
                  type="checkbox"
                  checked={settings.auto_zoom}
                  onChange={handleAutoZoomToggle}
                />
                <span>Auto-zoom when settings change</span>
              </label>
              <p className="help-text">
                When enabled, the map automatically zooms to fit the selected radius whenever you change settings or your location changes. Disable this if you prefer to manually control the zoom level.
              </p>
            </div>
          </div>

          <div className="section-divider"></div>

          {/* Display Disasters Radius Setting */}
          <div className="settings-section">
            <div className="section-header">
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Globe size={18} strokeWidth={2} />
                Display Disasters Range
              </h3>
              <p className="section-description">
                Control how far disasters are displayed on the map AND how far to search for proximity alerts
              </p>
              {settings.display_radius_mi > 50 && (
                <div className="proximity-alert-notice">
                  ⚠️ Note: Proximity alerts are capped at 50 miles due to backend limitations, even though the map will display disasters within {settings.display_radius_mi} miles.
                </div>
              )}
            </div>

            <div className="slider-container">
              <label htmlFor="display-radius-slider">
                Display Radius: <strong>{settings.display_radius_mi} miles</strong>
              </label>
              <input
                id="display-radius-slider"
                type="range"
                min="1"
                max="100"
                value={settings.display_radius_mi}
                onChange={handleDisplayRadiusChange}
                className="radius-slider"
                disabled={settings.show_all_disasters}
              />
              <div className="slider-labels">
                <span>1 mi</span>
                <span>50 mi</span>
                <span>100 mi</span>
              </div>
            </div>

            <div className="checkbox-container">
              <label>
                <input
                  type="checkbox"
                  checked={settings.show_all_disasters}
                  onChange={handleShowAllDisastersToggle}
                />
                <span>Show all disasters (ignore distance filter)</span>
              </label>
              <p className="help-text">
                When enabled, all disasters are displayed regardless of distance from your location
              </p>
            </div>

            <div className="checkbox-container">
              <label>
                <input
                  type="checkbox"
                  checked={settings.reduced_motion}
                  onChange={handleReducedMotionToggle}
                />
                <span>Disable animations (for screen recording)</span>
              </label>
              <p className="help-text">
                Disables animations, transitions, hover effects, and backdrop filters. Recommended for low FPS screen recording to prevent visual flickering.
              </p>
            </div>
          </div>

          <div className="section-divider"></div>

          {/* Summary Section */}
          <div className="settings-summary">
            <h4 style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Map size={18} strokeWidth={2} />
              Current Settings
            </h4>
            <ul>
              <li>
                Map will zoom to show a <strong>{settings.zoom_radius_mi}-mile radius</strong> around your location
                {settings.auto_zoom && ' (auto-zoom enabled)'}
              </li>
              <li>
                {settings.show_all_disasters
                  ? 'Displaying all disasters regardless of distance'
                  : `Showing disasters within ${settings.display_radius_mi} miles of your location`
                }
              </li>
            </ul>
          </div>
        </div>

        <div className="modal-footer">
          <button
            className="reset-button"
            onClick={handleReset}
            disabled={isLoading}
          >
            Reset to Defaults
          </button>

          <div className="action-buttons">
            <button
              className="cancel-button"
              onClick={handleClose}
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              className="save-button"
              onClick={handleSave}
              disabled={isLoading || !hasUnsavedChanges}
            >
              {isLoading ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MapSettingsModal;
