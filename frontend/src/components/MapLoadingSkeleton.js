import React from 'react';
import { Globe } from 'lucide-react';
import './MapLoadingSkeleton.css';

/**
 * Loading skeleton for the map component
 * Shows animated placeholders while disaster data is being fetched
 */
const MapLoadingSkeleton = () => {
  // Generate random marker positions for visual variety
  const generateMarkerPositions = () => {
    const positions = [];
    const markerCount = 12; // Show 12 skeleton markers

    for (let i = 0; i < markerCount; i++) {
      positions.push({
        id: i,
        top: `${Math.random() * 70 + 15}%`, // 15-85%
        left: `${Math.random() * 70 + 15}%`, // 15-85%
        delay: `${Math.random() * 2}s` // Stagger animations
      });
    }

    return positions;
  };

  const markers = generateMarkerPositions();

  return (
    <div className="map-loading-skeleton">
      {/* Background with subtle pattern */}
      <div className="skeleton-map-background">
        <div className="skeleton-pulse-overlay" />
      </div>

      {/* Skeleton markers */}
      <div className="skeleton-markers-container">
        {markers.map((marker) => (
          <div
            key={marker.id}
            className="skeleton-marker"
            style={{
              top: marker.top,
              left: marker.left,
              animationDelay: marker.delay
            }}
          />
        ))}
      </div>

      {/* Loading text with shimmer effect */}
      <div className="skeleton-loading-text">
        <div className="shimmer-wrapper">
          <div className="shimmer" />
        </div>
        <div className="loading-content">
          <div className="loading-icon">
            <Globe size={48} strokeWidth={2} className="loading-globe" />
          </div>
          <div className="loading-message">
            <span className="loading-primary">Loading disaster data...</span>
            <span className="loading-secondary">Fetching real-time alerts from NASA, NOAA, and more</span>
          </div>
        </div>
      </div>

      {/* Skeleton zoom controls */}
      <div className="skeleton-zoom-controls">
        <div className="skeleton-zoom-button" />
        <div className="skeleton-zoom-button" />
      </div>
    </div>
  );
};

export default MapLoadingSkeleton;
