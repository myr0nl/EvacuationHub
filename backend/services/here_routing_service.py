"""
HERE Routing Service for Disaster-Aware Navigation

Provides fallback routing capabilities when OpenRouteService fails due to road
mapping limitations. Uses HERE Routing API v8 with polygon avoidance support.

Features:
- Calculate up to 3 alternative routes using HERE driving-car profile
- Support for up to 20 polygon avoidance areas per request
- Better road data coverage compared to OpenStreetMap
- Handles API failures gracefully with detailed error messages
- Compatible with existing safety scoring pipeline

Author: Disaster Alert System
Date: 2025-10-18
"""

import logging
import os
from typing import Dict, List, Optional, Any
import requests

# Configure logging
logger = logging.getLogger(__name__)


class HERERoutingService:
    """
    Service for calculating routes using HERE Routing API v8 as a fallback.

    HERE provides better road data coverage than OpenStreetMap, making it ideal
    for locations where ORS fails due to incomplete mapping data.
    """

    # HERE API Configuration
    HERE_BASE_URL = "https://router.hereapi.com/v8/routes"
    HERE_TIMEOUT_SECONDS = 30

    # HERE supports up to 20 polygons per request
    MAX_POLYGONS = 20

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the HERE Routing Service.

        Args:
            api_key: HERE API key. If None, reads from HERE_API_KEY env variable

        Raises:
            ValueError: If API key is not provided and not found in environment
        """
        self.api_key = api_key or os.getenv('HERE_API_KEY')
        if not self.api_key:
            logger.warning("HERE_API_KEY not provided - HERE routing will be unavailable")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("HERE Routing Service initialized successfully")

    def is_enabled(self) -> bool:
        """Check if HERE routing is available (API key configured)."""
        return self.enabled

    def calculate_routes(
        self,
        origin: Dict[str, float],
        destination: Dict[str, float],
        disaster_polygons: List[Dict[str, Any]] = None,
        alternatives: int = 3
    ) -> Dict[str, Any]:
        """
        Calculate routes using HERE Routing API with disaster avoidance.

        Args:
            origin: {"lat": float, "lon": float}
            destination: {"lat": float, "lon": float}
            disaster_polygons: List of GeoJSON Polygon objects to avoid
            alternatives: Number of alternative routes (1-3, default 3)

        Returns:
            Dictionary with:
            - routes: List of route objects with geometry, distance, duration
            - avoided_disasters: List of disasters that were avoided

        Raises:
            requests.exceptions.RequestException: If API request fails
            ValueError: If response format is invalid
        """
        if not self.enabled:
            raise ValueError("HERE Routing Service not enabled - API key not configured")

        logger.info(f"Calculating route from {origin} to {destination} with HERE API")

        # Build request parameters
        params = self._build_request_params(origin, destination, disaster_polygons, alternatives)

        # Make API request
        warning_message = None
        try:
            response = requests.get(
                self.HERE_BASE_URL,
                params=params,
                timeout=self.HERE_TIMEOUT_SECONDS
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            logger.error("HERE API request timed out")
            raise
        except requests.exceptions.RequestException as e:
            # Handle 414 Request-URI Too Large error
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 414:
                logger.warning(f"HERE API URI too large (414) - too many disaster polygons ({len(disaster_polygons or [])})")
                logger.info("Retrying HERE API request without disaster avoidance polygons")

                # Retry without disaster polygons
                try:
                    params_no_polygons = self._build_request_params(origin, destination, [], alternatives)
                    response = requests.get(
                        self.HERE_BASE_URL,
                        params=params_no_polygons,
                        timeout=self.HERE_TIMEOUT_SECONDS
                    )
                    response.raise_for_status()
                    warning_message = f"Too many disasters ({len(disaster_polygons or [])}) to avoid - showing shortest path instead. Routes may pass near disaster zones."
                    logger.info("Successfully calculated routes without polygon avoidance")
                except requests.exceptions.RequestException as retry_error:
                    logger.error(f"HERE API retry without polygons also failed: {str(retry_error)}")
                    raise
            else:
                logger.error(f"HERE API request failed: {str(e)}")
                if hasattr(e.response, 'text'):
                    logger.error(f"Response: {e.response.text}")
                raise

        # Parse response
        try:
            data = response.json()
            routes = self._parse_here_response(data)
            logger.info(f"Successfully calculated {len(routes)} routes with HERE API")

            result = {
                'routes': routes,
                'avoided_disasters': disaster_polygons or [],
                'provider': 'HERE'
            }

            # Add warning message if URI was too large
            if warning_message:
                result['warning'] = warning_message

            return result
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to parse HERE API response: {str(e)}")
            logger.error(f"Response data: {response.text[:500]}")
            raise ValueError(f"Invalid response from HERE API: {str(e)}")

    def _build_request_params(
        self,
        origin: Dict[str, float],
        destination: Dict[str, float],
        disaster_polygons: List[Dict[str, Any]] = None,
        alternatives: int = 3
    ) -> Dict[str, str]:
        """
        Build query parameters for HERE API request.

        Args:
            origin: {"lat": float, "lon": float}
            destination: {"lat": float, "lon": float}
            disaster_polygons: List of GeoJSON Polygon objects
            alternatives: Number of alternative routes

        Returns:
            Dictionary of query parameters
        """
        params = {
            'apiKey': self.api_key,
            'transportMode': 'car',
            'origin': f"{origin['lat']},{origin['lon']}",
            'destination': f"{destination['lat']},{destination['lon']}",
            'return': 'polyline,summary,actions',
            'alternatives': min(alternatives, 3)  # HERE supports max 3 alternatives
        }

        # Add polygon avoidance if disasters provided
        if disaster_polygons:
            avoid_areas = self._format_avoid_polygons(disaster_polygons)
            if avoid_areas:
                params['avoid[areas]'] = avoid_areas
                logger.info(f"Added {len(disaster_polygons)} disaster polygons to avoid")

        return params

    def _format_avoid_polygons(self, disaster_polygons: List[Dict[str, Any]]) -> str:
        """
        Format disaster polygons into HERE API avoid[areas] parameter.

        HERE format: polygon:lat1,lon1;lat2,lon2;lat3,lon3|polygon:lat1,lon1;...
        Note: HERE uses lat,lon order (different from GeoJSON lon,lat)

        Args:
            disaster_polygons: List of GeoJSON Polygon objects

        Returns:
            Pipe-separated string of polygon definitions
        """
        if not disaster_polygons:
            return ""

        formatted_polygons = []

        for polygon_data in disaster_polygons[:self.MAX_POLYGONS]:
            try:
                # Extract coordinates from GeoJSON Polygon
                # GeoJSON format: [[lon, lat], [lon, lat], ...]
                if polygon_data.get('type') == 'Polygon':
                    coordinates = polygon_data.get('coordinates', [[]])[0]

                    # Convert to HERE format: lat,lon;lat,lon;lat,lon
                    # Note: GeoJSON uses [lon, lat] but HERE uses lat,lon
                    coord_pairs = []
                    for coord in coordinates:
                        if len(coord) >= 2:
                            lon, lat = coord[0], coord[1]
                            coord_pairs.append(f"{lat},{lon}")

                    if coord_pairs:
                        # HERE polygon format: polygon:lat1,lon1;lat2,lon2;...
                        polygon_str = "polygon:" + ";".join(coord_pairs)
                        formatted_polygons.append(polygon_str)
                        logger.debug(f"Formatted polygon with {len(coord_pairs)} points")

            except (KeyError, IndexError, TypeError) as e:
                logger.warning(f"Skipping invalid polygon: {str(e)}")
                continue

        if not formatted_polygons:
            logger.warning("No valid polygons found after formatting")
            return ""

        # Join with pipe separator
        result = "|".join(formatted_polygons)
        logger.info(f"Formatted {len(formatted_polygons)} polygons for HERE API")
        return result

    def _parse_here_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse HERE API response into standardized route format.

        HERE response format:
        {
          "routes": [
            {
              "id": "route-id",
              "sections": [
                {
                  "summary": {
                    "duration": 1234,  // seconds
                    "length": 5678,    // meters
                  },
                  "polyline": "encoded-polyline-string",
                  "actions": [...]
                }
              ]
            }
          ]
        }

        Args:
            data: Raw HERE API response

        Returns:
            List of route dictionaries compatible with our format
        """
        if 'routes' not in data:
            raise ValueError("No routes found in HERE API response")

        routes = []
        for idx, here_route in enumerate(data['routes']):
            try:
                # HERE routes have sections - we'll use the first section
                section = here_route['sections'][0]
                summary = section['summary']

                # Decode polyline to coordinates
                geometry = self._decode_polyline(section['polyline'])

                # Transform HERE actions to our waypoint format
                waypoints = []
                for action in section.get('actions', []):
                    # Generate human-readable instruction from action type
                    action_type = action.get('action', '')
                    direction = action.get('direction', '')
                    instruction = action.get('instruction', '')

                    # If no instruction provided, generate one from action type
                    if not instruction or instruction == action_type:
                        instruction = self._generate_instruction(action_type, direction)

                    waypoint = {
                        'instruction': instruction,
                        'distance_mi': action.get('length', 0) / 1609.34,  # Convert meters to miles
                        'duration_seconds': action.get('duration', 0),
                        'type': action_type
                    }
                    waypoints.append(waypoint)

                route = {
                    'route_id': f"here_route_{idx + 1}",
                    'distance_mi': summary['length'] / 1609.34,  # Convert meters to miles
                    'duration_seconds': summary['duration'],
                    'geometry': geometry,  # List of [lon, lat] pairs
                    'waypoints': waypoints,  # Transformed from HERE actions
                    'provider': 'HERE'
                }

                routes.append(route)
                logger.debug(f"Parsed route {idx + 1}: {route['distance_mi']:.2f}mi, {route['duration_seconds']}s")

            except (KeyError, IndexError, TypeError) as e:
                logger.warning(f"Failed to parse route {idx}: {str(e)}")
                continue

        if not routes:
            raise ValueError("No valid routes found after parsing HERE response")

        return routes

    def _decode_polyline(self, encoded: str) -> List[List[float]]:
        """
        Decode HERE flexible polyline encoding to coordinates.

        HERE uses flexible polyline encoding. For now, we'll request
        the simple polyline format which is easier to decode.

        Args:
            encoded: Encoded polyline string

        Returns:
            List of [lon, lat] coordinate pairs
        """
        # Note: HERE's polyline encoding is different from Google's
        # For production, you'd use the flexpolyline library
        # pip install flexpolyline

        try:
            import flexpolyline
            decoded = flexpolyline.decode(encoded)
            # flexpolyline returns [(lat, lon), ...] - convert to [lon, lat]
            return [[coord[1], coord[0]] for coord in decoded]
        except ImportError:
            logger.warning("flexpolyline library not installed - returning empty geometry")
            logger.info("Install with: pip install flexpolyline")
            return []
        except Exception as e:
            logger.error(f"Failed to decode polyline: {str(e)}")
            return []

    def _generate_instruction(self, action_type: str, direction: str = '') -> str:
        """
        Generate human-readable instruction from HERE action type.

        Args:
            action_type: HERE action type (depart, arrive, turn, etc.)
            direction: Optional direction (left, right, etc.)

        Returns:
            Human-readable instruction string
        """
        instruction_templates = {
            'depart': 'Start your route',
            'arrive': 'Arrive at your destination',
            'turn': f'Turn {direction}' if direction else 'Turn',
            'straight': 'Continue straight',
            'keep': f'Keep {direction}' if direction else 'Keep',
            'roundabout': 'Enter roundabout',
            'uturn': 'Make a U-turn'
        }

        return instruction_templates.get(action_type, f'{action_type.capitalize()} {direction}'.strip())
