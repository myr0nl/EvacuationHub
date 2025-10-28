import React, { useState, useRef, useEffect, useCallback } from 'react';
import { User, Flame, CloudRain } from 'lucide-react';
import './FilterBottomSheet.css';

/**
 * FilterBottomSheet - Mobile bottom sheet for disaster filters
 *
 * A draggable bottom sheet modal with 3 states: collapsed (hidden), peek (40vh), expanded (85vh).
 * Supports touch gestures for dragging and includes backdrop overlay.
 *
 * @param {boolean} isOpen - Whether the bottom sheet is visible
 * @param {function} onClose - Handler to close the bottom sheet
 * @param {object} filters - Current filter state
 * @param {object} counts - Data counts for each source
 * @param {function} onFilterChange - Handler for filter changes
 * @param {function} onClearAll - Handler to clear all filters
 */
function FilterBottomSheet({
  isOpen,
  onClose,
  filters = {},
  counts = {},
  onFilterChange,
  onClearAll
}) {
  const [sheetState, setSheetState] = useState('peek'); // 'collapsed', 'peek', 'expanded'
  const [dragStartY, setDragStartY] = useState(null);
  const [currentTranslateY, setCurrentTranslateY] = useState(0);
  const sheetRef = useRef(null);
  const dragHandleRef = useRef(null);

  // Reset to peek state when opening
  useEffect(() => {
    if (isOpen) {
      setSheetState('peek');
      setCurrentTranslateY(0);
    }
  }, [isOpen]);

  // Calculate active filter count
  const activeFilterCount = [
    filters.showReports,
    filters.showWildfires,
    filters.showWeatherAlerts
  ].filter(Boolean).length;

  const totalCount = (counts.userReports || 0) + (counts.wildfires || 0) + (counts.weatherAlerts || 0);
  const showingCount = counts.showing || 0;

  // Handle touch start
  const handleTouchStart = useCallback((e) => {
    // Only allow dragging from the handle area
    if (!dragHandleRef.current?.contains(e.target)) return;

    setDragStartY(e.touches[0].clientY);
  }, []);

  // Handle touch move
  const handleTouchMove = useCallback((e) => {
    if (dragStartY === null) return;

    const deltaY = e.touches[0].clientY - dragStartY;

    // Only allow dragging down from expanded, or up/down from peek
    if (sheetState === 'expanded' && deltaY < 0) {
      return; // Can't drag up when already expanded
    }

    setCurrentTranslateY(Math.max(0, deltaY)); // Prevent negative values (dragging up)
  }, [dragStartY, sheetState]);

  // Handle touch end
  const handleTouchEnd = useCallback(() => {
    if (dragStartY === null) return;

    const threshold = 50; // Pixels to trigger state change

    if (currentTranslateY > threshold) {
      // Dragged down significantly
      if (sheetState === 'expanded') {
        setSheetState('peek');
      } else if (sheetState === 'peek') {
        onClose(); // Close the sheet
      }
    } else if (currentTranslateY < -threshold) {
      // Dragged up significantly
      if (sheetState === 'peek') {
        setSheetState('expanded');
      }
    }

    // Reset drag state
    setDragStartY(null);
    setCurrentTranslateY(0);
  }, [dragStartY, currentTranslateY, sheetState, onClose]);

  // Handle backdrop click
  const handleBackdropClick = useCallback(() => {
    onClose();
  }, [onClose]);

  // Prevent clicks on sheet from closing it
  const handleSheetClick = useCallback((e) => {
    e.stopPropagation();
  }, []);

  // Handle clear all filters
  const handleClearAll = useCallback(() => {
    if (onClearAll) {
      onClearAll();
    }
  }, [onClearAll]);

  // Handle individual filter toggle
  const handleFilterToggle = useCallback((filterName) => {
    if (onFilterChange) {
      onFilterChange(filterName, !filters[filterName]);
    }
  }, [filters, onFilterChange]);

  // Get sheet height based on state
  const getSheetHeight = () => {
    if (sheetState === 'peek') return '40vh';
    if (sheetState === 'expanded') return '85vh';
    return '0vh';
  };

  // Calculate transform for dragging
  const getTransform = () => {
    if (currentTranslateY > 0) {
      return `translateY(${currentTranslateY}px)`;
    }
    return 'translateY(0)';
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop overlay */}
      <div
        className={`filter-bottom-sheet-backdrop ${isOpen ? 'visible' : ''}`}
        onClick={handleBackdropClick}
        role="presentation"
      />

      {/* Bottom sheet */}
      <div
        ref={sheetRef}
        className={`filter-bottom-sheet ${isOpen ? 'open' : ''} ${sheetState}`}
        style={{
          height: getSheetHeight(),
          transform: getTransform()
        }}
        onClick={handleSheetClick}
        role="dialog"
        aria-modal="true"
        aria-labelledby="bottom-sheet-title"
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        {/* Drag handle */}
        <div
          ref={dragHandleRef}
          className="drag-handle-container"
          role="button"
          aria-label="Drag to expand or collapse"
          tabIndex={0}
        >
          <div className="drag-handle" aria-hidden="true" />
        </div>

        {/* Header */}
        <div className="bottom-sheet-header">
          <div className="header-content">
            <h2 id="bottom-sheet-title" className="sheet-title">
              Filter Disasters
            </h2>
            <div className="header-count">
              {activeFilterCount} of 3 active
            </div>
          </div>
          <button
            className="clear-all-btn"
            onClick={handleClearAll}
            disabled={activeFilterCount === 0}
            aria-label="Clear all filters"
          >
            Clear All
          </button>
        </div>

        {/* Filter content */}
        <div className="bottom-sheet-content">
          {/* Data Sources Section */}
          <div className="filter-section">
            <h3 className="section-title">Data Sources</h3>
            <div className="filter-options">
              {/* User Reports */}
              <label className="filter-option">
                <input
                  type="checkbox"
                  role="checkbox"
                  aria-checked={filters.showReports}
                  checked={filters.showReports}
                  onChange={() => handleFilterToggle('showReports')}
                  tabIndex={0}
                />
                <span className="option-content">
                  <User className="option-icon" size={24} strokeWidth={2} aria-hidden="true" />
                  <span className="option-label">User Reports</span>
                  <span className="option-count">{counts.userReports || 0}</span>
                </span>
              </label>

              {/* Wildfires */}
              <label className="filter-option">
                <input
                  type="checkbox"
                  role="checkbox"
                  aria-checked={filters.showWildfires}
                  checked={filters.showWildfires}
                  onChange={() => handleFilterToggle('showWildfires')}
                  tabIndex={0}
                />
                <span className="option-content">
                  <Flame className="option-icon" size={24} strokeWidth={2} aria-hidden="true" />
                  <span className="option-label">Wildfires</span>
                  <span className="option-count">{counts.wildfires || 0}</span>
                </span>
              </label>

              {/* Weather Alerts */}
              <label className="filter-option">
                <input
                  type="checkbox"
                  role="checkbox"
                  aria-checked={filters.showWeatherAlerts}
                  checked={filters.showWeatherAlerts}
                  onChange={() => handleFilterToggle('showWeatherAlerts')}
                  tabIndex={0}
                />
                <span className="option-content">
                  <CloudRain className="option-icon" size={24} strokeWidth={2} aria-hidden="true" />
                  <span className="option-label">Weather Alerts</span>
                  <span className="option-count">{counts.weatherAlerts || 0}</span>
                </span>
              </label>
            </div>
          </div>
        </div>

        {/* Summary footer */}
        <div className="bottom-sheet-footer">
          <div className="summary">
            <span className="summary-label">SHOWING:</span>
            <span className="summary-value">{showingCount}</span>
            <span className="summary-divider">|</span>
            <span className="summary-label">TOTAL:</span>
            <span className="summary-value">{totalCount}</span>
          </div>
        </div>
      </div>
    </>
  );
}

export default FilterBottomSheet;
