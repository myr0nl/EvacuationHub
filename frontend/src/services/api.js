import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout (AI processing can take 15-20s)
});

// Add request interceptor for authentication token
api.interceptors.request.use(
  async (config) => {
    console.log(`API Request: ${config.method.toUpperCase()} ${config.url}`);

    // Add authentication token if available
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    console.log(`API Response: ${response.status} ${response.config.url}`);
    return response;
  },
  (error) => {
    console.error('API Response Error:', error.response || error);

    if (error.response) {
      // Server responded with error status
      const message = error.response.data?.message || error.response.data?.error || 'Server error occurred';
      throw new Error(message);
    } else if (error.request) {
      // Request made but no response
      throw new Error('No response from server. Please check if the backend is running.');
    } else {
      // Request setup error
      throw new Error(error.message || 'Request failed');
    }
  }
);

/**
 * Fetch all disaster reports
 * @returns {Promise<Array>} Array of disaster report objects
 */
export const getReports = async () => {
  try {
    const response = await api.get('/api/reports');
    return response.data;
  } catch (error) {
    console.error('Error fetching reports:', error);
    throw error;
  }
};

/**
 * Fetch a single disaster report by ID
 * @param {number} id - Report ID
 * @returns {Promise<Object>} Disaster report object
 */
export const getReportById = async (id) => {
  try {
    const response = await api.get(`/api/reports/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching report ${id}:`, error);
    throw error;
  }
};

/**
 * Create a new disaster report
 * @param {Object} reportData - Report data
 * @param {string} reportData.disaster_type - Type of disaster
 * @param {string} reportData.severity - Severity level
 * @param {number} reportData.latitude - Latitude coordinate
 * @param {number} reportData.longitude - Longitude coordinate
 * @param {string} [reportData.description] - Optional description
 * @param {number} [reportData.affected_population] - Optional affected population count
 * @param {string} [reportData.id_token] - Firebase ID token for authenticated users
 * @returns {Promise<Object>} Created report object
 */
export const createReport = async (reportData) => {
  try {
    const response = await api.post('/api/reports', reportData);
    const report = response.data;

    // Trigger background AI analysis if applicable (don't await - fire and forget)
    if (report.data?.ai_analysis_status === 'pending') {
      enhanceReportWithAI(report.id).catch(err =>
        console.warn('Background AI enhancement failed:', err)
      );
    }

    return report;
  } catch (error) {
    console.error('Error creating report:', error);
    throw error;
  }
};

/**
 * Trigger AI analysis for a report (background operation)
 * @param {string} reportId - Report ID
 * @returns {Promise<Object>} AI enhancement result
 */
export const enhanceReportWithAI = async (reportId) => {
  try {
    const response = await api.post(`/api/reports/${reportId}/enhance-ai`);
    return response.data;
  } catch (error) {
    console.error(`Error enhancing report ${reportId} with AI:`, error);
    throw error;
  }
};

/**
 * Poll for AI analysis completion on a report
 * Checks report status every 3 seconds until AI analysis completes or timeout (45s)
 * @param {string} reportId - Report ID to check
 * @param {function} onUpdate - Callback function called with updated report data when AI completes
 * @param {number} maxAttempts - Maximum number of polling attempts (default 15 = 45s)
 * @returns {Promise<Object|null>} Updated report object or null if timeout/error
 */
export const pollAIAnalysisStatus = async (reportId, onUpdate, maxAttempts = 15) => {
  let attempts = 0;

  const checkStatus = async () => {
    attempts++;

    try {
      const report = await getReportById(reportId);

      // Check if AI analysis is complete
      const aiStatus = report.ai_analysis_status;

      if (aiStatus === 'completed') {
        console.log(`✅ AI analysis completed for report ${reportId}`);
        if (onUpdate) onUpdate(report);
        return report;
      } else if (aiStatus === 'failed') {
        console.warn(`❌ AI analysis failed for report ${reportId}`);
        if (onUpdate) onUpdate(report);
        return report;
      } else if (aiStatus === 'not_applicable') {
        console.log(`ℹ️ AI analysis not applicable for report ${reportId}`);
        return null;
      }

      // Still processing, check again if within max attempts
      if (attempts < maxAttempts) {
        console.log(`🔄 AI analysis still processing for report ${reportId} (attempt ${attempts}/${maxAttempts})`);
        await new Promise(resolve => setTimeout(resolve, 3000)); // Wait 3 seconds
        return checkStatus();
      } else {
        console.warn(`⏱️ AI analysis polling timeout for report ${reportId} after ${attempts} attempts`);
        return null;
      }
    } catch (error) {
      console.error(`Error polling AI status for report ${reportId}:`, error);
      return null;
    }
  };

  return checkStatus();
};

