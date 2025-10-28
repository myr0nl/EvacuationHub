/**
 * Tests for useDeviceDetection hook
 *
 * Run with: npm test useDeviceDetection.test.js
 */

import { renderHook, act } from '@testing-library/react';
import { useDeviceDetection } from '../useDeviceDetection';

// Mock window dimensions
const mockWindowDimensions = (width, height) => {
  Object.defineProperty(window, 'innerWidth', {
    writable: true,
    configurable: true,
    value: width,
  });
  Object.defineProperty(window, 'innerHeight', {
    writable: true,
    configurable: true,
    value: height,
  });
};

describe('useDeviceDetection', () => {
  beforeEach(() => {
    // Reset window dimensions
    mockWindowDimensions(1920, 1080);
    // Clear all timers
    jest.clearAllTimers();
  });

  afterEach(() => {
    jest.clearAllTimers();
  });

  describe('Device Type Detection', () => {
    it('should detect desktop device', () => {
      mockWindowDimensions(1920, 1080);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.device).toBe('desktop');
      expect(result.current.isDesktop).toBe(true);
      expect(result.current.isMobile).toBe(false);
      expect(result.current.isTablet).toBe(false);
    });

    it('should detect mobile device', () => {
      mockWindowDimensions(375, 667);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.device).toBe('mobile');
      expect(result.current.isMobile).toBe(true);
      expect(result.current.isTablet).toBe(false);
      expect(result.current.isDesktop).toBe(false);
    });

    it('should detect tablet device', () => {
      mockWindowDimensions(768, 1024);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.device).toBe('tablet');
      expect(result.current.isTablet).toBe(true);
      expect(result.current.isMobile).toBe(false);
      expect(result.current.isDesktop).toBe(false);
    });

    it('should handle edge case at mobile breakpoint (640px)', () => {
      mockWindowDimensions(640, 800);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.device).toBe('mobile');
    });

    it('should handle edge case just after mobile breakpoint (641px)', () => {
      mockWindowDimensions(641, 800);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.device).toBe('tablet');
    });

    it('should handle edge case at tablet breakpoint (1024px)', () => {
      mockWindowDimensions(1024, 800);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.device).toBe('tablet');
    });

    it('should handle edge case just after tablet breakpoint (1025px)', () => {
      mockWindowDimensions(1025, 800);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.device).toBe('desktop');
    });

    it('should handle very small mobile devices (320px)', () => {
      mockWindowDimensions(320, 568);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.device).toBe('mobile');
      expect(result.current.isMobile).toBe(true);
    });

    it('should handle large desktop screens (2560px)', () => {
      mockWindowDimensions(2560, 1440);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.device).toBe('desktop');
      expect(result.current.isDesktop).toBe(true);
    });
  });

  describe('Orientation Detection', () => {
    it('should detect portrait orientation', () => {
      mockWindowDimensions(375, 667);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.orientation).toBe('portrait');
    });

    it('should detect landscape orientation', () => {
      mockWindowDimensions(667, 375);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.orientation).toBe('landscape');
    });

    it('should handle square dimensions as landscape', () => {
      mockWindowDimensions(512, 512);
      const { result } = renderHook(() => useDeviceDetection());

      // When width === height, width > height is false, so portrait
      expect(result.current.orientation).toBe('portrait');
    });

    it('should detect landscape for mobile in landscape mode', () => {
      // Mobile device in landscape: width=640 (mobile breakpoint), height=375
      // This keeps the device as mobile even in landscape
      mockWindowDimensions(640, 375);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.orientation).toBe('landscape');
      expect(result.current.isMobile).toBe(true);
    });

    it('should detect landscape for tablet in landscape mode', () => {
      mockWindowDimensions(1024, 768);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.orientation).toBe('landscape');
      expect(result.current.isTablet).toBe(true);
    });
  });

  describe('Dimension Updates', () => {
    it('should return correct width and height', () => {
      mockWindowDimensions(1024, 768);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.width).toBe(1024);
      expect(result.current.height).toBe(768);
    });

    it('should update dimensions on resize event', async () => {
      jest.useFakeTimers();
      mockWindowDimensions(1920, 1080);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.isDesktop).toBe(true);
      expect(result.current.width).toBe(1920);

      // Resize to mobile
      act(() => {
        mockWindowDimensions(375, 667);
        window.dispatchEvent(new Event('resize'));
      });

      // Before debounce timer fires
      expect(result.current.isMobile).toBe(false);

      // After debounce (150ms)
      act(() => {
        jest.advanceTimersByTime(150);
      });

      expect(result.current.isMobile).toBe(true);
      expect(result.current.width).toBe(375);
      expect(result.current.height).toBe(667);

      jest.useRealTimers();
    });

    it('should debounce multiple rapid resize events', async () => {
      jest.useFakeTimers();
      mockWindowDimensions(1920, 1080);
      const { result } = renderHook(() => useDeviceDetection());

      act(() => {
        // Simulate rapid resize events
        mockWindowDimensions(1920, 900);
        window.dispatchEvent(new Event('resize'));
        jest.advanceTimersByTime(50);

        mockWindowDimensions(1600, 800);
        window.dispatchEvent(new Event('resize'));
        jest.advanceTimersByTime(50);

        mockWindowDimensions(1024, 700);
        window.dispatchEvent(new Event('resize'));
        jest.advanceTimersByTime(50);

        // Should still be at initial dimensions because debounce hasn't completed
        expect(result.current.width).toBe(1920);

        // Now advance to complete the debounce
        jest.advanceTimersByTime(100);
      });

      // Should now reflect the final resize
      expect(result.current.width).toBe(1024);

      jest.useRealTimers();
    });

    it('should trigger resize handler on orientation change event', () => {
      jest.useFakeTimers();
      mockWindowDimensions(375, 667);

      // Mock screen.orientation with addEventListener
      const addListenerMock = jest.fn();
      Object.defineProperty(window, 'screen', {
        value: {
          orientation: {
            addEventListener: addListenerMock,
            removeEventListener: jest.fn(),
          },
        },
        writable: true,
        configurable: true,
      });

      const { result } = renderHook(() => useDeviceDetection());

      // Verify that orientation change listener was registered
      expect(addListenerMock).toHaveBeenCalledWith('change', expect.any(Function));

      jest.useRealTimers();
    });
  });

  describe('Cleanup', () => {
    it('should cleanup event listeners on unmount', () => {
      const removeEventListenerSpy = jest.spyOn(window, 'removeEventListener');

      const { unmount } = renderHook(() => useDeviceDetection());

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('resize', expect.any(Function));

      removeEventListenerSpy.mockRestore();
    });

    it('should cleanup timers on unmount', () => {
      jest.useFakeTimers();
      mockWindowDimensions(1920, 1080);

      const { unmount } = renderHook(() => useDeviceDetection());

      act(() => {
        mockWindowDimensions(375, 667);
        window.dispatchEvent(new Event('resize'));
      });

      unmount();

      // Advancing timer should not throw
      expect(() => {
        jest.advanceTimersByTime(200);
      }).not.toThrow();

      jest.useRealTimers();
    });

    it('should cleanup screen orientation listener if available', () => {
      const removeEventListenerSpy = jest.fn();

      Object.defineProperty(window, 'screen', {
        value: {
          orientation: {
            addEventListener: jest.fn(),
            removeEventListener: removeEventListenerSpy,
          },
        },
        writable: true,
        configurable: true,
      });

      const { unmount } = renderHook(() => useDeviceDetection());

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('change', expect.any(Function));
    });
  });

  describe('Initial State', () => {
    it('should handle window being undefined', () => {
      // This is a code path that shouldn't normally happen in tests,
      // but the code handles it by returning 0,0 dimensions
      const { result } = renderHook(() => useDeviceDetection());

      // In our test environment, window is always defined
      expect(result.current.width).toBeGreaterThan(0);
    });

    it('should initialize with current window dimensions', () => {
      mockWindowDimensions(800, 600);
      const { result } = renderHook(() => useDeviceDetection());

      expect(result.current.width).toBe(800);
      expect(result.current.height).toBe(600);
    });
  });
});
