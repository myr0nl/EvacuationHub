import React, { useState, useEffect, useMemo, useCallback, lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Analytics } from '@vercel/analytics/react';
import { SpeedInsights } from '@vercel/speed-insights/react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Map from './components/Map';
import ReportForm from './components/ReportForm';
import DisasterSidebar from './components/DisasterSidebar';
import MobileFilterFAB from './components/MobileFilterFAB';
import SidebarFAB from './components/SidebarFAB';
import RecenterFAB from './components/RecenterFAB';
import FilterBottomSheet from './components/FilterBottomSheet';
import CredibilityBadge from './components/CredibilityBadge';
import AlertNotificationPanel from './components/AlertNotificationPanel';
import AlertSettingsModal from './components/AlertSettingsModal';
import MapSettingsModal from './components/MapSettingsModal';
import SafeRoutePanel from './components/SafeRoutePanel';
import NavigationPanel from './components/NavigationPanel';
import EditReportModal from './components/EditReportModal';
import { getReports, getAllPublicData, deleteReport, pollAIAnalysisStatus } from './services/api';
import { calculateDistance } from './utils/geo';
import { Search, FileText, ShieldCheck, Settings, User, LogOut, X, Shield } from 'lucide-react';
import './styles/design-tokens.css';
import './styles/utilities.css';
import './App.css';

// Lazy load route components for better code splitting
const LoginPage = lazy(() => import('./components/LoginPage'));
const RegisterPage = lazy(() => import('./components/RegisterPage'));
const UserProfile = lazy(() => import('./components/UserProfile'));
const AdminPanel = lazy(() => import('./components/AdminPanel'));

// Loading fallback component for lazy-loaded routes
const LoadingFallback = () => (
  <div style={{
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100vh',
    fontSize: '18px',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    color: '#333',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
  }}>
    <div style={{
      textAlign: 'center',
      padding: '40px',
      background: 'rgba(255, 255, 255, 0.95)',
      borderRadius: '12px',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)'
    }}>
      <div style={{
        fontSize: '48px',
        marginBottom: '16px'
      }}>
        🚨
      </div>
      <div style={{
        fontSize: '20px',
        fontWeight: '500'
      }}>
        Loading...
      </div>
    </div>
  </div>
);

// Suppress ResizeObserver errors and MarkerClusterGroup timing errors (benign React Leaflet issues)
// In development: Log suppressed errors with warning prefix
// In production: Suppress silently
const resizeObserverLoopErr = /ResizeObserver loop completed with undelivered notifications/;
const markerClusterErr = /Cannot read properties of undefined \(reading 'removeObject'\)/;
const originalError = console.error;
console.error = (...args) => {
  const errorMsg = args[0] && args[0].toString ? args[0].toString() : '';
  if (resizeObserverLoopErr.test(errorMsg) || markerClusterErr.test(errorMsg)) {
    // In development mode, log suppressed errors so developers can see them
    if (process.env.NODE_ENV === 'development') {
      console.warn('[Suppressed Benign Error]:', ...args);
    }
    return; // Suppress in both modes, but log in dev
  }
  originalError.call(console, ...args);
};