/**
 * Update an existing disaster report
 * @param {number} id - Report ID
 * @param {Object} reportData - Updated report data
 * @returns {Promise<Object>} Updated report object
 */
export const updateReport = async (id, reportData) => {
  try {
    const response = await api.put(`/api/reports/${id}`, reportData);
    return response.data;
  } catch (error) {
    console.error(`Error updating report ${id}:`, error);
    throw error;
  }
};

/**
 * Delete a disaster report
 * @param {number} id - Report ID
 * @returns {Promise<Object>} Deletion confirmation
 */
export const deleteReport = async (id) => {
  try {
    const response = await api.delete(`/api/reports/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Error deleting report ${id}:`, error);
    throw error;
  }
};

/**
 * Bulk delete stale reports older than specified hours
 * @param {number} maxAgeHours - Maximum age in hours (default: 48)
 * @returns {Promise<Object>} Deletion summary { deleted_count, deleted_ids, max_age_hours }
 */
export const deleteStaleReports = async (maxAgeHours = 48) => {
  try {
    const response = await api.post('/api/reports/bulk/delete-stale', {
      max_age_hours: maxAgeHours
    });
    return response.data;
  } catch (error) {
    console.error(`Error deleting stale reports:`, error);
    throw error;
  }
};

/**
 * Filter reports by disaster type
 * @param {string} disasterType - Type of disaster
 * @returns {Promise<Array>} Filtered array of reports
 */
export const getReportsByType = async (disasterType) => {
  try {
    const response = await api.get(`/api/reports?type=${disasterType}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching reports by type ${disasterType}:`, error);
    throw error;
  }
};

/**
 * Filter reports by severity
 * @param {string} severity - Severity level
 * @returns {Promise<Array>} Filtered array of reports
 */
export const getReportsBySeverity = async (severity) => {
  try {
    const response = await api.get(`/api/reports?severity=${severity}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching reports by severity ${severity}:`, error);
    throw error;
  }
};

/**
 * Fetch wildfire data from NASA FIRMS
 * @param {number} days - Number of days of data (1-10)
 * @returns {Promise<Array>} Array of wildfire data points
 */
