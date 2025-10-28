import React, { useState, useEffect } from 'react';
import { createReport } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import CredibilityBadge from './CredibilityBadge';
import { Link } from 'react-router-dom';
import { Navigation, Map, Check, X } from 'lucide-react';
import './ReportForm.css';

function ReportForm({ onReportSubmitted, locationPickerEnabled, onToggleLocationPicker, pickedLocation, onClose }) {
  const { currentUser, userProfile } = useAuth();
  const [formData, setFormData] = useState({
    type: 'earthquake',
    severity: 'medium',
    latitude: '',
    longitude: '',
    description: '',
    affected_population: ''
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [credibilityImpact, setCredibilityImpact] = useState(null);

  const disasterTypes = [
    { value: 'earthquake', label: 'Earthquake' },
    { value: 'flood', label: 'Flood' },
    { value: 'wildfire', label: 'Wildfire' },
    { value: 'hurricane', label: 'Hurricane' },
    { value: 'tornado', label: 'Tornado' },
    { value: 'other', label: 'Other' }
  ];

  const severityLevels = [
    { value: 'low', label: 'Low', color: '#27ae60' },
    { value: 'medium', label: 'Medium', color: '#f39c12' },
    { value: 'high', label: 'High', color: '#e74c3c' },
    { value: 'critical', label: 'Critical', color: '#c0392b' }
  ];

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    setError(null);
    setSuccess(false);
  };

  const getCurrentLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setFormData(prev => ({
            ...prev,
            latitude: position.coords.latitude.toFixed(6),
            longitude: position.coords.longitude.toFixed(6)
          }));
        },
        (error) => {
          setError('Unable to get current location. Please enter manually.');
          console.error('Geolocation error:', error);
        },
        {
          enableHighAccuracy: false, // Fast, uses network location instead of GPS
          timeout: 5000, // 5 second timeout (default is infinite!)
          maximumAge: 60000 // Accept cached location up to 1 minute old
        }
      );
    } else {
      setError('Geolocation is not supported by your browser.');
    }
  };

  // Update form when location is picked from map
  useEffect(() => {
    if (pickedLocation) {
      setFormData(prev => ({
        ...prev,
        latitude: pickedLocation.lat.toFixed(6),
        longitude: pickedLocation.lon.toFixed(6)
      }));
      // Auto-disable location picker after selecting location
      if (onToggleLocationPicker) {
        onToggleLocationPicker(false);
      }
    }
  }, [pickedLocation, onToggleLocationPicker]);

  const validateForm = () => {
    if (!formData.latitude || !formData.longitude) {
      setError('Latitude and longitude are required');
      return false;
    }

    const lat = parseFloat(formData.latitude);
    const lng = parseFloat(formData.longitude);

    if (isNaN(lat) || lat < -90 || lat > 90) {
      setError('Latitude must be between -90 and 90');
      return false;
    }

    if (isNaN(lng) || lng < -180 || lng > 180) {
      setError('Longitude must be between -180 and 180');
      return false;
    }

    if (formData.affected_population && isNaN(parseInt(formData.affected_population))) {
      setError('Affected population must be a number');
      return false;
    }

    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(false);
    setCredibilityImpact(null);

    try {
      const submitData = {
        ...formData,
        source: 'user_report',
        latitude: parseFloat(formData.latitude),
        longitude: parseFloat(formData.longitude),
        affected_population: formData.affected_population ? parseInt(formData.affected_population) : null
      };

      // Add Firebase ID token if user is authenticated
      if (currentUser) {
        const token = await currentUser.getIdToken();
        submitData.id_token = token;
      }

      const newReport = await createReport(submitData);
      setSuccess(true);

      // Show credibility impact if available
      if (newReport.user_update) {
        setCredibilityImpact(newReport.user_update);
      }

      // Reset form
      setFormData({
        type: 'earthquake',
        severity: 'medium',
        latitude: '',
        longitude: '',
        description: '',
        affected_population: ''
      });

      // Notify parent component with the new report data
      setTimeout(() => {
        onReportSubmitted(newReport);
      }, 1500);

    } catch (err) {
      setError(err.message || 'Failed to submit report. Please try again.');
      console.error('Error submitting report:', err);
    } finally {
      setLoading(false);
    }
  };

  const getSourceCredibilityPercentage = () => {
    if (userProfile) {
      return Math.round((0.5 + userProfile.credibilityScore / 200) * 100);
    }
    return 70; // Default reCAPTCHA-based credibility
  };

  return (
    <div className="report-form">
      <div className="report-form-header">
        <h2>Report a Disaster</h2>
        {onClose && (
          <button
            type="button"
            className="report-form-close-btn"
            onClick={onClose}
            aria-label="Close report form"
          >
            <X size={24} strokeWidth={2} />
          </button>
        )}
      </div>

      {/* Authentication Status */}
      {!currentUser ? (
        <div className="alert alert-info">
          <strong>Not logged in:</strong> Your reports will use default credibility.{' '}
          <Link to="/login" style={{ color: '#1e40af', fontWeight: 'bold' }}>
            Login
          </Link>{' '}
          or{' '}
          <Link to="/register" style={{ color: '#1e40af', fontWeight: 'bold' }}>
            Register
          </Link>{' '}
          to build your reporter credibility!
        </div>
      ) : (
        <div className="credibility-preview">
          <h3>Your Credibility</h3>
          <CredibilityBadge
            level={userProfile?.credibilityLevel || 'Neutral'}
            score={userProfile?.credibilityScore || 50}
            size="medium"
          />
          <p className="credibility-note">
            Your reports carry <strong>{getSourceCredibilityPercentage()}%</strong> source credibility
          </p>
        </div>
      )}

      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      {success && (
        <div className="alert alert-success" style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
          <Check size={18} strokeWidth={2} style={{ marginTop: '2px', flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            Report submitted successfully!
            {credibilityImpact && (
              <div style={{ marginTop: '8px', fontSize: '0.9rem' }}>
                <strong>Credibility Update:</strong>{' '}
                {credibilityImpact.old_credibility} → {credibilityImpact.new_credibility}{' '}
                <span style={{ color: credibilityImpact.delta > 0 ? '#27ae60' : '#e74c3c' }}>
                  ({credibilityImpact.delta > 0 ? '+' : ''}{credibilityImpact.delta})
                </span>
                <br />
                <em>{credibilityImpact.reason}</em>
              </div>
            )}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="type">Disaster Type *</label>
          <select
            id="type"
            name="type"
            value={formData.type}
            onChange={handleChange}
            required
          >
            {disasterTypes.map(type => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="severity">Severity *</label>
          <div className="severity-options">
            {severityLevels.map(level => (
              <label
                key={level.value}
                className={`severity-option ${formData.severity === level.value ? 'selected' : ''}`}
                style={{
                  borderColor: formData.severity === level.value ? level.color : '#ddd',
                  backgroundColor: formData.severity === level.value ? `${level.color}15` : 'white'
                }}
              >
                <input
                  type="radio"
                  name="severity"
                  value={level.value}
                  checked={formData.severity === level.value}
                  onChange={handleChange}
                />
                <span style={{ color: level.color }}>{level.label}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="form-group">
          <label>Location *</label>

          {/* Location Picker Active Hint */}
          {locationPickerEnabled && (
            <div className="location-picker-hint">
              <Map size={16} strokeWidth={2} />
              <span>Tap anywhere on the map above to select location</span>
            </div>
          )}

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="location-button"
              onClick={getCurrentLocation}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Navigation size={18} strokeWidth={2} />
              Use Current Location
            </button>
            {onToggleLocationPicker && (
              <button
                type="button"
                className={`location-button ${locationPickerEnabled ? 'active' : ''}`}
                onClick={() => onToggleLocationPicker(!locationPickerEnabled)}
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                {locationPickerEnabled ? (
                  <>
                    <Check size={18} strokeWidth={2} />
                    Click Map to Select
                  </>
                ) : (
                  <>
                    <Map size={18} strokeWidth={2} />
                    Click on Map
                  </>
                )}
              </button>
            )}
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="latitude">Latitude *</label>
            <input
              type="number"
              id="latitude"
              name="latitude"
              value={formData.latitude}
              onChange={handleChange}
              step="0.000001"
              min="-90"
              max="90"
              placeholder="e.g., 37.7749"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="longitude">Longitude *</label>
            <input
              type="number"
              id="longitude"
              name="longitude"
              value={formData.longitude}
              onChange={handleChange}
              step="0.000001"
              min="-180"
              max="180"
              placeholder="e.g., -122.4194"
              required
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            name="description"
            value={formData.description}
            onChange={handleChange}
            rows="4"
            placeholder="Provide details about the disaster..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="affected_population">Affected Population</label>
          <input
            type="number"
            id="affected_population"
            name="affected_population"
            value={formData.affected_population}
            onChange={handleChange}
            min="0"
            placeholder="Estimated number of people affected"
          />
        </div>

        <button
          type="submit"
          className="submit-button"
          disabled={loading}
        >
          {loading ? 'Submitting...' : 'Submit Report'}
        </button>
      </form>
    </div>
  );
}

export default ReportForm;
