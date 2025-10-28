import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getSafeZones, checkZoneSafety, calculateSafeRoutes } from '../services/api';
import RouteComparisonCard from './RouteComparisonCard';
import { UI_ICONS, FACILITY_ICONS } from '../config/icons';
import './SafeRoutePanel.css';

// Constants for safety checking
const SAFETY_CHECK_RADIUS_MI = 10; // Radius in miles for checking threats around safe zones

/**
 * Safe Route Panel - Phase 2 with Route Calculation
 * Displays nearest safe zones, route calculation, and route comparison
 */
function SafeRoutePanel({ userLocation, onClose, onSafeZonesUpdate, onRouteSelect, onRoutesUpdate, onSelectedZoneChange }) {
  const [safeZones, setSafeZones] = useState([]);
  const [selectedZone, setSelectedZone] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [zoneSafety, setZoneSafety] = useState({});

  // Route calculation state
  const [routes, setRoutes] = useState([]);
  const [selectedRoute, setSelectedRoute] = useState(null);
  const [calculating, setCalculating] = useState(false);
  const [calculationError, setCalculationError] = useState(null);

  // Ref to track latest routes for cleanup
  const routesRef = useRef(routes);
  useEffect(() => {
    routesRef.current = routes;
  }, [routes]);

  // Ref to track if we've already fetched safe zones for this location
  const hasFetchedRef = useRef(false);

  /**
   * Open Google Maps with the calculated safe route
   * Uses waypoints to guide Google Maps along our disaster-avoiding route
   */
  const handleOpenGoogleMaps = useCallback((route, destination) => {
    if (!route || !route.geometry || !destination) {
      console.error('Cannot open Google Maps: missing route or destination');
      return;
    }

    try {
      // Downsample geometry to ~25 waypoints (Google Maps has a limit of 25 waypoints)
      // We select evenly spaced points to preserve the route shape
      const totalPoints = route.geometry.length;
      const maxWaypoints = 23; // Leave room for origin and destination
      const step = Math.max(1, Math.floor(totalPoints / maxWaypoints));

      const waypoints = route.geometry
        .filter((_, index) => index % step === 0 && index > 0 && index < totalPoints - 1)
        .slice(0, maxWaypoints) // Ensure we don't exceed limit
        .map(coord => `${coord[1]},${coord[0]}`) // Convert [lon,lat] to lat,lon for Google Maps
        .join('|');

      // Build Google Maps URL
      // Format: https://www.google.com/maps/dir/?api=1&origin=lat,lon&destination=lat,lon&waypoints=lat1,lon1|lat2,lon2&travelmode=driving
      const originCoord = route.geometry[0];
      const destCoord = route.geometry[route.geometry.length - 1];

      const params = new URLSearchParams({
        api: '1',
        origin: `${originCoord[1]},${originCoord[0]}`,
        destination: `${destCoord[1]},${destCoord[0]}`,
        travelmode: 'driving'
      });

      // Add waypoints if we have any
      if (waypoints) {
        params.append('waypoints', waypoints);
      }

      const googleMapsUrl = `https://www.google.com/maps/dir/?${params.toString()}`;

      console.log('🗺️ Opening Google Maps navigation with safe route');
      console.log('📍 Route details:', {
        distance: route.distance_mi?.toFixed(1) + ' mi',
        duration: Math.round(route.duration_seconds / 60) + ' min',
        safetyScore: route.safety_score,
        waypoints: waypoints.split('|').length
      });

      // Open in new tab/window (desktop) or Google Maps app (mobile)
      window.open(googleMapsUrl, '_blank');

    } catch (err) {
      console.error('Error opening Google Maps:', err);
      alert('Failed to open Google Maps. Please try again.');
    }
  }, []);

  // Memoize fetchSafeZones to prevent unnecessary useEffect triggers
  const fetchSafeZones = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const zones = await getSafeZones(
        userLocation.lat,
        userLocation.lon,
        5  // Get 5 nearest zones
      );
      setSafeZones(zones);

      // Notify parent component to show markers on map
      if (onSafeZonesUpdate) {
        onSafeZonesUpdate(zones);
      }

      // Auto-select the nearest zone
      if (zones.length > 0) {
        setSelectedZone(zones[0]);
        // Notify parent component of auto-selected zone for map highlighting
        if (onSelectedZoneChange) {
          onSelectedZoneChange(zones[0]);
        }
        checkSafety(zones[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch safe zones:', err);
      setError('Failed to load safe zones. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [userLocation, onSafeZonesUpdate, onSelectedZoneChange]);

  // Fetch nearest safe zones ONCE when panel opens
  // Only re-fetch if user location changes significantly
  useEffect(() => {
    if (userLocation && userLocation.lat && userLocation.lon && !hasFetchedRef.current) {
      // Clear old routes and selected zone
      setRoutes([]);
      setSelectedZone(null);
      setCalculating(false);
      setCalculationError(null);

      // Clear routes on map
      if (onRoutesUpdate) {
        onRoutesUpdate([]);
      }

      // Fetch new safe zones for the location
      fetchSafeZones();
      hasFetchedRef.current = true;
    }
  }, [userLocation, fetchSafeZones, onRoutesUpdate]);

  // Reset hasFetched flag when panel unmounts
  useEffect(() => {
    return () => {
      hasFetchedRef.current = false;
    };
  }, []);

  // Cleanup when panel unmounts (closes)
  // Only run cleanup on unmount, not when routes change
  useEffect(() => {
    return () => {
      // Panel is closing - decide what to clean up using ref value
      // If no routes were calculated, clear safe zone markers
      // If routes exist, keep everything visible for navigation
      if (routesRef.current.length === 0) {
        // No routes calculated - user just browsed safe zones
        // Clear the safe zone markers
        if (onSafeZonesUpdate) {
          onSafeZonesUpdate([]);
        }
        // Clear selected zone highlight
        if (onSelectedZoneChange) {
          onSelectedZoneChange(null);
        }
      }
      // If routes exist, keep them visible - user is navigating
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty deps - only run on unmount

  const checkSafety = async (zoneId) => {
    try {
      const safety = await checkZoneSafety(zoneId, SAFETY_CHECK_RADIUS_MI);
      setZoneSafety(prev => ({ ...prev, [zoneId]: safety }));
    } catch (err) {
      console.error(`Failed to check safety for ${zoneId}:`, err);
      // Store error state for this zone so user knows check failed
      setZoneSafety(prev => ({
        ...prev,
        [zoneId]: { error: 'Failed to check safety status' }
      }));
    }
  };

  const handleZoneClick = (zone) => {
    setSelectedZone(zone);
    // Notify parent component of selected zone for map highlighting
    if (onSelectedZoneChange) {
      onSelectedZoneChange(zone);
    }
    // Clear previous routes when selecting a new zone
    setRoutes([]);
    setSelectedRoute(null);
    setCalculationError(null);

    if (!zoneSafety[zone.id]) {
      checkSafety(zone.id);
    }
  };

  const handleCalculateRoutes = async () => {
    if (!selectedZone || !userLocation) {
      setCalculationError('Missing location information');
      return;
    }

    setCalculating(true);
    setCalculationError(null);

    try {
      const response = await calculateSafeRoutes({
        origin: {
          lat: userLocation.lat,
          lon: userLocation.lon
        },
        destination: {
          lat: selectedZone.latitude,
          lon: selectedZone.longitude
        },
        safe_zone_id: selectedZone.id,
        avoid_disasters: true,
        alternatives: 3
      });

      // Store routes in state
      const routes = response.routes || [];
      setRoutes(routes);

      // Notify parent component to show routes on map
      if (onRoutesUpdate && routes && routes.length > 0) {
        console.log('✅ Calling onRoutesUpdate with', routes.length, 'routes');
        onRoutesUpdate(routes);
      } else {
        console.warn('No routes to display');
      }

      console.log('Routes calculated successfully:', routes.length, 'routes found');
    } catch (err) {
      console.error('Failed to calculate routes:', err);
      setCalculationError(err.message || 'Failed to calculate routes. Please try again.');
    } finally {
      setCalculating(false);
    }
  };

  const handleRouteSelection = (route) => {
    setSelectedRoute(route);

    // Notify parent component that a route was selected
    if (onRouteSelect) {
      onRouteSelect(route);
    }
  };

  const getZoneIcon = (type) => {
    // Map zone types to facility icons from config
    const IconComponent = FACILITY_ICONS[type] || UI_ICONS.mapPin;
    return <IconComponent size={20} strokeWidth={2} />;
  };

  const formatZoneType = (type) => {
    return type.split('_').map(word =>
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };

  const getStatusColor = (status) => {
    const colors = {
      'open': '#10b981',
      'closed': '#ef4444',
      'at_capacity': '#f59e0b',
      'damaged': '#6b7280',
      'unknown': '#9ca3af'
    };
    return colors[status] || colors['unknown'];
  };

  const CloseIcon = UI_ICONS.close;
  const WarningIcon = UI_ICONS.warning;
  const MapPinIcon = UI_ICONS.mapPin;
  const MapIcon = UI_ICONS.map;
  const CheckIcon = UI_ICONS.check;
  const PhoneIcon = UI_ICONS.phone;
  const SafestIcon = UI_ICONS.safest;

  return (
    <div className="safe-route-panel">
      <div className="panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <SafestIcon size={24} strokeWidth={2} />
          <h2>Find Safe Zone</h2>
        </div>
        <button onClick={onClose} className="close-btn" aria-label="Close panel">
          <CloseIcon size={20} strokeWidth={2} />
        </button>
      </div>

      {error && (
        <div className="error-message" role="alert" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <WarningIcon size={18} strokeWidth={2} />
          <span>{error}</span>
        </div>
      )}

      {loading && (
        <div className="loading-message">
          Loading nearest safe zones...
        </div>
      )}

      {!loading && safeZones.length === 0 && !error && (
        <div className="no-zones-message">
          No safe zones found within 50 mi.
        </div>
      )}

      {!loading && safeZones.length > 0 && (
        <>
          <div className="safe-zones-section">
            <h3>Nearest Safe Zones ({safeZones.length})</h3>
            <div className="safe-zones-list">
              {safeZones.map(zone => (
                <div
                  key={zone.id}
                  className={`safe-zone-card ${selectedZone?.id === zone.id ? 'selected' : ''}`}
                  onClick={() => handleZoneClick(zone)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault(); // Prevent page scroll on Space
                      handleZoneClick(zone);
                    }
                  }}
                >
                  {selectedZone?.id === zone.id && (
                    <div className="zone-selected-indicator">
                      <CheckIcon size={18} strokeWidth={2} />
                    </div>
                  )}
                  <div className="zone-icon">{getZoneIcon(zone.type)}</div>
                  <div className="zone-info">
                    <h4>{zone.name}</h4>
                    <p className="zone-type">{formatZoneType(zone.type)}</p>
                    <p className="zone-distance" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <MapPinIcon size={16} strokeWidth={2} />
                      <span>{zone.distance_from_user_mi.toFixed(1)} mi away</span>
                    </p>
                    <div
                      className="zone-status-badge"
                      style={{ backgroundColor: getStatusColor(zone.operational_status) }}
                    >
                      {zone.operational_status.toUpperCase()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {selectedZone && (
            <div className="zone-details-section">
              <h3>Zone Details</h3>
              <div className="zone-details">
                <div className="detail-row">
                  <span className="detail-label">Address:</span>
                  <span className="detail-value">{selectedZone.address}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Capacity:</span>
                  <span className="detail-value">{selectedZone.capacity?.toLocaleString()} people</span>
                </div>
                {selectedZone.amenities && selectedZone.amenities.length > 0 && (
                  <div className="detail-row">
                    <span className="detail-label">Amenities:</span>
                    <span className="detail-value">
                      {selectedZone.amenities.join(', ')}
                    </span>
                  </div>
                )}
                {selectedZone.contact && selectedZone.contact.phone && (
                  <div className="detail-row">
                    <span className="detail-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <PhoneIcon size={16} strokeWidth={2} />
                      <span>Contact:</span>
                    </span>
                    <span className="detail-value">{selectedZone.contact.phone}</span>
                  </div>
                )}

                <div className="safety-status">
                  <h4>Safety Status</h4>
                  {!zoneSafety[selectedZone.id] ? (
                    <div className="safety-loading" style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#6b7280' }}>
                      <span>Checking for nearby threats...</span>
                    </div>
                  ) : zoneSafety[selectedZone.id].error ? (
                    <div className="safety-error" style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                      <CloseIcon size={18} strokeWidth={2} style={{ flexShrink: 0, marginTop: '2px' }} />
                      <div>
                        {zoneSafety[selectedZone.id].error}
                        <br />
                        <small>Unable to verify current threats</small>
                      </div>
                    </div>
                  ) : zoneSafety[selectedZone.id].safe ? (
                    <div className="safety-safe" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <CheckIcon size={18} strokeWidth={2} />
                      <span>Zone is currently safe</span>
                    </div>
                  ) : (
                    <div className="safety-unsafe" style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                      <WarningIcon size={18} strokeWidth={2} style={{ flexShrink: 0, marginTop: '2px' }} />
                      <div>
                        {zoneSafety[selectedZone.id].threats.length} active threat(s) nearby
                        <br />
                        <small>
                          Nearest threat: {zoneSafety[selectedZone.id].distance_to_nearest_threat_mi?.toFixed(1)} mi away
                        </small>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Calculate Routes Button - Show only when no routes calculated */}
              {routes.length === 0 && (
                <div className="action-buttons">
                  <button
                    className="primary-btn"
                    onClick={handleCalculateRoutes}
                    disabled={calculating}
                  >
                    {calculating ? 'Calculating...' : 'Calculate Routes'}
                  </button>
                  {calculationError && (
                    <div className="error-message" role="alert" style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <WarningIcon size={18} strokeWidth={2} />
                      <span>{calculationError}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Routes Display Section */}
              {routes.length > 0 && (
                <div className="routes-section">
                  <h3>Route Options ({routes.length})</h3>

                  {/* Display warning if any route has a warning (e.g., too many polygons) */}
                  {routes.some(r => r.warning) && (
                    <div className="route-warning-banner" style={{
                      backgroundColor: '#fff3cd',
                      border: '1px solid #ffc107',
                      borderRadius: '8px',
                      padding: '12px 16px',
                      marginBottom: '16px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}>
                      <WarningIcon size={20} strokeWidth={2} style={{ flexShrink: 0, color: '#856404' }} />
                      <span style={{ flex: 1, color: '#856404', fontSize: '14px' }}>
                        {routes.find(r => r.warning)?.warning}
                      </span>
                    </div>
                  )}

                  <div className="routes-list">
                    {routes.map((route, index) => (
                      <RouteComparisonCard
                        key={route.route_id || index}
                        route={route}
                        index={index}
                        onSelect={handleRouteSelection}
                        isSelected={selectedRoute && selectedRoute.route_id === route.route_id}
                      />
                    ))}
                  </div>

                  {/* Navigation Buttons - Show when a route is selected */}
                  {selectedRoute && (
                    <div className="action-buttons" style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      <button
                        className="primary-btn google-maps-btn"
                        onClick={() => handleOpenGoogleMaps(selectedRoute, selectedZone)}
                        style={{
                          background: 'linear-gradient(135deg, #4285f4 0%, #2a75f3 100%)',
                          fontSize: '1.05rem',
                          padding: '0.85rem 1.5rem',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '10px',
                          boxShadow: '0 4px 12px rgba(66, 133, 244, 0.3)'
                        }}
                        title="Open this safe route in Google Maps for turn-by-turn navigation"
                      >
                        <MapIcon size={22} strokeWidth={2} />
                        <span>Navigate with Google Maps</span>
                      </button>

                      <button
                        className="secondary-btn"
                        onClick={() => onRouteSelect && onRouteSelect(selectedRoute)}
                        style={{
                          background: 'white',
                          color: '#374151',
                          border: '2px solid #d1d5db',
                          fontSize: '0.95rem',
                          padding: '0.65rem 1.25rem'
                        }}
                        title="View turn-by-turn directions within the app"
                      >
                        View Directions (In-App Preview)
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default SafeRoutePanel;
