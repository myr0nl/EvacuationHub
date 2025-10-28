import React, { useState, useCallback, useMemo, memo, useEffect } from 'react';
import { MapPin, Flame, Users, Trash2, ChevronRight, ChevronDown, ClipboardList, RefreshCw } from 'lucide-react';
import { DISASTER_ICONS, SOURCE_ICONS, getDisasterIcon } from '../config/icons';
import './DisasterSidebar.css';

// PERFORMANCE OPTIMIZATION: Helper functions moved outside component to prevent recreation on every render
// These are pure functions that don't need access to component state or props
const getDisasterIconComponent = (item) => {
  // For user reports, return icon based on disaster type
  if (item.source === 'user_report' || item.source === 'user_report_authenticated') {
    return getDisasterIcon(item.disaster_type);
  }
  // For official sources, return source-specific icon
  if (item.source === 'nasa_firms') return SOURCE_ICONS.nasa_firms;
  if (item.source === 'noaa_weather') return SOURCE_ICONS.noaa_weather;
  return DISASTER_ICONS.other;
};

const getSeverityColor = (severity) => {
  const severityLower = (severity || 'unknown').toLowerCase();
  const colorMap = {
    critical: '#d32f2f',   // Dark red
    extreme: '#d32f2f',    // Dark red
    high: '#f57c00',       // Orange
    severe: '#f57c00',     // Orange
    medium: '#ffa726',     // Light orange
    moderate: '#ffa726',   // Light orange
    low: '#fbc02d',        // Yellow
    minor: '#fbc02d',      // Yellow
    unknown: '#757575'     // Gray
  };
  return colorMap[severityLower] || colorMap.unknown;
};

const formatLocation = (item) => {
  if (item.location) return item.location;
  return `${item.latitude?.toFixed(3)}, ${item.longitude?.toFixed(3)}`;
};

