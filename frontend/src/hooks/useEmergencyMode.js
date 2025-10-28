import { useState, useEffect, useMemo, useCallback } from 'react';

/**
 * Emergency mode activation thresholds
 */
const EMERGENCY_THRESHOLDS = {
  DISTANCE_MI: 10, // Auto-activate within 10 miles
  SEVERITY_LEVELS: ['critical', 'high'], // Only critical/high alerts trigger emergency mode
};

/**
 * Custom hook for managing emergency mode state
 *
 * Emergency mode auto-activates when:
 * - User is on a mobile device
 * - Critical or high severity alert within 10 miles
 *
 * Can be manually overridden by user toggle
 *
 * @param {{
 *   proximityAlerts?: Array<{
 *     distance_mi: number,
 *     alert_severity: 'critical' | 'high' | 'medium' | 'low',
 *     disaster_type: string,
 *     latitude: number,
 *     longitude: number
 *   }>,
 *   userLocation?: { lat: number, lon: number } | null,
 *   isMobile?: boolean
 * }} params
 *
 * @returns {{
 *   isEmergencyMode: boolean,
 *   isAutoActivated: boolean,
 *   toggleEmergencyMode: () => void,
 *   resetEmergencyMode: () => void,
 *   nearestCriticalAlert: object | null
 * }}
 *
 * @example
 * const { isEmergencyMode, toggleEmergencyMode, nearestCriticalAlert } = useEmergencyMode({
 *   proximityAlerts,
 *   userLocation,
 *   isMobile
 * });
 */
export const useEmergencyMode = ({
  proximityAlerts = [],
  userLocation = null,
  isMobile = false,
} = {}) => {
  // Track manual override state
  const [manualOverride, setManualOverride] = useState(null); // null = auto, true = force on, false = force off

  /**
   * Check if there are critical/high alerts within threshold distance
   */
  const criticalNearbyAlerts = useMemo(() => {
    if (!Array.isArray(proximityAlerts) || proximityAlerts.length === 0) {
      return [];
    }

    return proximityAlerts.filter((alert) => {
      // Validate alert object
      if (!alert || typeof alert !== 'object') return false;

      const distance = alert.distance_mi;
      const severity = alert.alert_severity;

      // Check if severity is critical or high
      const isCriticalSeverity = EMERGENCY_THRESHOLDS.SEVERITY_LEVELS.includes(
        severity?.toLowerCase()
      );

      // Check if within distance threshold
      const isWithinThreshold =
        typeof distance === 'number' &&
        distance <= EMERGENCY_THRESHOLDS.DISTANCE_MI;

      return isCriticalSeverity && isWithinThreshold;
    });
  }, [proximityAlerts]);

  /**
   * Find the nearest critical alert
   */
  const nearestCriticalAlert = useMemo(() => {
    if (criticalNearbyAlerts.length === 0) return null;

    // Sort by distance and return closest
    const sorted = [...criticalNearbyAlerts].sort(
      (a, b) => (a.distance_mi || Infinity) - (b.distance_mi || Infinity)
    );

    return sorted[0] || null;
  }, [criticalNearbyAlerts]);

  /**
   * Determine if emergency mode should be auto-activated
   */
  const shouldAutoActivate = useMemo(() => {
    // Only auto-activate on mobile devices
    if (!isMobile) return false;

    // Need user location for distance calculations
    if (!userLocation || typeof userLocation.lat !== 'number' || typeof userLocation.lon !== 'number') {
      return false;
    }

    // Auto-activate if there are critical nearby alerts
    return criticalNearbyAlerts.length > 0;
  }, [isMobile, userLocation, criticalNearbyAlerts]);

  /**
   * Calculate final emergency mode state
   */
  const isEmergencyMode = useMemo(() => {
    // Manual override takes precedence
    if (manualOverride !== null) {
      return manualOverride;
    }

    // Otherwise use auto-activation logic
    return shouldAutoActivate;
  }, [manualOverride, shouldAutoActivate]);

  /**
   * Toggle emergency mode (manual override)
   */
  const toggleEmergencyMode = useCallback(() => {
    setManualOverride((prev) => {
      // If currently in auto mode, toggle based on current state
      if (prev === null) {
        return !shouldAutoActivate;
      }
      // If manually set, toggle the override
      return !prev;
    });
  }, [shouldAutoActivate]);

  /**
   * Reset to auto mode (clear manual override)
   */
  const resetEmergencyMode = useCallback(() => {
    setManualOverride(null);
  }, []);

  /**
   * Auto-reset manual override when conditions change significantly
   * This prevents users from being stuck in wrong mode after disaster moves away
   */
  useEffect(() => {
    // If user manually forced emergency mode OFF, but critical alert gets closer, reset to auto
    if (manualOverride === false && shouldAutoActivate) {
      const closestDistance = nearestCriticalAlert?.distance_mi;
      // Reset if critical alert within 5 miles (immediate danger)
      if (closestDistance && closestDistance <= 5) {
        setManualOverride(null);
      }
    }

    // If user manually forced emergency mode ON, but all critical alerts cleared, reset to auto after delay
    if (manualOverride === true && !shouldAutoActivate) {
      const resetTimer = setTimeout(() => {
        setManualOverride(null);
      }, 60000); // Reset after 1 minute of no critical alerts

      return () => clearTimeout(resetTimer);
    }
  }, [manualOverride, shouldAutoActivate, nearestCriticalAlert]);

  return {
    isEmergencyMode,
    isAutoActivated: manualOverride === null && shouldAutoActivate,
    toggleEmergencyMode,
    resetEmergencyMode,
    nearestCriticalAlert,
    criticalAlertCount: criticalNearbyAlerts.length,
  };
};

export default useEmergencyMode;