function MainApp() {
  const { currentUser, userProfile, logout } = useAuth();
  const [reports, setReports] = useState([]);
  const [wildfires, setWildfires] = useState([]);
  const [weatherAlerts, setWeatherAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [hoveredItem, setHoveredItem] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);
  const [filteredDataPoints, setFilteredDataPoints] = useState([]);

  // Proximity alert state
  const [proximityAlerts, setProximityAlerts] = useState([]);
  const [userLocation, setUserLocation] = useState(null);
  const [isAlertSettingsOpen, setIsAlertSettingsOpen] = useState(false);
  const [alertPreferences, setAlertPreferences] = useState(null);
  const [mapCenter, setMapCenter] = useState(null);
  const [showSafeRoutePanel, setShowSafeRoutePanel] = useState(false);
  const [safeZones, setSafeZones] = useState([]);
  const [selectedSafeZone, setSelectedSafeZone] = useState(null); // NEW: Selected safe zone for map highlighting
  const [routes, setRoutes] = useState([]);
  const [selectedRoute, setSelectedRoute] = useState(null);

  // Map settings state
  const [isMapSettingsOpen, setIsMapSettingsOpen] = useState(false);
  const [mapSettings, setMapSettings] = useState(null);
  const [isHeaderVisible, setIsHeaderVisible] = useState(true);
  const [editingReport, setEditingReport] = useState(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 480);

  // Admin state - check if user has admin custom claims
  const [isAdmin, setIsAdmin] = useState(false);

  // Version state
  const [appVersion, setAppVersion] = useState(null);

  // Desktop sidebar state
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // Mobile filter bottom sheet state
  const [isBottomSheetOpen, setIsBottomSheetOpen] = useState(false);
  const [mobileFilters, setMobileFilters] = useState({
    showReports: true,
    showWildfires: true,
    showWeatherAlerts: true
  });

  // Location picker for testing and report form
  const [locationPickerEnabled, setLocationPickerEnabled] = useState(false);
  const [locationError, setLocationError] = useState(null);
  const [isLoadingLocation, setIsLoadingLocation] = useState(false);
  const [pickedLocationForReport, setPickedLocationForReport] = useState(null);

  // Detect mobile viewport
  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 480);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Update header toggle button position based on header height
  useEffect(() => {
    if (!isMobile) return;

    const updateButtonPosition = () => {
      const header = document.querySelector('.app-header');
      const button = document.querySelector('.header-toggle-btn');
      const alertPanel = document.querySelector('.alert-notification-panel');

      if (header && button) {
        if (isHeaderVisible) {
          const headerHeight = header.offsetHeight;
          button.style.top = `${headerHeight}px`;

          // Also position alert notification panel below header
          if (alertPanel) {
            alertPanel.style.top = `${headerHeight + 20}px`; // 20px margin below header
          }
        } else {
          // When header is hidden, move button to top of screen
          button.style.top = '0px';

          // Move alert panel to top when header is hidden
          if (alertPanel) {
            alertPanel.style.top = '20px'; // Small margin from top
          }
        }
      }
    };

    // Update on mount and when header visibility changes
    updateButtonPosition();

    // Also update on window resize (header height may change)
    window.addEventListener('resize', updateButtonPosition);

    // Small delay to ensure header has rendered
    const timer = setTimeout(updateButtonPosition, 100);

    return () => {
      window.removeEventListener('resize', updateButtonPosition);
      clearTimeout(timer);
    };
  }, [isMobile, isHeaderVisible]);

  // OPTIMIZATION: Memoize fetchAllData to prevent recreating the function on every render
  const fetchAllData = useCallback(async () => {
    try {
      setLoading(true);

      // Fetch user reports and public data separately to handle failures gracefully
      let reportsData = [];
      let publicData = { wildfires: [], weather_alerts: [] };

      // Try to fetch reports (may fail if Firebase not configured)
      try {
        reportsData = await getReports();
      } catch (reportsErr) {
        console.warn('Could not fetch user reports (Firebase may not be configured):', reportsErr);
        // Continue without user reports
      }

      // Fetch public data (3 days to match backend cache)
      try {
        publicData = await getAllPublicData({ days: 3, severity: 'Minor' });
      } catch (publicErr) {
        console.error('Error fetching public data:', publicErr);
        setError('Failed to fetch public disaster data.');
      }

      setReports(reportsData);
      setWildfires(publicData.wildfires || []);
      setWeatherAlerts(publicData.weather_alerts || []);

      // Only show error if both failed
      if (reportsData.length === 0 && publicData.wildfires.length === 0 && publicData.weather_alerts.length === 0) {
        setError('No data available. Please check your connection.');
      } else {
        setError(null);
      }
    } catch (err) {
      setError('Failed to fetch data. Please try again later.');
      console.error('Error fetching data:', err);
    } finally {
      setLoading(false);
    }
  }, []); // No dependencies - uses setter functions which are stable

  // OPTIMIZATION: Initial data fetch with proper cleanup
  useEffect(() => {
    fetchAllData();
    // Refresh data every 5 minutes
    const interval = setInterval(fetchAllData, 300000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // PERFORMANCE FIX: Remove fetchAllData dependency to prevent duplicate calls

  // AI polling removed - user refreshes page to see AI analysis results

  // Fetch app version on mount
  useEffect(() => {
    fetch('/version.json')
      .then(res => res.json())
      .then(data => setAppVersion(data))
      .catch(err => console.error('Error fetching version:', err));
  }, []);

  // Check if user has admin custom claims
  useEffect(() => {
    if (currentUser) {
      currentUser.getIdTokenResult().then((idTokenResult) => {
        setIsAdmin(!!idTokenResult.claims.admin);
      }).catch((error) => {
        console.error('Error fetching admin claims:', error);
        setIsAdmin(false);
      });
    } else {
      setIsAdmin(false);
    }
  }, [currentUser]);

  // Function to request location permission (user-initiated)
  const requestLocation = useCallback(() => {
    setIsLoadingLocation(true);
    setLocationError(null);

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setUserLocation({
            lat: position.coords.latitude,
            lon: position.coords.longitude
          });
          setLocationError(null);
          setIsLoadingLocation(false);

          // Start watching location after successful initial request
          const watchId = navigator.geolocation.watchPosition(
            (position) => {
              setUserLocation({
                lat: position.coords.latitude,
                lon: position.coords.longitude
              });
            },
            (error) => console.error('Error watching location:', error),
            { enableHighAccuracy: false, maximumAge: 60000 }
          );

          // Store watchId for cleanup
          window._locationWatchId = watchId;
        },
        (error) => {
          console.error('Error getting location:', error);
          let errorMessage = 'Could not get your location. ';
          if (error.code === 1) {
            errorMessage += 'Please enable location access in your browser settings. Click the lock icon in your address bar and allow location access.';
          } else if (error.code === 2) {
            errorMessage += 'Location services unavailable. Please check: (1) System location services are enabled, (2) Browser has location permission, (3) You have Wi-Fi or GPS enabled. On Mac: System Settings → Privacy & Security → Location Services → ON. Then click the lock icon in your address bar and ensure location is allowed for this site.';
          } else if (error.code === 3) {
            errorMessage += 'Location request timed out. Please try again.';
          }
          setLocationError(errorMessage);
          setIsLoadingLocation(false);
        },
        { enableHighAccuracy: false, timeout: 30000, maximumAge: 10000 }
      );
    } else {
      setLocationError('Geolocation is not supported by your browser. Proximity alerts will not work.');
      setIsLoadingLocation(false);
    }
  }, []);

  // Auto-request user location on mount (both mobile and desktop)
  useEffect(() => {
    // Auto-request location on app load to center map on user
    if (navigator.geolocation) {
      requestLocation();
    }

    return () => {
      if (window._locationWatchId) {
        navigator.geolocation.clearWatch(window._locationWatchId);
      }
    };
  }, [requestLocation]);

  // FIX: Load alert preferences from localStorage for guest users on mount
  useEffect(() => {
    if (!currentUser && !alertPreferences) {
      try {
        const saved = localStorage.getItem('guestAlertPreferences');
        if (saved) {
          const preferences = JSON.parse(saved);
          setAlertPreferences(preferences);
          console.log('Loaded guest preferences from localStorage:', preferences);
        }
      } catch (error) {
        console.error('Error loading preferences from localStorage:', error);
      }
    }
  }, [currentUser, alertPreferences]);

  // Load map settings from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem('mapSettings');
      if (saved) {
        const settings = JSON.parse(saved);
        setMapSettings(settings);
        console.log('Loaded map settings from localStorage:', settings);
      } else {
        // Set default settings
        const defaultSettings = {
          zoom_radius_mi: 20,
          display_radius_mi: 20,
          auto_zoom: false,
          show_all_disasters: false
        };
        setMapSettings(defaultSettings);
      }
    } catch (error) {
      console.error('Error loading map settings from localStorage:', error);
      // Set default settings on error
      setMapSettings({
        zoom_radius_mi: 20,
        display_radius_mi: 20,
        auto_zoom: false,
        show_all_disasters: false
      });
    }
  }, []);

  // OPTIMIZATION: Adaptive polling with debouncing and smart intervals
  useEffect(() => {
    if (!userLocation || !mapSettings) return;

    // Track last location we fetched alerts for
    let lastFetchLocation = { ...userLocation };
    let retryCount = 0;
    let currentIntervalId = null;
    let debounceTimeoutId = null;
    let fetchSequenceNumber = 0; // Track fetch order to ignore stale responses

    // AbortController to cancel in-flight requests on cleanup
    const abortController = new AbortController();

    // ADAPTIVE POLLING: Match backend cache refresh rates
    const POLLING_INTERVALS = {
      high_priority: 15 * 60 * 1000,    // 15 minutes - critical/high alerts nearby
      medium_priority: 30 * 60 * 1000,  // 30 minutes - medium/low alerts nearby
      low_priority: 60 * 60 * 1000      // 60 minutes - no alerts or all distant
    };

    /**
     * Determine optimal polling interval based on proximity alert severity.
     *
     * Adaptive polling strategy:
     * - High priority (15 min): Critical or high severity alerts nearby
     * - Medium priority (30 min): Medium or low severity alerts nearby
     * - Low priority (60 min): No alerts or all distant
     *
     * @param {Array} alerts - Array of proximity alert objects
     * @returns {number} Polling interval in milliseconds
     */
    const getPollingInterval = (alerts) => {
      if (!alerts || alerts.length === 0) {
        return POLLING_INTERVALS.low_priority;
      }

      // Check for critical or high severity alerts
      const hasCriticalOrHigh = alerts.some(
        a => a.alert_severity === 'critical' || a.alert_severity === 'high'
      );

      if (hasCriticalOrHigh) {
        return POLLING_INTERVALS.high_priority;
      }

      // Check for medium severity alerts
      const hasMedium = alerts.some(a => a.alert_severity === 'medium');
      if (hasMedium) {
        return POLLING_INTERVALS.medium_priority;
      }

      return POLLING_INTERVALS.low_priority;
    };

    const fetchProximityAlerts = async (skipDistanceCheck = false) => {
      // NOTE: Radius changes are debounced to prevent spam
      // When proximityRadius changes, debounce timer delays the fetch

      // Increment sequence number for this fetch
      const currentSequence = ++fetchSequenceNumber;

      if (!skipDistanceCheck) {
        // PERFORMANCE: Only fetch if user moved significantly (>0.5 miles)
        const distanceMoved = calculateDistance(
          lastFetchLocation.lat,
          lastFetchLocation.lon,
          userLocation.lat,
          userLocation.lon
        );

        if (distanceMoved < 0.5) {
          // User hasn't moved enough (less than 0.5 miles), skip this fetch
          // NOTE: No need to check coordinate inequality - if distance is small, skip regardless
          return;
        }
      }

      try {
        const headers = {};
        if (currentUser) {
          const token = await currentUser.getIdToken();
          headers['Authorization'] = `Bearer ${token}`;
        }

        // Cap proximity alert radius at 50 miles (backend limit) even if display_radius_mi is higher
        const alertRadius = Math.min(mapSettings.display_radius_mi, 50);

        const response = await fetch(
          `${process.env.REACT_APP_API_URL || 'http://localhost:5001'}/api/alerts/proximity?lat=${userLocation.lat}&lon=${userLocation.lon}&radius=${alertRadius}`,
          {
            headers,
            signal: abortController.signal
          }
        );

        // PERFORMANCE FIX: Handle rate limiting with exponential backoff
        if (response.status === 429) {
          const backoffMs = Math.min(1000 * Math.pow(2, retryCount), 30000);
          retryCount++;
          console.warn(`Proximity alerts rate limited. Backing off for ${backoffMs / 1000}s (retry ${retryCount})`);
          setTimeout(fetchProximityAlerts, backoffMs);
          return;
        }

        if (response.ok) {
          const data = await response.json();

          // RACE CONDITION FIX: Ignore stale responses (out-of-order arrival)
          if (currentSequence !== fetchSequenceNumber) {
            console.log(`Ignoring stale response (sequence ${currentSequence}, current ${fetchSequenceNumber})`);
            return;
          }

          setProximityAlerts(data.alerts || []);

          // Update last fetch location on success
          lastFetchLocation = { ...userLocation };
          retryCount = 0; // Reset retry count on success

          // ADAPTIVE POLLING: Adjust interval based on alert severity
          const newInterval = getPollingInterval(data.alerts);

          // Only restart interval if it changed
          if (currentIntervalId) {
            clearInterval(currentIntervalId);
          }
          currentIntervalId = setInterval(fetchProximityAlerts, newInterval);

          // Log interval for debugging
          const intervalMinutes = Math.round(newInterval / 60000);
          console.log(`Proximity alert polling: ${intervalMinutes} min interval (${data.alerts?.length || 0} alerts)`);
        } else {
          throw new Error(`HTTP ${response.status}`);
        }
      } catch (error) {
        // Gracefully handle AbortError (happens on cleanup/unmount)
        if (error.name === 'AbortError') {
          console.log('Proximity alert fetch aborted (component unmounted)');
          return;
        }
        console.error('Error fetching proximity alerts:', error);
      }
    };

    // DEBOUNCED FETCH: Wait 500ms after radius changes before fetching
    const debouncedFetch = () => {
      if (debounceTimeoutId) {
        clearTimeout(debounceTimeoutId);
      }
      debounceTimeoutId = setTimeout(() => {
        fetchProximityAlerts(true); // Skip distance check for radius changes
      }, 500);
    };

    // Determine if this is a radius change (vs location/user change)
    const isRadiusChange = lastFetchLocation.lat === userLocation.lat &&
                           lastFetchLocation.lon === userLocation.lon;

    if (isRadiusChange) {
      // DEBOUNCE: Radius changes are debounced to prevent slider spam
      debouncedFetch();
    } else {
      // IMMEDIATE: Location or user changes fetch immediately
      fetchProximityAlerts();
    }

    // Pause polling when page is hidden (Page Visibility API)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        // Resume: fetch immediately when tab becomes visible
        fetchProximityAlerts();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    // OPTIMIZATION: Comprehensive cleanup
    return () => {
      abortController.abort(); // Cancel any in-flight requests
      if (currentIntervalId) clearInterval(currentIntervalId);
      if (debounceTimeoutId) clearTimeout(debounceTimeoutId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [userLocation, mapSettings, currentUser]);

  // OPTIMIZATION: Fetch user alert preferences with AbortController cleanup
  useEffect(() => {
    if (!currentUser) return;

    const abortController = new AbortController();

    const fetchPreferences = async () => {
      try {
        const token = await currentUser.getIdToken();
        const response = await fetch(
          `${process.env.REACT_APP_API_URL || 'http://localhost:5001'}/api/alerts/preferences`,
          {
            headers: { 'Authorization': `Bearer ${token}` },
            signal: abortController.signal
          }
        );

        if (response.ok) {
          const prefs = await response.json();
          setAlertPreferences(prefs);

          // MIGRATION: If user has old radius_mi in preferences, migrate to display_radius_mi in map settings
          if (prefs.radius_mi && mapSettings && !mapSettings.display_radius_mi) {
            const newMapSettings = {
              ...mapSettings,
              display_radius_mi: prefs.radius_mi
            };
            setMapSettings(newMapSettings);
            localStorage.setItem('mapSettings', JSON.stringify(newMapSettings));
          }
        }
      } catch (error) {
        if (error.name !== 'AbortError') {
          console.error('Error fetching alert preferences:', error);
        }
      }
    };

    fetchPreferences();

    return () => {
      abortController.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUser]);  // Re-fetch when user logs in/out. mapSettings intentionally excluded to avoid re-running migration

  // OPTIMIZATION: Removed redundant useEffect for filteredDataPoints
  // It's already handled by handleFilterChange in DisasterSidebar

  // OPTIMIZATION: Memoize event handler with useCallback to prevent recreating on every render
  const handleReportSubmitted = useCallback(async (newReport) => {
    setShowForm(false);
    setPickedLocationForReport(null); // Clear picked location marker
    setLocationPickerEnabled(false); // Disable location picker

    // Optimistic UI update: Add new report immediately without full data fetch
    if (newReport && newReport.id) {
      // Backend returns { id, data, confidence }, we need to merge them
      const reportData = {
        ...newReport.data,
        id: newReport.id,
        source: newReport.data.source || 'user_report' // Preserve authenticated source
      };

      console.log('📝 New report submitted:', {
        id: newReport.id,
        ai_status: reportData.ai_analysis_status,
        has_description: !!reportData.description,
        has_image: !!reportData.image_url
      });

      setReports(prevReports => [...prevReports, reportData]);

      // Start polling for AI analysis if applicable
      if (reportData.ai_analysis_status === 'pending') {
        console.log(`🔄 Starting AI analysis polling for report ${newReport.id}`);

        pollAIAnalysisStatus(newReport.id, (updatedReport) => {
          console.log(`✅ AI analysis completed, updating report ${newReport.id}`);

          // Update the report in state with AI results
          setReports(prevReports =>
            prevReports.map(report =>
              report.id === newReport.id
                ? { ...report, ...updatedReport }
                : report
            )
          );
        }).catch(err => {
          console.warn(`AI polling error for report ${newReport.id}:`, err);
        });
      } else {
        console.log(`ℹ️ No AI polling needed for report ${newReport.id}, status: ${reportData.ai_analysis_status}`);
      }
    } else {
      // Fallback: Only refresh user reports if no newReport passed
      try {
        const reportsData = await getReports();
        setReports(reportsData);
      } catch (err) {
        console.error('Error refreshing reports:', err);
      }
    }
  }, []); // No dependencies - uses state updater functions

  // OPTIMIZATION: Memoize filter change handler
  const handleFilterChange = useCallback((filteredData) => {
    // Update the filtered data that will be displayed on the map
    setFilteredDataPoints(filteredData);
  }, []);

  // Apply mobile filters to create filtered data (when on mobile)
  useEffect(() => {
    if (isMobile) {
      // On mobile, use mobile filters instead of sidebar filters
      const mobileFilteredData = [
        ...(mobileFilters.showReports ? reports : []),
        ...(mobileFilters.showWildfires ? wildfires : []),
        ...(mobileFilters.showWeatherAlerts ? weatherAlerts : [])
      ];
      setFilteredDataPoints(mobileFilteredData);
    }
  }, [isMobile, mobileFilters, reports, wildfires, weatherAlerts]);

  // OPTIMIZATION: Memoize hover handler
  const handleItemHover = useCallback((item) => {
    setHoveredItem(item);
  }, []);

  // OPTIMIZATION: Memoize click handler
  const handleItemClick = useCallback((item) => {
    setSelectedItem(item);
    // Could zoom map to item location here
  }, []);

  const handleGetRoute = (disaster) => {
    // TODO: Phase 10 - Implement safe route planning
    console.log('Get route to safe zone for disaster:', disaster);
    alert(`Route planning feature coming soon!\n\nThis will help you navigate safely around:\n${disaster.type || disaster.disaster_type || 'disaster'} at ${disaster.latitude?.toFixed(4)}, ${disaster.longitude?.toFixed(4)}`);
  };

  const handleMarkAddressed = (disaster) => {
    // TODO: Phase 9 - Implement status update/vouching system
    console.log('Mark disaster as addressed:', disaster);
    alert(`Emergency status update feature coming soon!\n\nYou'll be able to vouch that this ${disaster.type || disaster.disaster_type || 'disaster'} has been addressed.`);
  };

  const handleShare = (disaster) => {
    const disasterType = disaster.type || disaster.disaster_type || disaster.event || 'Disaster';
    const location = disaster.location_name || `${disaster.latitude?.toFixed(4)}, ${disaster.longitude?.toFixed(4)}`;
    const shareText = `${disasterType} reported at ${location}`;
    const shareUrl = window.location.href;

    if (navigator.share) {
      // Use native share if available
      navigator.share({
        title: 'Disaster Alert',
        text: shareText,
        url: shareUrl,
      }).catch((error) => {
        if (error.name !== 'AbortError') {
          console.error('Error sharing:', error);
        }
      });
    } else {
      // Fallback to clipboard
      const fullText = `${shareText}\n\nView on Disaster Alert System: ${shareUrl}`;
      navigator.clipboard.writeText(fullText).then(() => {
        alert('Share link copied to clipboard!');
      }).catch((error) => {
        console.error('Error copying to clipboard:', error);
        alert('Could not copy to clipboard. Please share manually.');
      });
    }
  };

  // OPTIMIZATION: Memoize combined data points to avoid recalculation on every render
  // Only recalculates when reports, wildfires, or weatherAlerts change
  const allDataPoints = useMemo(() => [
    ...reports,
    ...wildfires,
    ...weatherAlerts
  ], [reports, wildfires, weatherAlerts]);

  // OPTIMIZATION: Memoize logout handler
  const handleLogout = useCallback(async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout error:', error);
    }
  }, [logout]);

  // OPTIMIZATION: Memoize view alert handler
  const handleViewAlertOnMap = useCallback((alert) => {
    // Center map on alert location
    if (alert.latitude && alert.longitude) {
      setMapCenter({ lat: alert.latitude, lng: alert.longitude });
    }
  }, []);

  // OPTIMIZATION: Memoize dismiss alert handler
  const handleDismissAlert = useCallback(async (alertId) => {
    try {
      if (!currentUser) {
        // For non-authenticated users, just remove from local state
        setProximityAlerts(prev => prev.filter(a => a.id !== alertId));
        return;
      }

      const token = await currentUser.getIdToken();
      const response = await fetch(
        `${process.env.REACT_APP_API_URL || 'http://localhost:5001'}/api/alerts/${alertId}/acknowledge`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );

      if (response.ok) {
        setProximityAlerts(prev => prev.filter(a => a.id !== alertId));
      }
    } catch (error) {
      console.error('Error dismissing alert:', error);
    }
  }, [currentUser]);

  // OPTIMIZATION: Memoize save preferences handler
  const handleSavePreferences = useCallback(async (preferences) => {
    try {
      // For guest users, save preferences locally only
      if (!currentUser) {
        setAlertPreferences(preferences);
        // FIX: Persist to localStorage for guest users
        localStorage.setItem('guestAlertPreferences', JSON.stringify(preferences));
        console.log('Guest preferences saved locally:', preferences);
        return; // Success - no need to save to backend for guests
      }

      // For authenticated users, save to backend
      const token = await currentUser.getIdToken();
      const response = await fetch(
        `${process.env.REACT_APP_API_URL || 'http://localhost:5001'}/api/alerts/preferences`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(preferences)
        }
      );

      if (response.ok) {
        const updated = await response.json();
        setAlertPreferences(updated);
      } else {
        throw new Error('Failed to save preferences');
      }
    } catch (error) {
      console.error('Error saving preferences:', error);
      throw error; // Let the modal handle the error display
    }
  }, [currentUser]);


  // OPTIMIZATION: Memoize routes update handler
  const handleRoutesUpdate = useCallback((newRoutes) => {
    setRoutes(newRoutes);
    // Only clear selection if routes are actually being cleared (empty array)
    // Don't clear when routes are being updated/calculated
    if (newRoutes.length === 0) {
      setSelectedRoute(null);
    }
  }, []);

  // OPTIMIZATION: Memoize route select handler
  const handleRouteSelect = useCallback((route) => {
    setSelectedRoute(route);
    setShowSafeRoutePanel(false); // Close the panel when route is selected
    console.log('Selected route:', route);
  }, []);

  // Clear selected route and related markers
  const handleClearRoute = useCallback(() => {
    setSelectedRoute(null);
    setRoutes([]); // Clear all routes from map
    setSafeZones([]); // Clear safe zone markers
    setSelectedSafeZone(null); // Clear selected safe zone
  }, []);

  // OPTIMIZATION: Memoize safe zones update handler to prevent infinite re-fetching
  const handleSafeZonesUpdate = useCallback((zones) => {
    setSafeZones(zones);
  }, []);

  // OPTIMIZATION: Memoize selected zone change handler to prevent infinite re-fetching
  const handleSelectedZoneChange = useCallback((zone) => {
    setSelectedSafeZone(zone);
  }, []);

  // OPTIMIZATION: Memoize location picked handler
  const handleLocationPicked = useCallback((location) => {
    console.log('Custom location set:', location);

    // If report form is open, use this for the report location
    if (showForm) {
      setPickedLocationForReport(location);
    } else {
      // Otherwise, use it for user location (proximity alerts)
      setUserLocation(location);
      setLocationPickerEnabled(false); // Disable after picking

      // Clear old routes and selected route when location changes
      setRoutes([]);
      setSelectedRoute(null);

      // If safe route panel is open, close it so user can reopen with new location
      setShowSafeRoutePanel(false);
    }
  }, [showForm]);

  // OPTIMIZATION: Memoize test location handler
  const handleSetTestLocation = useCallback(() => {
    setLocationPickerEnabled(true);
    // Close the settings modal so user can see the map
    setIsAlertSettingsOpen(false);
  }, []);

  // OPTIMIZATION: Memoize recenter map handler
  const handleRecenterMap = useCallback(() => {
    if (userLocation) {
      // Force re-center by creating a new object with timestamp
      // This ensures the map centers even if the location hasn't changed
      setMapCenter({
        lat: userLocation.lat,
        lng: userLocation.lon,
        zoom: 12,
        timestamp: Date.now() // Force React to detect change
      });
    }
  }, [userLocation]);

  // OPTIMIZATION: Memoize map settings save handler
  const handleSaveMapSettings = useCallback(async (settings) => {
    try {
      // Create a new object reference to ensure React detects the change
      const newSettings = { ...settings };
      setMapSettings(newSettings);

      // For authenticated users, also save to backend
      if (currentUser) {
        try {
          const token = await currentUser.getIdToken();
          const response = await fetch(
            `${process.env.REACT_APP_API_URL || 'http://localhost:5001'}/api/settings/map`,
            {
              method: 'PUT',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
              },
              body: JSON.stringify(settings)
            }
          );

          if (response.ok) {
            console.log('Map settings saved to backend for authenticated user');
          } else {
            console.warn('Failed to save map settings to backend, using localStorage only');
          }
        } catch (error) {
          console.warn('Error saving map settings to backend:', error);
          // Continue - localStorage save already happened in modal
        }
      }

      console.log('Map settings updated:', newSettings);
    } catch (error) {
      console.error('Error saving map settings:', error);
      throw error; // Let the modal handle the error display
    }
  }, [currentUser]);

  // ADMIN: Delete report handler
  const handleDeleteReport = useCallback(async (reportId) => {
    if (!window.confirm('Are you sure you want to delete this report? This action cannot be undone.')) {
      return;
    }

    try {
      const token = await currentUser.getIdToken();
      const response = await fetch(
        `${process.env.REACT_APP_API_URL || 'http://localhost:5001'}/api/reports/${reportId}`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      if (response.ok) {
        // Remove from local state
        setReports(prev => prev.filter(r => r.id !== reportId));
        alert('Report deleted successfully');
      } else {
        const error = await response.json();
        alert(`Failed to delete report: ${error.message || error.error}`);
      }
    } catch (error) {
      console.error('Error deleting report:', error);
      alert('Error deleting report. Please try again.');
    }
  }, [currentUser]);

  // ADMIN: Edit report handler (opens form with pre-filled data)
  const handleEditReport = useCallback((report) => {
    setEditingReport(report);
  }, []);

  // ADMIN: Save edited report
  const handleSaveEditedReport = useCallback(async (reportId, updates) => {
    try {
      const token = await currentUser.getIdToken();
      const response = await fetch(
        `${process.env.REACT_APP_API_URL || 'http://localhost:5001'}/api/reports/${reportId}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(updates)
        }
      );

      if (response.ok) {
        const result = await response.json();
        // Update local state with the updated report
        setReports(prev => prev.map(r => r.id === reportId ? { ...r, ...result.data } : r));
        alert('Report updated successfully!');
      } else {
        const error = await response.json();
        throw new Error(error.message || error.error || 'Failed to update report');
      }
    } catch (error) {
      console.error('Error saving edited report:', error);
      throw error; // Re-throw so the modal can display the error
    }
  }, [currentUser]);

  // FIX: Filter proximity alerts based on user preferences (severity + disaster types)
  const filteredProximityAlerts = useMemo(() => {
    if (!alertPreferences) {
      // No preferences set yet - return all alerts
      return proximityAlerts;
    }

    const severityFilter = alertPreferences.severity_filter || ['critical', 'high', 'medium', 'low'];
    const disasterTypesFilter = alertPreferences.disaster_types || [];

    return proximityAlerts.filter(alert => {
      // Filter by severity
      const severityMatch = severityFilter.includes(alert.alert_severity?.toLowerCase());

      // Filter by disaster type (if any types are selected)
      const typeMatch = disasterTypesFilter.length === 0 ||
                        disasterTypesFilter.includes(alert.disaster_type?.toLowerCase());

      return severityMatch && typeMatch;
    });
  }, [proximityAlerts, alertPreferences]);

  // OPTIMIZATION: Memoized mobile filter handlers
  const handleMobileFilterChange = useCallback((filterName, value) => {
    setMobileFilters(prev => ({
      ...prev,
      [filterName]: value
    }));
  }, []);

  const handleClearAllFilters = useCallback(() => {
    setMobileFilters({
      showReports: false,
      showWildfires: false,
      showWeatherAlerts: false
    });
  }, []);

  const handleToggleSidebar = useCallback(() => {
    setIsSidebarOpen(prev => !prev);
  }, []);

  const handleOpenBottomSheet = useCallback(() => {
    setIsBottomSheetOpen(true);
  }, []);

  const handleCloseBottomSheet = useCallback(() => {
    setIsBottomSheetOpen(false);
  }, []);

  // Calculate active filter count for FAB badge
  const activeFilterCount = useMemo(() => {
    return [
      mobileFilters.showReports,
      mobileFilters.showWildfires,
      mobileFilters.showWeatherAlerts
    ].filter(Boolean).length;
  }, [mobileFilters]);

  // Calculate counts for bottom sheet
  const filterCounts = useMemo(() => {
    return {
      userReports: reports.length,
      wildfires: wildfires.length,
      weatherAlerts: weatherAlerts.length,
      showing: filteredDataPoints.length,
      total: reports.length + wildfires.length + weatherAlerts.length
    };
  }, [reports.length, wildfires.length, weatherAlerts.length, filteredDataPoints.length]);

  return (
    <div className="App">
      {/* Mobile header toggle button - only show on small screens */}
      {isMobile && (
        <button
          className={`header-toggle-btn ${isHeaderVisible ? 'header-visible' : ''}`}
          onClick={() => setIsHeaderVisible(!isHeaderVisible)}
          aria-label={isHeaderVisible ? 'Hide header' : 'Show header'}
        >
          {isHeaderVisible ? '▲' : '▼'}
        </button>
      )}

      <header className={`app-header ${!isHeaderVisible ? 'hidden' : ''}`}>
        <div className="header-left">
          <div className="brand-container">
            <h1>
              <Search size={28} strokeWidth={2.5} className="brand-icon" aria-hidden="true" />
              DisasterScope
            </h1>
            <p className="hero-tagline">See the full scope of disasters. Navigate to safety.</p>
          </div>
        </div>

        <div className="header-right">
          {currentUser ? (
            <div className="user-menu">
              <div className="user-menu-dropdown">
                <button className="user-menu-button">
                  <CredibilityBadge
                    level={userProfile?.credibilityLevel || 'Neutral'}
                    score={userProfile?.credibilityScore || 50}
                    size="small"
                    inline={true}
                  />
                  <span className="user-name">{userProfile?.displayName || 'User'}</span>
                  <span className="dropdown-arrow">▼</span>
                </button>
                <div className="user-menu-dropdown-content">
                  <Link to="/profile" className="dropdown-item">
                    <User size={18} strokeWidth={2} className="dropdown-icon" />
                    Profile
                  </Link>
                  {isAdmin && (
                    <Link to="/admin" className="dropdown-item">
                      <Shield size={18} strokeWidth={2} className="dropdown-icon" />
                      Admin Panel
                    </Link>
                  )}
                  <button onClick={handleLogout} className="dropdown-item logout-item">
                    <LogOut size={18} strokeWidth={2} className="dropdown-icon" />
                    Logout
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="auth-buttons">
              <Link to="/login" className="login-button">
                Login
              </Link>
              <Link to="/register" className="register-button">
                Register
              </Link>
            </div>
          )}

          {currentUser && (
            <button
              className="btn-secondary btn-light report-button"
              onClick={() => {
                setShowForm(!showForm);
                if (showForm) {
                  // Closing the form - clear picked location marker
                  setPickedLocationForReport(null);
                  setLocationPickerEnabled(false);
                }
              }}
            >
              {showForm ? (
                <>
                  <X size={18} strokeWidth={2} />
                  Close
                </>
              ) : (
                <>
                  <FileText size={18} strokeWidth={2} />
                  Report
                </>
              )}
            </button>
          )}

          {currentUser && (
            <button
              className="btn-secondary btn-success safe-route-button"
              onClick={() => setShowSafeRoutePanel(!showSafeRoutePanel)}
              disabled={!userLocation}
              title={!userLocation ? 'Enable location access to find safe routes' : 'Find safe zones near you'}
            >
              {showSafeRoutePanel ? (
                <>
                  <X size={18} strokeWidth={2} />
                  Close
                </>
              ) : (
                <>
                  <ShieldCheck size={18} strokeWidth={2} />
                  Route
                </>
              )}
            </button>
          )}

          <button
            className="btn-icon settings-button"
            onClick={() => setIsMapSettingsOpen(true)}
            aria-label="Open settings"
            title="Settings"
          >
            <Settings size={20} strokeWidth={2} />
          </button>
        </div>
      </header>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {!currentUser && (
        <div className="guest-banner">
          <div className="guest-banner-content">
            <span className="guest-icon">👋</span>
            <span className="guest-message">
              Browsing as Guest —
              <Link to="/login" className="guest-link">Login</Link> or
              <Link to="/register" className="guest-link">Register</Link> to report disasters and calculate safe routes
            </span>
          </div>
        </div>
      )}

      <div className="app-content">
        {/* Desktop sidebar - hidden on mobile */}
        {(
          <>
            <SidebarFAB
              onClick={handleToggleSidebar}
              isOpen={isSidebarOpen}
            />
            <DisasterSidebar
              reports={reports}
              wildfires={wildfires}
              weatherAlerts={weatherAlerts}
              onFilterChange={handleFilterChange}
              onItemHover={handleItemHover}
              onItemClick={handleItemClick}
              onDeleteReport={handleDeleteReport}
              currentUser={currentUser}
              onGetRoute={handleGetRoute}
              onMarkAddressed={handleMarkAddressed}
              onShare={handleShare}
              isOpen={isSidebarOpen}
            />
          </>
        )}

        {/* Mobile filter FAB - only visible on mobile */}
        <MobileFilterFAB
          activeFilterCount={activeFilterCount}
          onClick={handleOpenBottomSheet}
          isOpen={isBottomSheetOpen}
        />

        {/* Recenter FAB - bottom right corner */}
        <RecenterFAB
          onClick={handleRecenterMap}
          hasLocation={!!userLocation}
        />

        {/* Mobile filter bottom sheet */}
        <FilterBottomSheet
          isOpen={isBottomSheetOpen}
          onClose={handleCloseBottomSheet}
          filters={mobileFilters}
          counts={filterCounts}
          onFilterChange={handleMobileFilterChange}
          onClearAll={handleClearAllFilters}
        />

        {showForm && (
          <div className={`form-container ${isMobile && locationPickerEnabled ? 'location-picker-active' : ''}`}>
            <ReportForm
              onReportSubmitted={handleReportSubmitted}
              locationPickerEnabled={locationPickerEnabled}
              onToggleLocationPicker={setLocationPickerEnabled}
              pickedLocation={pickedLocationForReport}
              onClose={() => {
                setShowForm(false);
                setPickedLocationForReport(null);
                setLocationPickerEnabled(false);
              }}
            />
          </div>
        )}

        <div className="map-container">
          <Map
            dataPoints={filteredDataPoints}
            hoveredItem={hoveredItem}
            selectedItem={selectedItem}
            userLocation={userLocation}
            proximityRadius={mapSettings?.display_radius_mi || 20}
            isAdmin={isAdmin}
            currentUser={currentUser}
            onDeleteReport={handleDeleteReport}
            onEditReport={handleEditReport}
            proximityAlerts={proximityAlerts}
            mapCenter={mapCenter}
            showRadiusCircle={alertPreferences?.show_radius_circle ?? true}
            safeZones={safeZones}
            selectedSafeZone={selectedSafeZone} // NEW: Pass selected safe zone for map highlighting
            routes={routes}
            selectedRoute={selectedRoute}
            locationPickerEnabled={locationPickerEnabled}
            onLocationPicked={handleLocationPicked}
            pickedLocation={pickedLocationForReport} // NEW: Pass picked location for report form marker
            loading={loading} // PERFORMANCE: Pass loading state to show skeleton
            mapSettings={mapSettings} // NEW: Pass map settings for zoom and filtering
            isSidebarOpen={isSidebarOpen} // NEW: Pass sidebar state for zoom control positioning
          />
        </div>
      </div>

      {/* Proximity alert components */}
      {(
        <AlertNotificationPanel
          alerts={filteredProximityAlerts}
          onViewOnMap={handleViewAlertOnMap}
          onDismiss={handleDismissAlert}
        onOpenSettings={() => setIsAlertSettingsOpen(true)}
        userLocation={userLocation}
      />
      )}

      {isAlertSettingsOpen && (
        <AlertSettingsModal
          isOpen={isAlertSettingsOpen}
          onClose={() => setIsAlertSettingsOpen(false)}
          onSave={handleSavePreferences}
          initialPreferences={alertPreferences}
          userLocation={userLocation}
          onEnableLocation={requestLocation}
          onSetTestLocation={handleSetTestLocation}
          locationError={locationError}
          isLoadingLocation={isLoadingLocation}
        />
      )}

      {isMapSettingsOpen && (
        <MapSettingsModal
          isOpen={isMapSettingsOpen}
          onClose={() => setIsMapSettingsOpen(false)}
          onSave={handleSaveMapSettings}
          initialSettings={mapSettings}
        />
      )}

      {/* Edit Report Modal */}
      {editingReport && (
        <EditReportModal
          report={editingReport}
          onClose={() => setEditingReport(null)}
          onSave={handleSaveEditedReport}
          currentUser={currentUser}
        />
      )}

      {/* Safe Route Panel */}
      {showSafeRoutePanel && userLocation && (
        <SafeRoutePanel
          userLocation={userLocation}
          onClose={() => setShowSafeRoutePanel(false)}
          onSafeZonesUpdate={handleSafeZonesUpdate}
          onSelectedZoneChange={handleSelectedZoneChange}
          onRoutesUpdate={handleRoutesUpdate}
          onRouteSelect={handleRouteSelect}
        />
      )}

      {/* Clear Route Button - Show when a route is selected */}
      {selectedRoute && (
        <button
          className="clear-route-btn"
          onClick={handleClearRoute}
          title="Clear selected route"
        >
          ✕ Clear Route
        </button>
      )}

      {/* Turn-by-Turn Instructions - Show when a route is selected */}
      {selectedRoute && selectedRoute.waypoints && selectedRoute.waypoints.length > 0 && (
        <NavigationPanel
          selectedRoute={selectedRoute}
          userLocation={userLocation}
          onExit={handleClearRoute}
          onRecenter={null}
          onOverviewToggle={null}
        />
      )}

      <footer className="app-footer">
        <p>
          User Reports: {reports.length} |
          Wildfires: {wildfires.length} |
          Weather Alerts: {weatherAlerts.length} |
          Total: {allDataPoints.length} |
          Last Updated: {new Date().toLocaleTimeString()}
          {appVersion && ` | v${appVersion.version}`}
        </p>
      </footer>
    </div>
  );
}

function App() {
  return (
    <Router>
      <AuthProvider>
        <Analytics />
        <SpeedInsights />
        <Suspense fallback={<LoadingFallback />}>
          <Routes>
            <Route path="/" element={<MainApp />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/profile" element={<UserProfile />} />
            <Route path="/admin" element={<AdminPanel />} />
          </Routes>
        </Suspense>
      </AuthProvider>
    </Router>
  );
}

export default App;
