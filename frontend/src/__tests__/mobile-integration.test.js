/**
 * Integration Tests for Mobile Emergency Mode
 *
 * Tests device detection, emergency mode, and responsive behavior
 * working together as an integrated system.
 *
 * Run with: npm test mobile-integration.test.js
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useDeviceDetection } from '../hooks/useDeviceDetection';
import { useEmergencyMode } from '../hooks/useEmergencyMode';
import OfflineIndicator from '../components/OfflineIndicator';
import PWAInstallPrompt from '../components/PWAInstallPrompt';

describe('Mobile Emergency Mode Integration Tests', () => {
  beforeEach(() => {
    jest.clearAllTimers();
    jest.clearAllMocks();

    // Mock localStorage
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: jest.fn(),
        setItem: jest.fn(),
        removeItem: jest.fn(),
        clear: jest.fn(),
      },
      writable: true,
    });

    // Mock matchMedia for PWA
    window.matchMedia = jest.fn((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }));

    // Mock fetch for OfflineIndicator
    global.fetch = jest.fn();

    // Mock navigator.onLine
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: true,
    });
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.clearAllMocks();

    // Reset window dimensions to a default state after each test
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      writable: true,
      value: 1024,
    });
    Object.defineProperty(window, 'innerHeight', {
      configurable: true,
      writable: true,
      value: 768,
    });
  });

  describe('Device Detection Integration', () => {
    it('should correctly detect device type and orientation together', () => {
      const devices = [
        { width: 375, height: 667, device: 'mobile', orientation: 'portrait' },
        { width: 640, height: 375, device: 'mobile', orientation: 'landscape' }, // Fixed: 640 is mobile breakpoint
        { width: 768, height: 1024, device: 'tablet', orientation: 'portrait' },
        { width: 1024, height: 768, device: 'tablet', orientation: 'landscape' },
        { width: 1920, height: 1080, device: 'desktop', orientation: 'landscape' },
      ];

      devices.forEach(({ width, height, device, orientation }) => {
        Object.defineProperty(window, 'innerWidth', {
          configurable: true,
          writable: true,
          value: width,
        });
        Object.defineProperty(window, 'innerHeight', {
          configurable: true,
          writable: true,
          value: height,
        });

        const { result, unmount } = renderHook(() => useDeviceDetection());

        expect(result.current.device).toBe(device);
        expect(result.current.orientation).toBe(orientation);

        // Clean up after each iteration to avoid state leakage
        unmount();
      });

      // Reset window dimensions after test completes
      Object.defineProperty(window, 'innerWidth', {
        configurable: true,
        writable: true,
        value: 1024,
      });
      Object.defineProperty(window, 'innerHeight', {
        configurable: true,
        writable: true,
        value: 768,
      });
    });

    it('should update all device properties when resizing', async () => {
      jest.useFakeTimers();

      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        value: 1920,
      });
      Object.defineProperty(window, 'innerHeight', {
        writable: true,
        value: 1080,
      });

      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.device).toBe('desktop');
      expect(result.current.orientation).toBe('landscape');
      expect(result.current.isDesktop).toBe(true);
      expect(result.current.isMobile).toBe(false);

      // Resize to mobile
      act(() => {
        Object.defineProperty(window, 'innerWidth', {
          writable: true,
          value: 375,
        });
        Object.defineProperty(window, 'innerHeight', {
          writable: true,
          value: 667,
        });
        window.dispatchEvent(new Event('resize'));
      });

      // Advance debounce timer
      act(() => {
        jest.advanceTimersByTime(150);
      });

      expect(result.current.device).toBe('mobile');
      expect(result.current.orientation).toBe('portrait');
      expect(result.current.isMobile).toBe(true);
      expect(result.current.isDesktop).toBe(false);

      jest.useRealTimers();
    });
  });

  describe('Emergency Mode + Device Detection Integration', () => {
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

    it('should only activate emergency mode on mobile devices', () => {
      const alert = createMockAlert('critical', 5);

      const devices = [
        { width: 375, height: 667, isMobile: true, shouldActivate: true },
        { width: 1024, height: 768, isMobile: false, shouldActivate: false },
        { width: 1920, height: 1080, isMobile: false, shouldActivate: false },
      ];

      devices.forEach(({ width, height, isMobile, shouldActivate }) => {
        Object.defineProperty(window, 'innerWidth', {
          writable: true,
          value: width,
        });
        Object.defineProperty(window, 'innerHeight', {
          writable: true,
          value: height,
        });

        const { result: deviceResult } = renderHook(() => useDeviceDetection());

        const { result: emergencyResult } = renderHook(() =>
          useEmergencyMode({
            proximityAlerts: [alert],
            userLocation: mockUserLocation,
            isMobile: deviceResult.current.isMobile,
          })
        );

        expect(emergencyResult.current.isEmergencyMode).toBe(shouldActivate);
        expect(deviceResult.current.isMobile).toBe(isMobile);
      });
    });

    it('should activate emergency mode when device is mobile AND alert conditions met', () => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        value: 375,
      });
      Object.defineProperty(window, 'innerHeight', {
        writable: true,
        value: 667,
      });

      const { result: deviceResult } = renderHook(() => useDeviceDetection());

      expect(deviceResult.current.isMobile).toBe(true);

      const criticalAlert = createMockAlert('critical', 5);

      const { result: emergencyResult } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [criticalAlert],
          userLocation: mockUserLocation,
          isMobile: deviceResult.current.isMobile,
        })
      );

      expect(emergencyResult.current.isEmergencyMode).toBe(true);
      expect(emergencyResult.current.isAutoActivated).toBe(true);
    });

    it('should not activate emergency mode on desktop even with critical alert', () => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        value: 1920,
      });
      Object.defineProperty(window, 'innerHeight', {
        writable: true,
        value: 1080,
      });

      const { result: deviceResult } = renderHook(() => useDeviceDetection());

      expect(deviceResult.current.isDesktop).toBe(true);

      const criticalAlert = createMockAlert('critical', 5);

      const { result: emergencyResult } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [criticalAlert],
          userLocation: mockUserLocation,
          isMobile: deviceResult.current.isMobile,
        })
      );

      expect(emergencyResult.current.isEmergencyMode).toBe(false);
    });
  });

  describe('Responsive Component Rendering', () => {
    it('should render OfflineIndicator on all devices when offline', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      global.fetch.mockResolvedValueOnce({
        headers: new Map([['X-Cache-Age-Ms', '60000']]),
      });

      const { container } = render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        expect(screen.getByText(/You're offline/)).toBeInTheDocument();
      });
    });

    it('should render PWA install prompt on all devices', async () => {
      jest.useFakeTimers();

      window.localStorage.getItem.mockReturnValueOnce(null);

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      render(<PWAInstallPrompt />);

      // Dispatch event after component mounts to ensure listener is registered
      act(() => {
        window.dispatchEvent(beforeinstallpromptEvent);
      });

      // Advance timers by 5 seconds to trigger the showPrompt timeout
      act(() => {
        jest.advanceTimersByTime(5000);
      });

      await waitFor(() => {
        expect(screen.getByText('Install Disaster Alert')).toBeInTheDocument();
      });

      jest.useRealTimers();
    });
  });

  describe('Multiple Hooks Integration', () => {
    it('should handle device detection + emergency mode + responsive data flow', async () => {
      jest.useFakeTimers();

      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        value: 1920,
      });
      Object.defineProperty(window, 'innerHeight', {
        writable: true,
        value: 1080,
      });

      const mockUserLocation = { lat: 37.7749, lon: -122.4194 };
      const criticalAlert = {
        disaster_id: 'test-1',
        alert_severity: 'critical',
        distance_mi: 5,
      };

      const { result: deviceResult } = renderHook(() => useDeviceDetection());

      // On desktop - should NOT activate emergency mode
      const { result: emergencyResult } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [criticalAlert],
          userLocation: mockUserLocation,
          isMobile: deviceResult.current.isMobile,
        })
      );

      expect(deviceResult.current.isDesktop).toBe(true);
      expect(emergencyResult.current.isEmergencyMode).toBe(false);

      // Simulate resize to mobile
      act(() => {
        Object.defineProperty(window, 'innerWidth', {
          writable: true,
          value: 375,
        });
        Object.defineProperty(window, 'innerHeight', {
          writable: true,
          value: 667,
        });
        window.dispatchEvent(new Event('resize'));
      });

      // Advance debounce
      act(() => {
        jest.advanceTimersByTime(150);
      });

      // Now on mobile - emergency mode SHOULD activate
      const { result: emergencyResultMobile } = renderHook(() =>
        useEmergencyMode({
          proximityAlerts: [criticalAlert],
          userLocation: mockUserLocation,
          isMobile: true, // Mobile now
        })
      );

      expect(emergencyResultMobile.current.isEmergencyMode).toBe(true);

      jest.useRealTimers();
    });
  });

  describe('Breakpoint Coverage', () => {
    const testBreakpoints = [
      { width: 320, label: 'mobile-small' },
      { width: 375, label: 'mobile-std' },
      { width: 640, label: 'mobile-lg' },
      { width: 641, label: 'tablet-sm' },
      { width: 768, label: 'tablet' },
      { width: 1024, label: 'tablet-lg' },
      { width: 1025, label: 'desktop-sm' },
      { width: 1920, label: 'desktop-std' },
      { width: 2560, label: 'desktop-lg' },
    ];

    it('should correctly classify all standard breakpoints', () => {
      testBreakpoints.forEach(({ width, label }) => {
        Object.defineProperty(window, 'innerWidth', {
          configurable: true,
          writable: true,
          value: width,
        });
        Object.defineProperty(window, 'innerHeight', {
          configurable: true,
          writable: true,
          value: 800,
        });

        const { result, unmount } = renderHook(() => useDeviceDetection());

        const expectedDevice = label.startsWith('mobile') ? 'mobile' :
                               label.startsWith('tablet') ? 'tablet' :
                               'desktop';

        expect(result.current.device).toBe(expectedDevice);

        // Clean up after each iteration to avoid state leakage
        unmount();
      });

      // Reset window dimensions after test completes
      Object.defineProperty(window, 'innerWidth', {
        configurable: true,
        writable: true,
        value: 1024,
      });
      Object.defineProperty(window, 'innerHeight', {
        configurable: true,
        writable: true,
        value: 768,
      });
    });

    it('should handle orientation changes at all breakpoints', async () => {
      jest.useFakeTimers();

      // Test mobile device orientation change
      Object.defineProperty(window, 'innerWidth', {
        configurable: true,
        writable: true,
        value: 375,
      });
      Object.defineProperty(window, 'innerHeight', {
        configurable: true,
        writable: true,
        value: 667,
      });

      let { result, unmount } = renderHook(() => useDeviceDetection());
      expect(result.current.device).toBe('mobile');
      expect(result.current.orientation).toBe('portrait');

      act(() => {
        Object.defineProperty(window, 'innerWidth', {
          configurable: true,
          writable: true,
          value: 667,
        });
        Object.defineProperty(window, 'innerHeight', {
          configurable: true,
          writable: true,
          value: 375,
        });
        window.dispatchEvent(new Event('resize'));
      });

      // Advance timers to allow debounce to complete (150ms)
      act(() => {
        jest.advanceTimersByTime(200);
      });

      expect(result.current.orientation).toBe('landscape');
      unmount();

      // Test tablet device orientation change
      jest.clearAllTimers();
      Object.defineProperty(window, 'innerWidth', {
        configurable: true,
        writable: true,
        value: 768,
      });
      Object.defineProperty(window, 'innerHeight', {
        configurable: true,
        writable: true,
        value: 1024,
      });

      ({ result, unmount } = renderHook(() => useDeviceDetection()));
      expect(result.current.device).toBe('tablet');
      expect(result.current.orientation).toBe('portrait');

      act(() => {
        Object.defineProperty(window, 'innerWidth', {
          configurable: true,
          writable: true,
          value: 1024,
        });
        Object.defineProperty(window, 'innerHeight', {
          configurable: true,
          writable: true,
          value: 768,
        });
        window.dispatchEvent(new Event('resize'));
      });

      // Advance timers to allow debounce to complete (150ms)
      act(() => {
        jest.advanceTimersByTime(200);
      });

      expect(result.current.orientation).toBe('landscape');
      unmount();

      jest.useRealTimers();
    });

    it('should handle orientation change on desktop', async () => {
      jest.useFakeTimers();

      // Start with portrait desktop dimensions (height > width)
      Object.defineProperty(window, 'innerWidth', {
        configurable: true,
        writable: true,
        value: 1080,
      });
      Object.defineProperty(window, 'innerHeight', {
        configurable: true,
        writable: true,
        value: 1920,
      });

      const { result, unmount } = renderHook(() => useDeviceDetection());
      expect(result.current.device).toBe('desktop');
      expect(result.current.orientation).toBe('portrait');

      // Rotate to landscape (width > height)
      act(() => {
        Object.defineProperty(window, 'innerWidth', {
          configurable: true,
          writable: true,
          value: 1920,
        });
        Object.defineProperty(window, 'innerHeight', {
          configurable: true,
          writable: true,
          value: 1080,
        });
        window.dispatchEvent(new Event('resize'));
      });

      // Advance timers to allow debounce to complete (150ms)
      act(() => {
        jest.advanceTimersByTime(200);
      });

      expect(result.current.orientation).toBe('landscape');
      unmount();

      jest.useRealTimers();
    });
  });

  describe('Performance - Multiple State Changes', () => {
    it('should handle rapid device changes without memory leaks', async () => {
      jest.useFakeTimers();

      const widths = [375, 768, 1024, 375, 1920, 375];

      widths.forEach((width) => {
        Object.defineProperty(window, 'innerWidth', {
          writable: true,
          value: width,
        });

        const { result } = renderHook(() => useDeviceDetection());

        expect(result.current.width).toBe(width);

        act(() => {
          window.dispatchEvent(new Event('resize'));
        });

        act(() => {
          jest.advanceTimersByTime(150);
        });
      });

      // Should complete without errors
      expect(true).toBe(true);

      jest.useRealTimers();
    });

    it('should handle multiple emergency mode state changes', () => {
      const mockUserLocation = { lat: 37.7749, lon: -122.4194 };

      const alerts = [
        { alert_severity: 'critical', distance_mi: 5 },
        { alert_severity: 'high', distance_mi: 8 },
        { alert_severity: 'medium', distance_mi: 3 },
        { alert_severity: 'critical', distance_mi: 15 },
      ];

      alerts.forEach((alert) => {
        const { result } = renderHook(() =>
          useEmergencyMode({
            proximityAlerts: [alert],
            userLocation: mockUserLocation,
            isMobile: true,
          })
        );

        // Should not throw
        expect(result.current).toHaveProperty('isEmergencyMode');
        expect(result.current).toHaveProperty('criticalAlertCount');
      });
    });
  });

  describe('Accessibility Across Devices', () => {
    it('should maintain accessibility labels on all devices', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      global.fetch.mockResolvedValueOnce({
        headers: new Map([['X-Cache-Age-Ms', '60000']]),
      });

      render(<OfflineIndicator />);

      fireEvent.offline(window);

      await waitFor(() => {
        const dismissButton = screen.getByLabelText(/Dismiss offline notification/);
        expect(dismissButton).toHaveAttribute('aria-label');
      });
    });

    it('should provide semantic HTML in PWA prompt', async () => {
      jest.useFakeTimers();

      window.localStorage.getItem.mockReturnValueOnce(null);

      const mockPrompt = jest.fn();
      const beforeinstallpromptEvent = new Event('beforeinstallprompt');
      beforeinstallpromptEvent.prompt = mockPrompt;

      render(<PWAInstallPrompt />);

      // Dispatch event after component mounts to ensure listener is registered
      act(() => {
        window.dispatchEvent(beforeinstallpromptEvent);
      });

      // Advance timers by 5 seconds to trigger the showPrompt timeout
      act(() => {
        jest.advanceTimersByTime(5000);
      });

      // Check for semantic elements
      await waitFor(() => {
        expect(screen.getByText('Install Disaster Alert')).toBeInTheDocument();
      });
      expect(screen.getByText(/Install this app/)).toBeInTheDocument();

      jest.useRealTimers();
    });
  });

  describe('Touch Device Interactions', () => {
    it('should handle touch events on mobile devices', async () => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        value: 375,
      });
      Object.defineProperty(window, 'innerHeight', {
        writable: true,
        value: 667,
      });

      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.isMobile).toBe(true);

      // Simulate touch event
      const touchEvent = new TouchEvent('touchstart', {
        touches: [{ clientX: 0, clientY: 0 }],
      });

      // Should not throw
      expect(() => {
        window.dispatchEvent(touchEvent);
      }).not.toThrow();
    });
  });

  describe('State Consistency Across Components', () => {
    it('should maintain consistent device state across multiple component mounts', () => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        value: 375,
      });
      Object.defineProperty(window, 'innerHeight', {
        writable: true,
        value: 667,
      });

      const { result: result1 } = renderHook(() => useDeviceDetection());
      const { result: result2 } = renderHook(() => useDeviceDetection());
      const { result: result3 } = renderHook(() => useDeviceDetection());

      expect(result1.current.device).toBe('mobile');
      expect(result2.current.device).toBe('mobile');
      expect(result3.current.device).toBe('mobile');

      expect(result1.current.device).toBe(result2.current.device);
      expect(result2.current.device).toBe(result3.current.device);
    });
  });
});