function DisasterSidebar({
  reports,
  wildfires,
  weatherAlerts,
  onFilterChange,
  onItemHover,
  onItemClick,
  onDeleteReport,
  currentUser,
  onGetRoute,
  onMarkAddressed,
  onShare,
  isOpen = false
}) {
  const [filters, setFilters] = useState({
    showReports: true,
    showWildfires: true,
    showWeatherAlerts: true,
    severityFilter: 'all',
    maxAgeHours: 'all' // all, 1, 6, 24, 48
  });

  const [isScrolling, setIsScrolling] = useState(false); // FIX: Track scrolling state to prevent flicker
  const [expandedCategories, setExpandedCategories] = useState(new Set()); // Track which categories are expanded

  /**
   * SIMPLIFIED: No filtering - just return all dataPoints
   * Filters are only applied at the data source level (showReports, showWildfires, showWeatherAlerts)
   */
  const filterDataPoints = useCallback((dataPoints, currentFilters, currentSearchTerm) => {
    // No filtering needed - just return all data points
    // The data source filtering is already done when combining reports/wildfires/alerts
    return dataPoints;
  }, []); // Empty deps - pure function

  /**
   * PERFORMANCE OPTIMIZATION: Memoized combined and filtered data
   * Only recalculates when props (reports, wildfires, weatherAlerts), filters, or search changes
   * Prevents duplicate filtering logic that was running in both the render and handleFilterChange
   */
  const allDataPoints = useMemo(() => {
    return filterDataPoints(
      [
        ...(filters.showReports ? reports : []),
        ...(filters.showWildfires ? wildfires : []),
        ...(filters.showWeatherAlerts ? weatherAlerts : [])
      ],
      filters,
      '' // No search term functionality currently
    );
  }, [reports, wildfires, weatherAlerts, filters, filterDataPoints]);

  /**
   * PERFORMANCE OPTIMIZATION: Memoized filter change handler
   * Prevents recreation on every render, only when dependencies change
   */
  // Toggle category expansion
  const toggleCategory = useCallback((category) => {
    setExpandedCategories(prev => {
      const newSet = new Set(prev);
      if (newSet.has(category)) {
        newSet.delete(category);
      } else {
        newSet.add(category);
      }
      return newSet;
    });
  }, []);

  const handleFilterChange = useCallback((filterName, value) => {
    const newFilters = { ...filters, [filterName]: value };
    setFilters(newFilters);

    // Calculate the filtered data with the new filters using reusable function
    const filteredData = filterDataPoints(
      [
        ...(newFilters.showReports ? reports : []),
        ...(newFilters.showWildfires ? wildfires : []),
        ...(newFilters.showWeatherAlerts ? weatherAlerts : [])
      ],
      newFilters,
      '' // No search term functionality currently
    );

    if (onFilterChange) {
      onFilterChange(filteredData);
    }
  }, [filters, reports, wildfires, weatherAlerts, filterDataPoints, onFilterChange]);

  /**
   * CRITICAL FIX: Notify parent component when filtered data changes
   * This ensures the Map component receives data on initial mount and when filters/data update
   */
  useEffect(() => {
    if (onFilterChange) {
      onFilterChange(allDataPoints);
    }
  }, [allDataPoints, onFilterChange]);

  /**
   * FIX: Detect scrolling to prevent map marker flicker
   * When user scrolls the sidebar, mouse enters/leaves items rapidly causing constant hover state changes
   * This temporarily disables hover events during scroll to prevent map re-renders
   */
  useEffect(() => {
    const sidebarList = document.querySelector('.sidebar-list');
    if (!sidebarList) return;

    let scrollTimeout;

    const handleScroll = () => {
      // Set scrolling state to true immediately
      if (!isScrolling) {
        setIsScrolling(true);
      }

      // Clear any existing timeout
      clearTimeout(scrollTimeout);

      // Set timeout to clear scrolling state after 150ms of no scroll
      scrollTimeout = setTimeout(() => {
        setIsScrolling(false);
      }, 150);
    };

    sidebarList.addEventListener('scroll', handleScroll, { passive: true });

    return () => {
      sidebarList.removeEventListener('scroll', handleScroll);
      clearTimeout(scrollTimeout);
    };
  }, [isScrolling]);

  /**
   * PERFORMANCE OPTIMIZATION: Memoized grouped data
   * Only recalculates when allDataPoints changes
   * Prevents filtering by source on every render
   */
  const groupedData = useMemo(() => {
    return {
      'User Reports': allDataPoints.filter(d => d.source === 'user_report' || d.source === 'user_report_authenticated'),
      'Wildfires': allDataPoints.filter(d => d.source === 'nasa_firms'),
      'Weather Alerts': allDataPoints.filter(d => d.source === 'noaa')
    };
  }, [allDataPoints]);

  return (
    <div className={`disaster-sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <h2>
          <ClipboardList size={20} strokeWidth={2} className="header-icon" />
          Disaster List
        </h2>
      </div>

      <>
          <div className="sidebar-filters">
            <div className="filter-group">
              <h3>Data Sources</h3>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={filters.showReports}
                  onChange={(e) => handleFilterChange('showReports', e.target.checked)}
                />
                <span>User Reports ({reports.length})</span>
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={filters.showWildfires}
                  onChange={(e) => handleFilterChange('showWildfires', e.target.checked)}
                />
                <span>Wildfires ({wildfires.length})</span>
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={filters.showWeatherAlerts}
                  onChange={(e) => handleFilterChange('showWeatherAlerts', e.target.checked)}
                />
                <span>Weather Alerts ({weatherAlerts.length})</span>
              </label>
            </div>
          </div>

          <div className="sidebar-stats">
            <div className="stat-item">
              <span className="stat-label">Showing:</span>
              <span className="stat-value">{allDataPoints.length}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Total:</span>
              <span className="stat-value">
                {reports.length + wildfires.length + weatherAlerts.length}
              </span>
            </div>
          </div>

          <div className="sidebar-list">
            {Object.entries(groupedData).map(([category, items]) => {
              if (items.length === 0) return null;
              const isExpanded = expandedCategories.has(category);

              return (
                <div key={category} className="disaster-category">
                  <h4
                    className="category-header clickable"
                    onClick={() => toggleCategory(category)}
                    style={{ cursor: 'pointer' }}
                  >
                    <span className="category-toggle">
                      {isExpanded ? (
                        <ChevronDown size={16} strokeWidth={2} />
                      ) : (
                        <ChevronRight size={16} strokeWidth={2} />
                      )}
                    </span>
                    {category} ({items.length})
                  </h4>
                  {isExpanded && (
                  <div className="category-items">
                    {items.map((item, index) => {
                      const itemKey = item.id || `${category}-${index}`;

                      // Always use list view (detailed view mode removed for simplification)
                      return (
                        <div key={itemKey} className="disaster-item-wrapper">
                          <button
                            className="disaster-item"
                            onClick={() => onItemClick && onItemClick(item)}
                            onMouseEnter={() => !isScrolling && onItemHover && onItemHover(item)}
                            onMouseLeave={() => !isScrolling && onItemHover && onItemHover(null)}
                            onFocus={() => onItemHover && onItemHover(item)}
                            onBlur={() => onItemHover && onItemHover(null)}
                            aria-label={`${item.disaster_type || item.type || item.event || 'Disaster'} at ${formatLocation(item)}`}
                          >
                            <div className="item-header">
                              <span className="item-icon">
                                {React.createElement(getDisasterIconComponent(item), { size: 18, strokeWidth: 2 })}
                              </span>
                              <span className="item-type">
                                {item.disaster_type || item.type || item.event || 'Unknown'}
                              </span>
                              {item.severity && (
                                <span
                                  className="item-severity"
                                  style={{ backgroundColor: getSeverityColor(item.severity) }}
                                >
                                  {item.severity}
                                </span>
                              )}
                            </div>
                            <div className="item-description">
                              {item.description || item.headline || item.event || 'No description'}
                            </div>
                            <div className="item-location">
                              <MapPin size={14} strokeWidth={2} className="location-icon" />
                              {formatLocation(item)}
                            </div>
                            {item.brightness && (
                              <div className="item-detail">
                                <Flame size={14} strokeWidth={2} className="detail-icon" />
                                Brightness: {item.brightness}°K
                              </div>
                            )}
                            {item.affected_population && (
                              <div className="item-detail">
                                <Users size={14} strokeWidth={2} className="detail-icon" />
                                Affected: {item.affected_population}
                              </div>
                            )}
                          </button>
                          {(item.source === 'user_report' || item.source === 'user_report_authenticated') && onDeleteReport && (() => {
                            // Only show delete button if:
                            // 1. User is logged in AND
                            // 2. (Report has no user_id (legacy) OR user owns the report)
                            const canDelete = currentUser && (!item.user_id || item.user_id === currentUser.uid);
                            return canDelete;
                          })() && (
                            <button
                              className="delete-button"
                              onClick={(e) => {
                                e.stopPropagation();
                                if (window.confirm('Are you sure you want to delete this report?')) {
                                  onDeleteReport(item.id);
                                }
                              }}
                              aria-label={`Delete ${item.disaster_type || item.type || 'disaster'} report`}
                            >
                              <Trash2 size={14} strokeWidth={2} className="delete-icon" />
                              Delete
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  )}
                </div>
              );
            })}

            {allDataPoints.length === 0 && (
              <div className="no-results">
                <p>No disasters match your filters</p>
              </div>
            )}
          </div>
        </>
    </div>
  );
}

/**
 * PERFORMANCE OPTIMIZATION: Wrap component with React.memo
 * Custom comparison function to prevent unnecessary re-renders
 * Only re-renders when props actually change (shallow comparison for arrays/objects)
 */
export default memo(DisasterSidebar, (prevProps, nextProps) => {
  // Compare arrays by length and reference (parent should provide stable references)
  return (
    prevProps.reports === nextProps.reports &&
    prevProps.wildfires === nextProps.wildfires &&
    prevProps.weatherAlerts === nextProps.weatherAlerts &&
    prevProps.onFilterChange === nextProps.onFilterChange &&
    prevProps.onItemHover === nextProps.onItemHover &&
    prevProps.onItemClick === nextProps.onItemClick &&
    prevProps.onDeleteReport === nextProps.onDeleteReport &&
    prevProps.currentUser === nextProps.currentUser &&
    prevProps.onGetRoute === nextProps.onGetRoute &&
    prevProps.onMarkAddressed === nextProps.onMarkAddressed &&
    prevProps.onShare === nextProps.onShare
  );
});
