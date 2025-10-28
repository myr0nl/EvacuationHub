import React, { useState, useEffect } from 'react';

/**
 * PWAInstallPrompt Component
 *
 * Displays a prompt to install the app when the browser's install prompt is available.
 * Handles the beforeinstallprompt event and shows a custom UI.
 */
const PWAInstallPrompt = () => {
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);

  useEffect(() => {
    // Check if app is already installed
    if (window.matchMedia('(display-mode: standalone)').matches) {
      setIsInstalled(true);
      return;
    }

    // Check localStorage for user preference
    const dismissedAt = localStorage.getItem('pwa-install-dismissed-at');
    if (dismissedAt) {
      const dismissedDate = new Date(dismissedAt);
      const now = new Date();
      const daysSinceDismissed = (now - dismissedDate) / (1000 * 60 * 60 * 24);

      // Don't show again for 7 days after dismissal
      if (daysSinceDismissed < 7) {
        return;
      }
    }

    // Track timeout ID for cleanup
    let showPromptTimeoutId = null;

    // Listen for the beforeinstallprompt event
    const handleBeforeInstallPrompt = (e) => {
      // Prevent the mini-infobar from appearing on mobile
      e.preventDefault();

      // Store the event for later use
      setDeferredPrompt(e);

      // Show the custom install prompt after a delay
      showPromptTimeoutId = setTimeout(() => {
        setShowPrompt(true);
      }, 5000); // Show after 5 seconds
    };

    const handleAppInstalled = () => {
      console.log('[PWA] App installed successfully');
      setIsInstalled(true);
      setShowPrompt(false);
      setDeferredPrompt(null);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);

    return () => {
      // Clear pending timeout
      if (showPromptTimeoutId) {
        clearTimeout(showPromptTimeoutId);
      }
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, []);

  const handleInstallClick = async () => {
    if (!deferredPrompt) {
      return;
    }

    try {
      // Show the browser's install prompt
      deferredPrompt.prompt();

      // Wait for the user's response
      const { outcome } = await deferredPrompt.userChoice;

      console.log(`[PWA] Install prompt outcome: ${outcome}`);

      if (outcome === 'accepted') {
        console.log('[PWA] User accepted the install prompt');
      } else {
        console.log('[PWA] User dismissed the install prompt');
      }

      // Clear the deferred prompt and hide prompt
      setDeferredPrompt(null);
      setShowPrompt(false);
    } catch (error) {
      console.error('[PWA] Error during install:', error);
      // Still clear state on error
      setDeferredPrompt(null);
      setShowPrompt(false);
    }
  };

  const handleDismiss = () => {
    setShowPrompt(false);

    // Store dismissal timestamp
    localStorage.setItem('pwa-install-dismissed-at', new Date().toISOString());
  };

  if (isInstalled || !showPrompt) {
    return null;
  }

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '20px',
        left: '50%',
        transform: 'translateX(-50%)',
        backgroundColor: '#ffffff',
        borderRadius: '12px',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.2)',
        padding: '20px 24px',
        maxWidth: '400px',
        width: 'calc(100% - 40px)',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        fontFamily: 'Atkinson Hyperlegible, -apple-system, BlinkMacSystemFont, sans-serif',
        animation: 'slideUp 0.3s ease-out'
      }}
    >
      <style>
        {`
          @keyframes slideUp {
            from {
              transform: translateX(-50%) translateY(100px);
              opacity: 0;
            }
            to {
              transform: translateX(-50%) translateY(0);
              opacity: 1;
            }
          }
        `}
      </style>

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
        <div
          style={{
            width: '48px',
            height: '48px',
            borderRadius: '12px',
            backgroundColor: '#1e40af',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0
          }}
        >
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#ffffff"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
        </div>

        <div style={{ flex: 1 }}>
          <h3
            style={{
              margin: 0,
              fontSize: '16px',
              fontWeight: 600,
              color: '#1a1a1a',
              marginBottom: '6px'
            }}
          >
            Install Disaster Alert
          </h3>
          <p
            style={{
              margin: 0,
              fontSize: '14px',
              color: '#666666',
              lineHeight: '1.5'
            }}
          >
            Install this app for quick access to disaster alerts, offline support, and faster performance.
          </p>
        </div>

        <button
          onClick={handleDismiss}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#999999',
            cursor: 'pointer',
            fontSize: '24px',
            padding: 0,
            lineHeight: '1',
            width: '24px',
            height: '24px',
            flexShrink: 0
          }}
          aria-label="Dismiss install prompt"
        >
          ×
        </button>
      </div>

      <div style={{ display: 'flex', gap: '12px' }}>
        <button
          onClick={handleInstallClick}
          style={{
            flex: 1,
            backgroundColor: '#1e40af',
            color: '#ffffff',
            border: 'none',
            borderRadius: '8px',
            padding: '12px 20px',
            fontSize: '14px',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'background-color 0.2s'
          }}
          onMouseEnter={(e) => {
            e.target.style.backgroundColor = '#1e3a8a';
          }}
          onMouseLeave={(e) => {
            e.target.style.backgroundColor = '#1e40af';
          }}
        >
          Install App
        </button>

        <button
          onClick={handleDismiss}
          style={{
            backgroundColor: 'transparent',
            color: '#666666',
            border: '1px solid #e0e0e0',
            borderRadius: '8px',
            padding: '12px 20px',
            fontSize: '14px',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'background-color 0.2s'
          }}
          onMouseEnter={(e) => {
            e.target.style.backgroundColor = '#f5f5f5';
          }}
          onMouseLeave={(e) => {
            e.target.style.backgroundColor = 'transparent';
          }}
        >
          Not Now
        </button>
      </div>
    </div>
  );
};

export default PWAInstallPrompt;
