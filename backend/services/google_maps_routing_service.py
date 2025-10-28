"""
Google Maps Routing Service for Baseline Shortest Path

Provides the absolute shortest/fastest route without disaster avoidance as a
baseline comparison. This helps users understand the tradeoff between speed
and safety when choosing disaster-aware routes.

Features:
- Calculate single optimal route (fastest or shortest)
- Professional road data with real-time traffic (optional)
- No disaster avoidance - pure shortest path algorithm
- Used as baseline reference for safety-aware routes

Author: Disaster Alert System
Date: 2025-10-18
"""

import logging
import os
from typing import Dict, List, Optional, Any
import requests

# Configure logging
logger = logging.getLogger(__name__)


class GoogleMapsRoutingService:
    """
    Service for calculating baseline shortest/fastest routes using Google Maps API.

    Google Maps provides the industry-standard shortest path without any disaster
    avoidance. This route serves as a baseline to show users how much extra
    distance/time they're adding by choosing safer routes that avoid disasters.
    """

    # Google Maps API Configuration
    GOOGLE_BASE_URL = "https://maps.googleapis.com/maps/api/directions/json"
    GOOGLE_TIMEOUT_SECONDS = 10

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Google Maps Routing Service.

        Args:
            api_key: Google Maps API key. If None, reads from GOOGLE_MAPS_API_KEY env variable

        Raises:
            ValueError: If API key is not provided and not found in environment
        """
        self.api_key = api_key or os.getenv('GOOGLE_MAPS_API_KEY')
        if not self.api_key:
            logger.warning("GOOGLE_MAPS_API_KEY not provided - Google Maps routing will be unavailable")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("Google Maps Routing Service initialized successfully")

    def is_enabled(self) -> bool:
        """Check if Google Maps routing is available (API key configured)."""
        return self.enabled

    def calculate_baseline_route(
        self,
        origin: Dict[str, float],
        destination: Dict[str, float],
        mode: str = "shortest"
    ) -> Dict[str, Any]:
        """
        Calculate baseline shortest/fastest route without disaster avoidance.

        This provides a reference point showing the optimal route if disasters
        were not a concern. Users can compare this to safer routes to understand
        the tradeoff between speed and safety.

        Args:
            origin: {"lat": float, "lon": float}
            destination: {"lat": float, "lon": float}
            mode: "shortest" or "fastest" (default: "shortest")

        Returns:
            Dictionary with:
            - route: Single route object with geometry, distance, duration
            - is_baseline: Always True
            - provider: "Google Maps"

        Raises:
            requests.exceptions.RequestException: If API request fails
            ValueError: If response format is invalid
        """
        if not self.enabled:
            raise ValueError("Google Maps Routing Service not enabled - API key not configured")

        logger.info(f"Calculating baseline {mode} route from {origin} to {destination}")

        # Build request parameters
        params = self._build_request_params(origin, destination, mode)

        # Make API request
        try:
            response = requests.get(
                self.GOOGLE_BASE_URL,
                params=params,
                timeout=self.GOOGLE_TIMEOUT_SECONDS
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            logger.error("Google Maps API request timed out")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Google Maps API request failed: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            raise

        # Parse response
        try:
            data = response.json()

            # Check for Google Maps API errors
            if data.get('status') != 'OK':
                error_msg = data.get('error_message', data.get('status', 'Unknown error'))
                logger.error(f"Google Maps API error: {error_msg}")
                raise ValueError(f"Google Maps API error: {error_msg}")

            route = self._parse_google_response(data, mode)
            logger.info(f"Successfully calculated baseline route: {route['distance_mi']:.2f}mi, {route['duration_seconds']}s")

            return {
                'route': route,
                'is_baseline': True,
                'provider': 'Google Maps'
            }
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to parse Google Maps API response: {str(e)}")
            logger.error(f"Response data: {response.text[:500]}")
            raise ValueError(f"Invalid response from Google Maps API: {str(e)}")

    def _build_request_params(
        self,
        origin: Dict[str, float],
        destination: Dict[str, float],
        mode: str = "shortest"
    ) -> Dict[str, str]:
        """
        Build query parameters for Google Maps Directions API request.

        Args:
            origin: {"lat": float, "lon": float}
            destination: {"lat": float, "lon": float}
            mode: "shortest" or "fastest"

        Returns:
            Dictionary of query parameters
        """
        params = {
            'origin': f"{origin['lat']},{origin['lon']}",
            'destination': f"{destination['lat']},{destination['lon']}",
            'mode': 'driving',
            'key': self.api_key,
            'units': 'metric'
        }

        # Optimize for distance (shortest) or time (fastest)
        if mode == "shortest":
            # Request route optimized for distance
            params['avoid'] = ''  # No avoidances
            # Note: Google doesn't have explicit "shortest distance" mode
            # By default it optimizes for time, but we can use duration_in_traffic=false
        else:
            # Request route optimized for time (default behavior)
            params['departure_time'] = 'now'  # Use real-time traffic

        return params

    def _parse_google_response(self, data: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """
        Parse Google Maps Directions API response into standardized route format.

        Google response format:
        {
          "routes": [
            {
              "legs": [
                {
                  "distance": {"value": 12345, "text": "12.3 km"},
                  "duration": {"value": 1234, "text": "20 mins"},
                  "steps": [...]
                }
              ],
              "overview_polyline": {"points": "encoded-polyline-string"}
            }
          ]
        }

        Args:
            data: Raw Google Maps API response
            mode: "shortest" or "fastest"

        Returns:
            Route dictionary compatible with our format
        """
        if 'routes' not in data or not data['routes']:
            raise ValueError("No routes found in Google Maps API response")

        google_route = data['routes'][0]  # Google returns best route first
        leg = google_route['legs'][0]  # Single leg for origin→destination

        # Decode polyline to coordinates
        geometry = self._decode_polyline(google_route['overview_polyline']['points'])

        # Extract waypoints from steps
        waypoints = []
        for step in leg.get('steps', []):
            waypoint = {
                'instruction': step.get('html_instructions', '').replace('<b>', '').replace('</b>', '').replace('<div style="font-size:0.9em">', ' ').replace('</div>', ''),  # Strip HTML tags
                'distance_mi': step.get('distance', {}).get('value', 0) / 1609.34,  # Convert meters to miles
                'duration_seconds': step.get('duration', {}).get('value', 0),
                'type': step.get('maneuver', 'unknown')  # Google uses 'maneuver' for turn type
            }
            waypoints.append(waypoint)

        route = {
            'route_id': 'google_baseline',
            'distance_mi': leg['distance']['value'] / 1609.34,  # Convert meters to miles
            'duration_seconds': leg['duration']['value'],
            'geometry': geometry,  # List of [lon, lat] pairs
            'provider': 'Google Maps',
            'is_baseline': True,
            'is_fastest': (mode == "fastest"),
            'is_shortest': (mode == "shortest"),
            'safety_score': 0.0,  # No safety analysis for baseline
            'intersects_disasters': False,  # Not analyzed (no avoidance)
            'disasters_nearby': 0,  # Not analyzed
            'min_disaster_distance_mi': None,  # None instead of float('inf') for JSON compatibility
            'waypoints': waypoints  # Populated from Google Maps steps
        }

        logger.debug(f"Parsed Google Maps route: {route['distance_mi']:.2f}mi, {route['duration_seconds']}s")
        return route

    def _decode_polyline(self, encoded: str) -> List[List[float]]:
        """
        Decode Google Maps polyline encoding to coordinates.

        Google uses a specific polyline encoding algorithm.
        See: https://developers.google.com/maps/documentation/utilities/polylinealgorithm

        Args:
            encoded: Encoded polyline string

        Returns:
            List of [lon, lat] coordinate pairs
        """
        try:
            import polyline
            decoded = polyline.decode(encoded)
            # polyline.decode returns [(lat, lon), ...] - convert to [lon, lat]
            return [[coord[1], coord[0]] for coord in decoded]
        except ImportError:
            logger.warning("polyline library not installed - returning empty geometry")
            logger.info("Install with: pip install polyline")
            return []
        except Exception as e:
            logger.error(f"Failed to decode polyline: {str(e)}")
            return []
