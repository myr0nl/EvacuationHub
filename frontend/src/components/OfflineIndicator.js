import React, { useState, useEffect } from 'react';

/**
 * OfflineIndicator Component
 *
 * Displays a banner when the app is offline and using cached data.
 * Shows cache age and sync status.
 */
const OfflineIndicator = () => {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [cacheAge, setCacheAge] = useState(null);
  const [showBanner, setShowBanner] = useState(false);

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      setShowBanner(false);
    };

    const handleOffline = () => {
      setIsOnline(false);
      setShowBanner(true);
    };

    // Listen for online/offline events
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Check cache age when offline
    if (!navigator.onLine) {
      checkCacheAge();
    }

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  useEffect(() => {
    // Update cache age every minute when offline
    if (!isOnline) {
      const interval = setInterval(() => {
        checkCacheAge();
      }, 60000); // Update every minute

      return () => clearInterval(interval);
    }
  }, [isOnline]);

  const checkCacheAge = async () => {
    try {
      // Try to fetch from API and check response headers
      const response = await fetch('/api/cache/status');
      const cacheAgeHeader = response.headers.get('X-Cache-Age-Ms');

      if (cacheAgeHeader) {
        const ageMs = parseInt(cacheAgeHeader);
        setCacheAge(formatCacheAge(ageMs));
      }
    } catch (error) {
      // Offline, can't check cache age
      setCacheAge('Unknown');
    }
  };

  const formatCacheAge = (ageMs) => {
    const minutes = Math.floor(ageMs / 60000);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
      return `${hours}h ${minutes % 60}m ago`;
    } else {
      return `${minutes}m ago`;
    }
  };

  const handleDismiss = () => {
    setShowBanner(false);
  };

  if (!showBanner || isOnline) {
    return null;
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        backgroundColor: '#ff9800',
        color: '#ffffff',
        padding: '12px 20px',
        zIndex: 10000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)',
        fontFamily: 'Atkinson Hyperlegible, -apple-system, BlinkMacSystemFont, sans-serif',
        fontSize: '14px',
        fontWeight: 500
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M1 1l22 22M16.72 11.06A10.94 10.94 0 0 1 19 12.55M5 12.55a10.94 10.94 0 0 1 5.17-2.39M10.71 5.05A16 16 0 0 1 22.58 9M1.42 9a15.91 15.91 0 0 1 4.7-2.88M8.53 16.11a6 6 0 0 1 6.95 0M12 20h.01" />
        </svg>
        <span>
          You're offline - showing cached disaster data
          {cacheAge && ` (last updated ${cacheAge})`}
        </span>
      </div>

      <button
        onClick={handleDismiss}
        style={{
          background: 'transparent',
          border: 'none',
          color: '#ffffff',
          cursor: 'pointer',
          fontSize: '20px',
          padding: '0 8px',
          lineHeight: '1'
        }}
        aria-label="Dismiss offline notification"
      >
        ×
      </button>
    </div>
  );
};

export default OfflineIndicator;
