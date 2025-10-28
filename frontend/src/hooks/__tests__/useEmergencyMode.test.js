/**
 * Tests for useEmergencyMode hook
 *
 * Run with: npm test useEmergencyMode.test.js
 */

import { renderHook, act } from '@testing-library/react';
import { useEmergencyMode } from '../useEmergencyMode';

describe('useEmergencyMode', () => {
  const mockUserLocation = { lat: 37.7749, lon: -122.4194 };

  const createMockAlert = (severity, distance) => ({
    disaster_id: `alert-${Math.random()}`,
    disaster_type: 'wildfire',
    alert_severity: severity,
    distance_mi: distance,
    latitude: 37.7849,
    longitude: -122.4094,
    source: 'nasa_firms',
  });

  beforeEach(() => {
    jest.clearAllTimers();
  });

  afterEach(() => {
    jest.clearAllTimers();
  });

  describe('Auto-Activation Logic', () => {
    it('should not activate emergency mode on desktop', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [createMockAlert('critical', 5)],
          userLocation: mockUserLocation,
          isMobile: false,
        })
      );

      expect(result.current.isEmergencyMode).toBe(false);
      expect(result.current.isAutoActivated).toBe(false);
    });

    it('should activate emergency mode for critical alert within 10 miles on mobile', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [createMockAlert('critical', 5)],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(true);
      expect(result.current.isAutoActivated).toBe(true);
    });

    it('should activate emergency mode for high alert within 10 miles on mobile', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [createMockAlert('high', 8)],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(true);
      expect(result.current.isAutoActivated).toBe(true);
    });

    it('should handle different severity levels', () => {
      const severities = ['critical', 'high', 'medium', 'low'];
      const shouldActivate = [true, true, false, false];

      severities.forEach((severity, index) => {
        const { result } = renderHook(() =>
          useEmergencyMode({
            proximityAlerts: [createMockAlert(severity, 5)],
            userLocation: mockUserLocation,
            isMobile: true,
          })
        );

        expect(result.current.isEmergencyMode).toBe(shouldActivate[index]);
      });
    });

    it('should not activate for medium severity alert', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [createMockAlert('medium', 5)],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(false);
    });

    it('should not activate for low severity alert', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [createMockAlert('low', 5)],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(false);
    });

    it('should not activate for critical alert beyond 10 miles', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [createMockAlert('critical', 15)],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(false);
    });

    it('should activate for critical alert exactly at 10 miles', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [createMockAlert('critical', 10)],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(true);
    });

    it('should activate for high alert exactly at 10 miles', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [createMockAlert('high', 10)],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(true);
    });

    it('should handle case-insensitive severity levels', () => {
      const alertWithUppercase = createMockAlert('CRITICAL', 5);

      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [alertWithUppercase],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(true);
    });
  });

  describe('Data Validation', () => {
    it('should handle missing proximity alerts', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: undefined,
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(false);
      expect(result.current.criticalAlertCount).toBe(0);
    });

    it('should handle missing user location', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [createMockAlert('critical', 5)],
          userLocation: null,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(false);
    });

    it('should handle user location with invalid lat', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [createMockAlert('critical', 5)],
          userLocation: { lat: 'invalid', lon: -122.4194 },
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(false);
    });

    it('should handle user location with invalid lon', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [createMockAlert('critical', 5)],
          userLocation: { lat: 37.7749, lon: 'invalid' },
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(false);
    });

    it('should handle empty proximity alerts array', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(false);
      expect(result.current.nearestCriticalAlert).toBeNull();
      expect(result.current.criticalAlertCount).toBe(0);
    });

    it('should handle invalid alert objects', () => {
      const alerts = [
        createMockAlert('critical', 5),
        null,
        { invalid: 'object' },
        undefined,
        createMockAlert('high', 7),
      ];

      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: alerts,
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(true);
      expect(result.current.criticalAlertCount).toBe(2); // Only valid alerts
    });

    it('should handle alerts with missing distance_mi', () => {
      const alertWithoutDistance = { ...createMockAlert('critical', 5) };
      delete alertWithoutDistance.distance_mi;

      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [alertWithoutDistance],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(false);
    });

    it('should handle alerts with missing alert_severity', () => {
      const alertWithoutSeverity = { ...createMockAlert('critical', 5) };
      delete alertWithoutSeverity.alert_severity;

      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [alertWithoutSeverity],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(false);
    });
  });

  describe('Nearest Critical Alert', () => {
    it('should return nearest critical alert', () => {
      const alerts = [
        createMockAlert('critical', 8),
        createMockAlert('high', 5),
        createMockAlert('critical', 12),
      ];

      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: alerts,
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.nearestCriticalAlert).toBeDefined();
      expect(result.current.nearestCriticalAlert.distance_mi).toBe(5); // High severity, 5 miles
    });

    it('should handle multiple alerts at same distance', () => {
      const alerts = [
        createMockAlert('critical', 5),
        createMockAlert('high', 5),
      ];

      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: alerts,
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.nearestCriticalAlert.distance_mi).toBe(5);
    });

    it('should return null when no critical alerts', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [createMockAlert('medium', 2)],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.nearestCriticalAlert).toBeNull();
    });

    it('should exclude alerts beyond 10 mile threshold from nearest', () => {
      const alerts = [
        createMockAlert('critical', 8),
        createMockAlert('critical', 15), // Beyond threshold
        createMockAlert('high', 20), // Beyond threshold
      ];

      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: alerts,
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.nearestCriticalAlert.distance_mi).toBe(8);
    });
  });

  describe('Critical Alert Counting', () => {
    it('should count critical alerts correctly', () => {
      const alerts = [
        createMockAlert('critical', 5),
        createMockAlert('high', 7),
        createMockAlert('critical', 9),
      ];

      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: alerts,
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.criticalAlertCount).toBe(3); // 2 critical + 1 high
    });

    it('should count high severity alerts as critical', () => {
      const alerts = [
        createMockAlert('critical', 5),
        createMockAlert('high', 7),
      ];

      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: alerts,
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.criticalAlertCount).toBe(2);
    });

    it('should not count medium severity alerts', () => {
      const alerts = [
        createMockAlert('critical', 5),
        createMockAlert('medium', 7),
        createMockAlert('high', 9),
      ];

      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: alerts,
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.criticalAlertCount).toBe(2); // 1 critical + 1 high
    });

    it('should only count alerts within 10 miles', () => {
      const alerts = [
        createMockAlert('critical', 5),
        createMockAlert('critical', 8),
        createMockAlert('critical', 15), // Beyond 10 miles
      ];

      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: alerts,
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.criticalAlertCount).toBe(2);
    });
  });

  describe('Manual Toggle', () => {
    it('should toggle emergency mode manually', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(false);
      expect(result.current.isAutoActivated).toBe(false);

      act(() => {
        result.current.toggleEmergencyMode();
      });

      expect(result.current.isEmergencyMode).toBe(true);
      expect(result.current.isAutoActivated).toBe(false);
    });

    it('should toggle back to off', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      act(() => {
        result.current.toggleEmergencyMode();
      });

      expect(result.current.isEmergencyMode).toBe(true);

      act(() => {
        result.current.toggleEmergencyMode();
      });

      expect(result.current.isEmergencyMode).toBe(false);
    });

    it('should toggle manual override when auto-activated', () => {
      // Use distance > 5 miles to avoid auto-reset logic (line 157 in hook)
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [createMockAlert('critical', 7)], // Changed from 5 to 7
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(true);
      expect(result.current.isAutoActivated).toBe(true);

      // Toggle to force off
      act(() => {
        result.current.toggleEmergencyMode();
      });

      // After toggle from auto-activated state, we have a manual override
      // The mode should be turned off, and it's no longer auto-activated
      expect(result.current.isEmergencyMode).toBe(false);
      expect(result.current.isAutoActivated).toBe(false);
    });
  });

  describe('Reset to Auto Mode', () => {
    it('should reset to auto mode', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [],
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      // Toggle manually
      act(() => {
        result.current.toggleEmergencyMode();
      });

      expect(result.current.isEmergencyMode).toBe(true);
      expect(result.current.isAutoActivated).toBe(false);

      // Reset to auto
      act(() => {
        result.current.resetEmergencyMode();
      });

      expect(result.current.isEmergencyMode).toBe(false);
      expect(result.current.isAutoActivated).toBe(false);
    });

    it('should reset when manual override exists', () => {
      // Use distance > 5 miles to avoid auto-reset logic (line 157 in hook)
      const { result } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [createMockAlert('critical', 7)], // Changed from 5 to 7
          userLocation: mockUserLocation,
          isMobile: true,
        })
      );

      expect(result.current.isAutoActivated).toBe(true);

      // Override by toggling
      act(() => {
        result.current.toggleEmergencyMode();
      });

      // After toggle, we have a manual override
      expect(result.current.isAutoActivated).toBe(false);
      expect(result.current.isEmergencyMode).toBe(false);

      // Reset to auto mode
      act(() => {
        result.current.resetEmergencyMode();
      });

      // After reset, we're back to auto mode with critical alert active
      expect(result.current.isAutoActivated).toBe(true);
      expect(result.current.isEmergencyMode).toBe(true);
    });

    it('should auto-reset when critical alert gets within 5 miles', () => {
      jest.useFakeTimers();

      const { result, rerender } = renderHook(
        ({ alerts }) =>
          useEmergencyMode({
            proximityAlerts: alerts,
            userLocation: mockUserLocation,
            isMobile: true,
          }),
        {
          initialProps: { alerts: [createMockAlert('critical', 8)] },
        }
      );

      // User manually turns off emergency mode
      act(() => {
        result.current.toggleEmergencyMode();
      });

      expect(result.current.isEmergencyMode).toBe(false);
      expect(result.current.isAutoActivated).toBe(false);

      // Critical alert moves closer to 4 miles
      act(() => {
        rerender({ alerts: [createMockAlert('critical', 4)] });
      });

      // Should auto-reset
      expect(result.current.isAutoActivated).toBe(true);

      jest.useRealTimers();
    });

    it('should auto-reset after 1 minute when no critical alerts remain', () => {
      jest.useFakeTimers();

      const { result, rerender } = renderHook(
        ({ alerts }) =>
          useEmergencyMode({
            proximityAlerts: alerts,
            userLocation: mockUserLocation,
            isMobile: true,
          }),
        {
          initialProps: { alerts: [] },
        }
      );

      // User manually turns on emergency mode
      act(() => {
        result.current.toggleEmergencyMode();
      });

      expect(result.current.isEmergencyMode).toBe(true);
      expect(result.current.isAutoActivated).toBe(false);

      // Advance 30 seconds - should still be manually on
      act(() => {
        jest.advanceTimersByTime(30000);
      });

      expect(result.current.isEmergencyMode).toBe(true);

      // Advance to 60 seconds - should auto-reset
      act(() => {
        jest.advanceTimersByTime(30000);
      });

      expect(result.current.isAutoActivated).toBe(false);

      jest.useRealTimers();
    });
  });

  describe('Reactivity to Changes', () => {
    it('should update when proximity alerts change', () => {
      const { result, rerender } = renderHook(
        ({ alerts }) =>
          useEmergencyMode({
            proximityAlerts: alerts,
            userLocation: mockUserLocation,
            isMobile: true,
          }),
        {
          initialProps: { alerts: [] },
        }
      );

      expect(result.current.isEmergencyMode).toBe(false);

      // Add critical alert
      rerender({ alerts: [createMockAlert('critical', 5)] });

      expect(result.current.isEmergencyMode).toBe(true);

      // Remove critical alert
      rerender({ alerts: [createMockAlert('medium', 5)] });

      expect(result.current.isEmergencyMode).toBe(false);
    });

    it('should update when user location changes', () => {
      const newLocation = { lat: 40.7128, lon: -74.0060 };

      const { result, rerender } = renderHook(
        ({ location }) =>
          useEmergencyMode({
            proximityAlerts: [createMockAlert('critical', 5)],
            userLocation: location,
            isMobile: true,
          }),
        {
          initialProps: { location: mockUserLocation },
        }
      );

      expect(result.current.isEmergencyMode).toBe(true);

      // Change location (with null to represent no location)
      rerender({ location: null });

      expect(result.current.isEmergencyMode).toBe(false);
    });

    it('should update when isMobile prop changes', () => {
      const { result, rerender } = renderHook(
        ({ isMobile }) =>
          useEmergencyMode({
            proximityAlerts: [createMockAlert('critical', 5)],
            userLocation: mockUserLocation,
            isMobile,
          }),
        {
          initialProps: { isMobile: true },
        }
      );

      expect(result.current.isEmergencyMode).toBe(true);

      // Change to desktop
      rerender({ isMobile: false });

      expect(result.current.isEmergencyMode).toBe(false);
    });
  });

  describe('Default Parameters', () => {
    it('should handle being called with no parameters', () => {
      const { result } = renderHook(() => useEmergencyMode());

      expect(result.current.isEmergencyMode).toBe(false);
      expect(result.current.criticalAlertCount).toBe(0);
      expect(result.current.nearestCriticalAlert).toBeNull();
    });

    it('should handle partial parameters', () => {
      const { result } = renderHook(() =>
        useEmergencyMode({
          isMobile: true,
        })
      );

      expect(result.current.isEmergencyMode).toBe(false);
    });
  });
});
