import React, { useState, useRef, useEffect, useCallback } from 'react';
import './BottomSheet.css';

/**
 * Google Maps-style bottom sheet component for mobile
 * Features:
 * - 3-state system: collapsed (minimized), anchor (partial), expanded (full)
 * - Swipe gesture support for dragging between states
 * - Preserves map visibility in all states
 * - Smooth spring-based animations
 * - One-handed operation optimized
 */

const SHEET_STATES = {
  COLLAPSED: 'collapsed',   // ~180px - shows summary only
  ANCHOR: 'anchor',         // ~50vh - shows current + next few steps
  EXPANDED: 'expanded'      // ~80vh - shows full scrollable list
};

const SHEET_HEIGHTS = {
  collapsed: 180,           // Minimum height (route summary)
  anchor: '50vh',          // Partial expansion
  expanded: '80vh'         // Maximum height
};

const SWIPE_THRESHOLD = 50;  // Pixels to drag before state change
const VELOCITY_THRESHOLD = 0.5; // Speed threshold for gesture detection

const BottomSheet = ({ children, defaultState = SHEET_STATES.COLLAPSED, onStateChange, onClose }) => {
  const [sheetState, setSheetState] = useState(defaultState);
  const [isDragging, setIsDragging] = useState(false);
  const [startY, setStartY] = useState(0);
  const [currentY, setCurrentY] = useState(0);
  const [dragOffset, setDragOffset] = useState(0);
  const sheetRef = useRef(null);
  const startTimeRef = useRef(0);
  const lastYRef = useRef(0);

  // Calculate sheet height based on current state
  const getSheetHeight = useCallback(() => {
    switch (sheetState) {
      case SHEET_STATES.COLLAPSED:
        return SHEET_HEIGHTS.collapsed;
      case SHEET_STATES.ANCHOR:
        return SHEET_HEIGHTS.anchor;
      case SHEET_STATES.EXPANDED:
        return SHEET_HEIGHTS.expanded;
      default:
        return SHEET_HEIGHTS.collapsed;
    }
  }, [sheetState]);

  // Handle state transitions
  const transitionToState = useCallback((newState) => {
    if (newState !== sheetState) {
      setSheetState(newState);
      setDragOffset(0);
      if (onStateChange) {
        onStateChange(newState);
      }
    }
  }, [sheetState, onStateChange]);

  // Touch start handler
  const handleTouchStart = useCallback((e) => {
    // Only allow dragging from the drag handle area
    const target = e.target;
    const dragHandle = sheetRef.current?.querySelector('.bottom-sheet-drag-handle');
    const header = sheetRef.current?.querySelector('.bottom-sheet-header');

    if (dragHandle?.contains(target) || header?.contains(target)) {
      setIsDragging(true);
      setStartY(e.touches[0].clientY);
      setCurrentY(e.touches[0].clientY);
      lastYRef.current = e.touches[0].clientY;
      startTimeRef.current = Date.now();
    }
  }, []);

  // Touch move handler
  const handleTouchMove = useCallback((e) => {
    if (!isDragging) return;

    const touch = e.touches[0];
    setCurrentY(touch.clientY);
    const offset = touch.clientY - startY;

    // Only allow dragging down when expanded, up when collapsed, both when anchored
    if (sheetState === SHEET_STATES.EXPANDED && offset < 0) return;
    if (sheetState === SHEET_STATES.COLLAPSED && offset > 0) return;

    setDragOffset(offset);
    lastYRef.current = touch.clientY;
  }, [isDragging, startY, sheetState]);

  // Touch end handler
  const handleTouchEnd = useCallback(() => {
    if (!isDragging) return;

    const totalOffset = currentY - startY;
    const duration = Date.now() - startTimeRef.current;
    const velocity = Math.abs(totalOffset) / duration;

    // Determine next state based on gesture direction and velocity
    let nextState = sheetState;

    if (velocity > VELOCITY_THRESHOLD) {
      // Fast swipe - use velocity direction
      if (totalOffset > 0) {
        // Swipe down
        if (sheetState === SHEET_STATES.EXPANDED) {
          nextState = SHEET_STATES.ANCHOR;
        } else if (sheetState === SHEET_STATES.ANCHOR) {
          nextState = SHEET_STATES.COLLAPSED;
        } else if (sheetState === SHEET_STATES.COLLAPSED && onClose) {
          // Close completely on swipe down from collapsed
          onClose();
          setIsDragging(false);
          setDragOffset(0);
          return;
        }
      } else {
        // Swipe up
        nextState = sheetState === SHEET_STATES.COLLAPSED
          ? SHEET_STATES.ANCHOR
          : SHEET_STATES.EXPANDED;
      }
    } else {
      // Slow drag - use threshold
      if (Math.abs(totalOffset) > SWIPE_THRESHOLD) {
        if (totalOffset > 0) {
          // Drag down
          if (sheetState === SHEET_STATES.EXPANDED) {
            nextState = SHEET_STATES.ANCHOR;
          } else if (sheetState === SHEET_STATES.ANCHOR) {
            nextState = SHEET_STATES.COLLAPSED;
          } else if (sheetState === SHEET_STATES.COLLAPSED && totalOffset > SWIPE_THRESHOLD * 2 && onClose) {
            // Close completely on strong drag down from collapsed (double threshold)
            onClose();
            setIsDragging(false);
            setDragOffset(0);
            return;
          }
        } else {
          // Drag up
          nextState = sheetState === SHEET_STATES.COLLAPSED
            ? SHEET_STATES.ANCHOR
            : SHEET_STATES.EXPANDED;
        }
      }
    }

    transitionToState(nextState);
    setIsDragging(false);
    setDragOffset(0);
  }, [isDragging, currentY, startY, sheetState, transitionToState, onClose]);

  // Keyboard navigation handler for drag handle
  const handleKeyDown = useCallback((e) => {
    // Enter or Space: Toggle between states
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();

      // Cycle through states: collapsed → anchor → expanded → collapsed
      if (sheetState === SHEET_STATES.COLLAPSED) {
        transitionToState(SHEET_STATES.ANCHOR);
      } else if (sheetState === SHEET_STATES.ANCHOR) {
        transitionToState(SHEET_STATES.EXPANDED);
      } else {
        transitionToState(SHEET_STATES.COLLAPSED);
      }
    }

    // Escape: Go to collapsed state
    if (e.key === 'Escape') {
      e.preventDefault();
      transitionToState(SHEET_STATES.COLLAPSED);
    }
  }, [sheetState, transitionToState]);

  // Add touch event listeners
  useEffect(() => {
    const sheet = sheetRef.current;
    if (!sheet) return;

    sheet.addEventListener('touchstart', handleTouchStart, { passive: true });
    sheet.addEventListener('touchmove', handleTouchMove, { passive: true });
    sheet.addEventListener('touchend', handleTouchEnd, { passive: true });

    return () => {
      sheet.removeEventListener('touchstart', handleTouchStart);
      sheet.removeEventListener('touchmove', handleTouchMove);
      sheet.removeEventListener('touchend', handleTouchEnd);
    };
  }, [handleTouchStart, handleTouchMove, handleTouchEnd]);

  // Programmatic state change methods (exposed via ref)
  const expand = useCallback(() => transitionToState(SHEET_STATES.EXPANDED), [transitionToState]);
  const collapse = useCallback(() => transitionToState(SHEET_STATES.COLLAPSED), [transitionToState]);
  const anchor = useCallback(() => transitionToState(SHEET_STATES.ANCHOR), [transitionToState]);

  // Calculate dynamic transform based on drag offset
  const getTransform = () => {
    if (!isDragging) return 'translateY(0)';
    return `translateY(${Math.max(0, dragOffset)}px)`;
  };

  return (
    <>
      {/* Backdrop - dims map when expanded, closes sheet on click to allow map interaction */}
      <div
        className={`bottom-sheet-backdrop ${sheetState === SHEET_STATES.EXPANDED ? 'visible' : ''}`}
        onClick={() => {
          // Close the sheet completely to allow immediate map interaction
          if (onClose) {
            onClose();
          } else {
            // Fallback to collapsing if no onClose provided
            transitionToState(SHEET_STATES.COLLAPSED);
          }
        }}
      />

      {/* Bottom Sheet */}
      <div
        ref={sheetRef}
        className={`bottom-sheet ${sheetState} ${isDragging ? 'dragging' : ''}`}
        style={{
          height: getSheetHeight(),
          transform: getTransform(),
        }}
      >
        {/* Drag Handle */}
        <div
          className="bottom-sheet-drag-handle"
          role="button"
          tabIndex={0}
          aria-label="Drag to expand or collapse navigation"
          onKeyDown={handleKeyDown}
        >
          <div className="drag-indicator" />
        </div>

        {/* Sheet Content */}
        <div className="bottom-sheet-content">
          {typeof children === 'function'
            ? children({ sheetState, expand, collapse, anchor })
            : children}
        </div>
      </div>
    </>
  );
};

export default BottomSheet;
export { SHEET_STATES };