export const getWildfires = async (days = 3) => {
  try {
    const response = await api.get(`/api/public-data/wildfires?days=${days}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching wildfire data:', error);
    throw error;
  }
};

/**
 * Fetch weather alerts from NOAA
 * @param {string} severity - Minimum severity level (Extreme, Severe, Moderate, Minor)
 * @returns {Promise<Array>} Array of weather alert data points
 */
export const getWeatherAlerts = async (severity = 'Minor') => {
  try {
    const response = await api.get(`/api/public-data/weather-alerts?severity=${severity}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching weather alerts:', error);
    throw error;
  }
};

/**
 * Fetch all public data sources
 * @param {Object} options - Query options
 * @param {number} options.days - Days of wildfire data
 * @param {string} options.severity - Minimum severity for weather alerts
 * @returns {Promise<Object>} Object containing wildfires and weather_alerts arrays
 */
export const getAllPublicData = async ({ days = 3, severity = 'Minor' } = {}) => {
  try {
    const response = await api.get(`/api/public-data/all?days=${days}&severity=${severity}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching public data:', error);
    throw error;
  }
};

/**
 * Get user profile (authenticated)
 * @param {string} token - Firebase ID token
 * @returns {Promise<Object>} User profile object
 */
export const getUserProfile = async (token) => {
  try {
    const response = await api.get(`/api/auth/profile`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching user profile:', error);
    throw error;
  }
};

/**
 * Register a new user
 * @param {Object} userData - User registration data
 * @param {string} userData.email - User email
 * @param {string} userData.password - User password
 * @param {string} [userData.display_name] - Optional display name
 * @returns {Promise<Object>} User profile object
 */
export const registerUser = async (userData) => {
  try {
    const response = await api.post('/api/auth/register', userData);
    return response.data;
  } catch (error) {
    console.error('Error registering user:', error);
    throw error;
  }
};

/**
 * Login user
 * @param {string} idToken - Firebase ID token
 * @returns {Promise<Object>} User profile object
 */
export const loginUser = async (idToken) => {
  try {
    const response = await api.post('/api/auth/login', { id_token: idToken });
    return response.data;
  } catch (error) {
    console.error('Error logging in user:', error);
    throw error;
  }
};

// ================================================================================
// PHASE 10: SAFE ROUTE NAVIGATION - SAFE ZONE API METHODS
// ================================================================================

/**
 * Get nearest safe zones to user location
 * @param {number} lat - User latitude
 * @param {number} lon - User longitude
 * @param {number} limit - Maximum number of zones to return (default 5)
 * @param {number} maxDistanceKm - Maximum search distance in km (default 100)
 * @param {string} type - Optional zone type filter
 * @returns {Promise<Array>} Array of safe zones sorted by distance
 */
export const getSafeZones = async (lat, lon, limit = 5, maxDistanceKm = 100, type = null) => {
  try {
    let url = `/api/safe-zones?lat=${lat}&lon=${lon}&limit=${limit}&max_distance_mi=${maxDistanceKm}`;
    if (type) {
      url += `&type=${type}`;
    }
    const response = await api.get(url);
    return response.data;
  } catch (error) {
    console.error('Error fetching safe zones:', error);
    throw error;
  }
};

/**
 * Get details of a specific safe zone
 * @param {string} zoneId - Safe zone ID
 * @returns {Promise<Object>} Safe zone details
 */
export const getSafeZoneDetails = async (zoneId) => {
  try {
    const response = await api.get(`/api/safe-zones/${zoneId}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching safe zone ${zoneId}:`, error);
    throw error;
  }
};

/**
 * Check if a safe zone is currently safe (no nearby disasters)
 * @param {string} zoneId - Safe zone ID
 * @param {number} threatRadiusKm - Threat detection radius (default 5km)
 * @returns {Promise<Object>} Safety status with threats
 */
export const checkZoneSafety = async (zoneId, threatRadiusKm = 5) => {
  try {
    const response = await api.get(`/api/safe-zones/${zoneId}/status?threat_radius_mi=${threatRadiusKm}`);
    return response.data;
  } catch (error) {
    console.error(`Error checking zone safety for ${zoneId}:`, error);
    throw error;
  }
};

/**
 * Calculate safe routes between origin and destination, avoiding disasters
 * @param {Object} params - Route calculation parameters
 * @param {Object} params.origin - Origin coordinates {lat, lon}
 * @param {number} params.origin.lat - Origin latitude
 * @param {number} params.origin.lon - Origin longitude
 * @param {Object} params.destination - Destination coordinates {lat, lon}
 * @param {number} params.destination.lat - Destination latitude
 * @param {number} params.destination.lon - Destination longitude
 * @param {string} [params.safe_zone_id] - Optional safe zone ID to route to
 * @param {boolean} [params.avoid_disasters=true] - Whether to avoid disaster areas
 * @param {number} [params.alternatives=3] - Number of alternative routes (1-5)
 * @returns {Promise<Object>} Route calculation response with routes, avoided disasters, and recommendations
 */
export const calculateSafeRoutes = async (params) => {
  try {
    const response = await api.post('/api/routes/calculate', params);
    // Fix: Parse JSON string response if needed
    const data = typeof response.data === 'string' ? JSON.parse(response.data) : response.data;

    // DEBUG: Log first route to check if waypoints are present
    if (data && data.routes && data.routes.length > 0) {
      console.log('🔍 First route from API:', data.routes[0]);
      console.log('🔍 Waypoints present?', !!data.routes[0].waypoints);
      console.log('🔍 Waypoints count:', data.routes[0].waypoints?.length || 0);
    }

    return data;
  } catch (error) {
    console.error('Error calculating safe routes:', error);
    throw error;
  }
};

/**
 * Get detailed information about a specific route
 * @param {string} routeId - Route ID
 * @returns {Promise<Object>} Route details
 */
export const getRouteDetails = async (routeId) => {
  try {
    const response = await api.get(`/api/routes/${routeId}/details`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching route details for ${routeId}:`, error);
    throw error;
  }
};

export default api;
