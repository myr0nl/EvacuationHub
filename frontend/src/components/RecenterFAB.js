import React from 'react';
import { Crosshair } from 'lucide-react';
import './RecenterFAB.css';

/**
 * RecenterFAB - Floating Action Button to recenter map on user location
 *
 * A FAB that appears in the bottom-right corner to center the map on the user's current location.
 * Only visible when user location is available.
 *
 * @param {function} onClick - Handler to center the map on user location
 * @param {boolean} hasLocation - Whether user location is available
 */
function RecenterFAB({ onClick, hasLocation }) {
  if (!hasLocation) return null;

  return (
    <button
      className="recenter-fab"
      onClick={onClick}
      aria-label="Center map on my location"
      title="Center on my location"
      type="button"
    >
      <Crosshair
        className="fab-icon"
        size={24}
        strokeWidth={2}
        aria-hidden="true"
      />
    </button>
  );
}

export default RecenterFAB;
