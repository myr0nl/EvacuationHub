import { useState, useEffect, useMemo, useCallback } from 'react';

/**
 * Device type breakpoints (matches breakpoints.css)
 */
const BREAKPOINTS = {
  MOBILE: 640,
  TABLET: 1024,
};

/**
 * Custom hook for detecting device type and orientation
 *
 * @returns {{
 *   device: 'mobile' | 'tablet' | 'desktop',
 *   isMobile: boolean,
 *   isTablet: boolean,
 *   isDesktop: boolean,
 *   orientation: 'portrait' | 'landscape',
 *   width: number,
 *   height: number
 * }}
 *
 * @example
 * const { isMobile, isEmergencyMode, orientation } = useDeviceDetection();
 * if (isMobile && orientation === 'portrait') {
 *   // Render mobile portrait layout
 * }
 */
export const useDeviceDetection = () => {
  // Get initial window dimensions
  const getWindowDimensions = useCallback(() => {
    if (typeof window === 'undefined') {
      return { width: 0, height: 0 };
    }
    return {
      width: window.innerWidth,
      height: window.innerHeight,
    };
  }, []);

  const [windowDimensions, setWindowDimensions] = useState(getWindowDimensions);

  // Calculate device type based on width
  const device = useMemo(() => {
    const { width } = windowDimensions;
    if (width <= BREAKPOINTS.MOBILE) return 'mobile';
    if (width <= BREAKPOINTS.TABLET) return 'tablet';
    return 'desktop';
  }, [windowDimensions]);

  // Calculate orientation
  const orientation = useMemo(() => {
    const { width, height } = windowDimensions;
    return width > height ? 'landscape' : 'portrait';
  }, [windowDimensions]);

  // Debounced resize handler to optimize performance
  useEffect(() => {
    let timeoutId = null;

    const handleResize = () => {
      // Clear existing timeout
      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      // Debounce resize events by 150ms to avoid excessive re-renders
      timeoutId = setTimeout(() => {
        setWindowDimensions(getWindowDimensions());
      }, 150);
    };

    // Add resize event listener
    window.addEventListener('resize', handleResize);

    // Add orientation change listener for mobile devices
    if (window.screen && window.screen.orientation) {
      window.screen.orientation.addEventListener('change', handleResize);
    }

    // Cleanup
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      window.removeEventListener('resize', handleResize);
      if (window.screen && window.screen.orientation) {
        window.screen.orientation.removeEventListener('change', handleResize);
      }
    };
  }, [getWindowDimensions]);

  return {
    device,
    isMobile: device === 'mobile',
    isTablet: device === 'tablet',
    isDesktop: device === 'desktop',
    orientation,
    width: windowDimensions.width,
    height: windowDimensions.height,
  };
};

export default useDeviceDetection;
