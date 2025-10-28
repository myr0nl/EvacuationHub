/**
 * Geospatial utilities for distance calculations and coordinate validation
 *
 * This module provides:
 * - Haversine distance calculation (great circle distance)
 * - Coordinate validation (with equator/prime meridian edge case handling)
 * - Coordinate normalization
 *
 * @module utils/geo
 */

/**
 * Validates geographic coordinates, including edge cases at equator (0°) and prime meridian (0°).
 *
 * Edge Cases Handled:
 * - Equator (latitude = 0): Valid and common for equatorial countries
 * - Prime Meridian (longitude = 0): Valid and common for West Africa/UK
 * - Poles (latitude = ±90): Valid endpoints
 * - International Date Line (longitude = ±180): Valid, normalized to 180
 *
 * @param {number} latitude - Latitude in decimal degrees (-90 to 90)
 * @param {number} longitude - Longitude in decimal degrees (-180 to 180)
 * @returns {boolean} True if coordinates are valid, false otherwise
 *
 * @example
 * // Valid coordinates
 * isValidCoordinates(0, 0)           // true - Gulf of Guinea (equator + prime meridian)
 * isValidCoordinates(0, -122.4194)   // true - Equator crossing Pacific
 * isValidCoordinates(37.7749, 0)     // true - Prime meridian in Algeria
 * isValidCoordinates(90, 0)          // true - North Pole
 * isValidCoordinates(-90, 0)         // true - South Pole
 *
 * // Invalid coordinates
 * isValidCoordinates(91, 0)          // false - latitude out of range
 * isValidCoordinates(0, 181)         // false - longitude out of range
 * isValidCoordinates(null, 0)        // false - invalid type
 * isValidCoordinates(NaN, 0)         // false - not a number
 */
export function isValidCoordinates(latitude, longitude) {
  // Type check - must be actual numbers
  if (typeof latitude !== 'number' || typeof longitude !== 'number') {
    return false;
  }

  // NaN check - reject invalid numeric values
  if (Number.isNaN(latitude) || Number.isNaN(longitude)) {
    return false;
  }

  // Infinity check - reject infinite values
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return false;
  }

  // Range validation
  // IMPORTANT: Use <= and >= to include 0 (equator/prime meridian edge case)
  // Latitude: -90 (South Pole) to +90 (North Pole), inclusive
  // Longitude: -180 (antimeridian west) to +180 (antimeridian east), inclusive
  return latitude >= -90 && latitude <= 90 && longitude >= -180 && longitude <= 180;
}

/**
 * Normalizes longitude to the range [-180, 180].
 * Useful for handling coordinates that cross the International Date Line.
 *
 * @param {number} longitude - Longitude in decimal degrees
 * @returns {number} Normalized longitude in range [-180, 180]
 *
 * @example
 * normalizeLongitude(181)   // -179
 * normalizeLongitude(-181)  // 179
 * normalizeLongitude(360)   // 0
 * normalizeLongitude(0)     // 0 (prime meridian)
 */
export function normalizeLongitude(longitude) {
  // Normalize to [-180, 180]
  let normalized = longitude % 360;
  if (normalized > 180) {
    normalized -= 360;
  } else if (normalized < -180) {
    normalized += 360;
  }
  return normalized;
}

/**
 * Calculate the great circle distance between two points on Earth using the Haversine formula.
 *
 * The Haversine formula determines the shortest distance over the earth's surface,
 * giving an "as-the-crow-flies" distance between the points (ignoring elevation differences).
 *
 * Accuracy:
 * - Typically within 0.5% for most terrestrial distances
 * - Assumes Earth is a perfect sphere (good approximation for most use cases)
 * - For extreme precision requirements, use Vincenty's formula instead
 *
 * Performance:
 * - O(1) time complexity
 * - Uses precomputed constants and efficient trig operations
 *
 * @param {number} lat1 - First point latitude in decimal degrees (-90 to 90)
 * @param {number} lon1 - First point longitude in decimal degrees (-180 to 180)
 * @param {number} lat2 - Second point latitude in decimal degrees (-90 to 90)
 * @param {number} lon2 - Second point longitude in decimal degrees (-180 to 180)
 * @returns {number} Distance in miles (statute miles, not nautical miles)
 *
 * @throws {Error} If any coordinate is invalid
 *
 * @example
 * // Distance between San Francisco and Los Angeles
 * calculateDistance(37.7749, -122.4194, 34.0522, -118.2437)  // ~347.4 miles
 *
 * // Distance between New York and Boston
 * calculateDistance(40.7128, -74.0060, 42.3601, -71.0589)    // ~190.4 miles
 *
 * // Same point (should be 0)
 * calculateDistance(37.7749, -122.4194, 37.7749, -122.4194)  // 0.0 miles
 *
 * // Equator to prime meridian crossing
 * calculateDistance(0, 0, 0, 1)  // ~69.17 miles (1 degree longitude at equator)
 *
 * // Crossing International Date Line (longitude wrapping)
 * calculateDistance(40, 179, 40, -179)  // ~154 miles (only 2° apart)
 */
export function calculateDistance(lat1, lon1, lat2, lon2) {
  // Validate all coordinates
  if (!isValidCoordinates(lat1, lon1)) {
    throw new Error(`Invalid first coordinate: (${lat1}, ${lon1})`);
  }
  if (!isValidCoordinates(lat2, lon2)) {
    throw new Error(`Invalid second coordinate: (${lat2}, ${lon2})`);
  }

  // Earth's mean radius in miles (statute miles)
  const R = 3958.8;

  // Convert decimal degrees to radians
  const lat1Rad = lat1 * Math.PI / 180;
  const lon1Rad = lon1 * Math.PI / 180;
  const lat2Rad = lat2 * Math.PI / 180;
  const lon2Rad = lon2 * Math.PI / 180;

  // Calculate differences
  const dLat = lat2Rad - lat1Rad;
  const dLon = lon2Rad - lon1Rad;

  // Haversine formula
  // a = sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1Rad) * Math.cos(lat2Rad) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);

  // c = 2 * atan2(√a, √(1−a))
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  // Distance = R * c
  const distance = R * c;

  return distance;
}

/**
 * Checks if a point is within a certain radius of a center point.
 * Useful for proximity checks without calculating exact distance.
 *
 * @param {number} centerLat - Center point latitude
 * @param {number} centerLon - Center point longitude
 * @param {number} pointLat - Point to check latitude
 * @param {number} pointLon - Point to check longitude
 * @param {number} radiusMiles - Radius in miles
 * @returns {boolean} True if point is within radius, false otherwise
 *
 * @example
 * isWithinRadius(37.7749, -122.4194, 37.8, -122.4, 5)  // true (nearby in SF)
 * isWithinRadius(37.7749, -122.4194, 40.7128, -74.0060, 100)  // false (SF to NYC)
 */
export function isWithinRadius(centerLat, centerLon, pointLat, pointLon, radiusMiles) {
  const distance = calculateDistance(centerLat, centerLon, pointLat, pointLon);
  return distance <= radiusMiles;
}
