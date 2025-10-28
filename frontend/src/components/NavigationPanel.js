import React, { useState, useEffect, useMemo } from 'react';
import './NavigationPanel.css';
import NavigationInstructions from './NavigationInstructions';
import BottomSheet, { SHEET_STATES } from './BottomSheet';
import { UI_ICONS } from '../config/icons';

/**
 * NavigationPanel - Turn-by-turn navigation display
 * Google Maps-style mobile UX with bottom sheet pattern
 * Shows current step, upcoming directions, and progress
 */
function NavigationPanel({ selectedRoute, userLocation, onExit, onRecenter, onOverviewToggle }) {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [distanceToNextStep, setDistanceToNextStep] = useState(null);
  const [isCompactMode, setIsCompactMode] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

  // Extract waypoints from route
  const waypoints = useMemo(() => {
    console.log('NavigationPanel: selectedRoute:', selectedRoute);
    console.log('NavigationPanel: waypoints:', selectedRoute?.waypoints);
    return selectedRoute?.waypoints || [];
  }, [selectedRoute]);

  const currentStep = waypoints[currentStepIndex];
  const nextStep = waypoints[currentStepIndex + 1];
  const totalSteps = waypoints.length;
  const progress = totalSteps > 0 ? ((currentStepIndex + 1) / totalSteps) * 100 : 0;

  // Detect mobile viewport changes
  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Calculate distance to next step based on user location
  // (Simplified - in production you'd track actual route progress)
  useEffect(() => {
    if (!userLocation || !currentStep) return;

    // For now, just use the step's distance
    // In a real implementation, you'd calculate remaining distance to this step
    setDistanceToNextStep(currentStep.distance_mi);
  }, [userLocation, currentStep]);

  // Auto-advance to next step (demo - in production use actual location tracking)
  const handleNextStep = () => {
    if (currentStepIndex < totalSteps - 1) {
      setCurrentStepIndex(currentStepIndex + 1);
    }
  };

  const handlePrevStep = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(currentStepIndex - 1);
    }
  };

  // Format duration from seconds to human readable
  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes} min`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  // Get icon for instruction type
  const getInstructionIcon = (type) => {
    const lowerType = (type || '').toLowerCase();

    // Map instruction types to Lucide icons
    if (lowerType.includes('left')) {
      if (lowerType.includes('slight')) return <UI_ICONS.arrowUpLeft size={32} strokeWidth={2} />;
      if (lowerType.includes('sharp')) return <UI_ICONS.arrowLeft size={32} strokeWidth={2} />;
      return <UI_ICONS.arrowLeft size={32} strokeWidth={2} />;
    }
    if (lowerType.includes('right')) {
      if (lowerType.includes('slight')) return <UI_ICONS.arrowUpRight size={32} strokeWidth={2} />;
      if (lowerType.includes('sharp')) return <UI_ICONS.arrowRight size={32} strokeWidth={2} />;
      return <UI_ICONS.arrowRight size={32} strokeWidth={2} />;
    }
    if (lowerType.includes('straight')) return <UI_ICONS.arrowUp size={32} strokeWidth={2} />;
    if (lowerType.includes('uturn')) return <UI_ICONS.uturn size={32} strokeWidth={2} />;
    if (lowerType.includes('roundabout')) return <UI_ICONS.roundabout size={32} strokeWidth={2} />;
    if (lowerType.includes('depart')) return <UI_ICONS.navigation size={32} strokeWidth={2} />;
    if (lowerType.includes('arrive')) return <UI_ICONS.mapPin size={32} strokeWidth={2} />;

    // Default
    return <UI_ICONS.arrowUp size={32} strokeWidth={2} />;
  };

  const CloseIcon = UI_ICONS.close;
  const MapPinIcon = UI_ICONS.mapPin;
  const MapIcon = UI_ICONS.map;

  if (!selectedRoute || waypoints.length === 0) {
    return (
      <div className="navigation-panel">
        <div className="nav-error">
          <p>No navigation data available</p>
          <button className="nav-exit-btn" onClick={onExit}>Exit Navigation</button>
        </div>
      </div>
    );
  }

  // Render navigation content (used in both mobile bottom sheet and desktop panel)
  const renderNavigationContent = (sheetState) => {
    const isCollapsed = sheetState === SHEET_STATES.COLLAPSED;
    const isAnchor = sheetState === SHEET_STATES.ANCHOR;

    return (
      <>
        {/* Header with exit button and controls - always visible */}
        <div className="nav-header">
          <button
            className="nav-exit-btn"
            onClick={onExit}
            title="Exit navigation mode"
            aria-label="Exit navigation mode"
          >
            <CloseIcon size={20} strokeWidth={2} />
          </button>
          <div className="nav-destination-info">
            <span className="nav-destination-name">{selectedRoute.destination?.name || 'Safe Zone'}</span>
            <span className="nav-eta">
              {selectedRoute.distance_mi?.toFixed(1) || '0.0'} mi · {formatDuration(selectedRoute.duration_seconds)}
            </span>
          </div>
          <div className="nav-header-controls">
            {onRecenter && (
              <button
                className="nav-control-btn"
                onClick={onRecenter}
                title="Recenter map on your location"
                aria-label="Recenter map on your location"
              >
                <MapPinIcon size={18} strokeWidth={2} />
              </button>
            )}
            {onOverviewToggle && (
              <button
                className="nav-control-btn"
                onClick={onOverviewToggle}
                title="View full route"
                aria-label="View full route overview"
              >
                <MapIcon size={18} strokeWidth={2} />
              </button>
            )}
          </div>
        </div>

        {/* Current instruction - large and prominent - always visible */}
        <div className="nav-current-step">
          <div className="nav-instruction-icon">
            {getInstructionIcon(currentStep?.type)}
          </div>
          <div className="nav-instruction-text">
            <div className="nav-instruction-main">
              {currentStep?.instruction || 'Continue straight'}
            </div>
            {distanceToNextStep !== null && (
              <div className="nav-instruction-distance">
                {distanceToNextStep < 0.1
                  ? `${Math.round(distanceToNextStep * 5280)} ft`
                  : `${distanceToNextStep.toFixed(1)} mi`
                }
              </div>
            )}
          </div>
        </div>

        {/* Next step preview - visible in anchor and expanded states */}
        {!isCollapsed && nextStep && (
          <div className="nav-next-step">
            <span className="nav-then-label">Then</span>
            <span className="nav-next-icon" style={{ display: 'flex', alignItems: 'center' }}>
              {getInstructionIcon(nextStep.type)}
            </span>
            <span className="nav-next-text">{nextStep.instruction}</span>
          </div>
        )}

        {/* Progress bar - visible in anchor and expanded states */}
        {!isCollapsed && (
          <div className="nav-progress-container">
            <div className="nav-progress-bar" style={{ width: `${progress}%` }}></div>
            <div className="nav-progress-text">
              Step {currentStepIndex + 1} of {totalSteps}
            </div>
          </div>
        )}

        {/* Step navigation controls - visible in anchor and expanded states */}
        {!isCollapsed && (
          <div className="nav-step-controls">
            <button
              onClick={handlePrevStep}
              disabled={currentStepIndex === 0}
              className="nav-step-btn"
              aria-label="Previous navigation step"
              style={{ display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center' }}
            >
              <UI_ICONS.arrowLeft size={16} strokeWidth={2} />
              <span>Prev</span>
            </button>
            <button
              onClick={handleNextStep}
              disabled={currentStepIndex >= totalSteps - 1}
              className="nav-step-btn"
              aria-label="Next navigation step"
              style={{ display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center' }}
            >
              <span>Next</span>
              <UI_ICONS.arrowRight size={16} strokeWidth={2} />
            </button>
          </div>
        )}

        {/* All steps list - only in expanded state */}
        {sheetState === SHEET_STATES.EXPANDED && (
          <div className="nav-all-steps-container">
            <NavigationInstructions waypoints={waypoints} isExpanded={true} />
          </div>
        )}
      </>
    );
  };

  // Mobile: Use BottomSheet component
  if (isMobile) {
    return (
      <BottomSheet defaultState={SHEET_STATES.COLLAPSED}>
        {({ sheetState }) => (
          <div className={`navigation-panel mobile-sheet ${sheetState}`}>
            {renderNavigationContent(sheetState)}
          </div>
        )}
      </BottomSheet>
    );
  }

  // Desktop: Use traditional panel (keep existing behavior)
  return (
    <div className={`navigation-panel ${isCompactMode ? 'compact' : ''}`}>
      {renderNavigationContent(isCompactMode ? SHEET_STATES.COLLAPSED : SHEET_STATES.EXPANDED)}

      {/* Desktop-only compact mode toggle */}
      <button
        className="nav-compact-toggle"
        onClick={() => setIsCompactMode(!isCompactMode)}
        title={isCompactMode ? "Expand panel" : "Minimize panel"}
      >
        {isCompactMode ? <UI_ICONS.chevronUp size={20} strokeWidth={2} /> : <UI_ICONS.chevronDown size={20} strokeWidth={2} />}
      </button>
    </div>
  );
}

export default NavigationPanel;
