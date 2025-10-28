"""
Route Calculation Service for Disaster-Aware Navigation

Integrates with OpenRouteService (ORS) API to calculate alternative routes
while avoiding active disaster zones. Provides safety scoring and disaster
intersection analysis for each route option.

Features:
- Calculate up to 3 alternative routes using ORS driving-car profile
- Generate disaster buffer polygons based on severity levels
- Filter relevant disasters by type and recency (<48 hours)
- Calculate comprehensive safety scores (0-100) for each route
- Identify fastest route and safest route
- Handle API failures gracefully with fallback strategies

Author: Disaster Alert System
Date: 2025-10-18
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional, Any
import requests
from shapely.geometry import Point, Polygon, LineString, MultiPolygon
from shapely.ops import nearest_points
import hashlib
import json
import sys
# Add parent directory to path for utils import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.validators import CoordinateValidator
from utils.distance import haversine_distance

# Configure logging
logger = logging.getLogger(__name__)


class RouteCalculationService:
    """
    Service for calculating disaster-aware routes using OpenRouteService API.

    Provides methods to:
    - Fetch active disasters from Firebase
    - Generate buffer polygons around disasters based on severity
    - Calculate alternative routes avoiding disaster zones
    - Score routes based on safety metrics
    - Identify optimal route choices (fastest vs safest)
    """

    # ORS API Configuration
    ORS_BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    ORS_TIMEOUT_SECONDS = 30

    # Disaster buffer radii in miles (clean numbers matching confidence scorer thresholds)
    BUFFER_RADII_MI = {
        'critical': 5,    # Critical disasters: 5 mile buffer
        'extreme': 5,     # Extreme disasters: 5 mile buffer
        'high': 3,        # High severity: 3 mile buffer
        'severe': 3,      # Severe: 3 mile buffer
        'medium': 2,      # Medium severity: 2 mile buffer
        'moderate': 2,    # Moderate: 2 mile buffer
        'low': 1,         # Low severity: 1 mile buffer
        'minor': 1        # Minor: 1 mile buffer
    }
    DEFAULT_BUFFER_MI = 1  # Fallback for unknown severity

    # Disaster types to include in route avoidance
    INCLUDED_DISASTER_TYPES = {
        'wildfire', 'earthquake', 'flood', 'hurricane', 'tornado', 'volcano'
    }

    # Weather alert severities to include (NOAA alerts)
    SEVERE_WEATHER_SEVERITIES = {'Severe', 'Extreme'}

    # Disaster recency threshold (exclude disasters older than this)
    MAX_DISASTER_AGE_HOURS = 48

    # Safety score weights
    WEIGHT_MIN_DISTANCE = 0.50  # 50% weight
    WEIGHT_NEARBY_DISASTERS = 0.30  # 30% weight
    WEIGHT_ROUTE_DEVIATION = 0.20  # 20% weight

    # Nearby disaster threshold for safety scoring
    NEARBY_DISASTER_THRESHOLD_MI = 6.2

    def __init__(self, api_key: Optional[str] = None, db=None, here_service=None, google_service=None):
        """
        Initialize the Route Calculation Service.

        Args:
            api_key: OpenRouteService API key. If None, reads from ORS_API_KEY env variable
            db: Firebase Realtime Database reference
            here_service: Optional HERERoutingService instance for fallback routing
            google_service: Optional GoogleMapsRoutingService for baseline shortest path

        Raises:
            ValueError: If API key is not provided and not found in environment
        """
        self.api_key = api_key or os.getenv('ORS_API_KEY')
        if not self.api_key:
            raise ValueError("ORS_API_KEY must be provided or set as environment variable")

        self.db = db
        if not self.db:
            logger.warning("Firebase database not provided - disaster filtering will be limited")

        # Initialize HERE fallback service
        self.here_service = here_service

        # Initialize Google Maps baseline service
        self.google_service = google_service

        # Log initialization status
        services = ["ORS API"]
        if self.here_service and self.here_service.is_enabled():
            services.append("HERE fallback")
        if self.google_service and self.google_service.is_enabled():
            services.append("Google Maps baseline")
        logger.info(f"RouteCalculationService initialized with {', '.join(services)}")

    def snap_to_nearest_road(
        self,
        lat: float,
        lon: float,
        radius_meters: int = 5000
    ) -> Optional[Dict[str, float]]:
        """
        Snap coordinates to the nearest routable road.

        Uses a simple radius search - expands search radius if no road found.

        Args:
            lat: Latitude
            lon: Longitude
            radius_meters: Search radius in meters (default: 5000m = 5km)

        Returns:
            {"lat": float, "lon": float} of snapped location, or None if no road found
        """
        # Try with small incremental adjustments first
        # Most GPS inaccuracies are < 50 meters, but expand to 1km for remote areas
        test_offsets = [
            (0, 0),  # Try original first
            (0.0005, 0), (0, 0.0005), (-0.0005, 0), (0, -0.0005),  # ~50m
            (0.001, 0), (0, 0.001), (-0.001, 0), (0, -0.001),  # ~100m
            (0.002, 0), (0, 0.002), (-0.002, 0), (0, -0.002),  # ~200m
            (0.003, 0), (0, 0.003), (-0.003, 0), (0, -0.003),  # ~300m
            (0.005, 0), (0, 0.005), (-0.005, 0), (0, -0.005),  # ~500m
            (0.008, 0), (0, 0.008), (-0.008, 0), (0, -0.008),  # ~800m
            (0.01, 0), (0, 0.01), (-0.01, 0), (0, -0.01),  # ~1000m (1km)
        ]

        for lat_offset, lon_offset in test_offsets:
            test_lat = lat + lat_offset
            test_lon = lon + lon_offset

            # Quick test: try to get a route from this point to itself (very short distance)
            # ORS will fail immediately if point is not routable
            try:
                # Use a point 100m away as destination (roughly 0.001 degrees)
                test_dest_lat = test_lat + 0.001
                test_dest_lon = test_lon + 0.001

                payload = {
                    "coordinates": [[test_lon, test_lat], [test_dest_lon, test_dest_lat]]
                }

                response = requests.post(
                    self.ORS_BASE_URL,
                    json=payload,
                    headers={
                        'Authorization': self.api_key,
                        'Content-Type': 'application/json',
                        'Accept': 'application/geo+json'
                    },
                    timeout=5  # Quick timeout
                )

                data = response.json()

                # If no error, this point is routable!
                if 'features' in data and data['features']:
                    logger.info(f"Snapped ({lat}, {lon}) to ({test_lat}, {test_lon})")
                    return {"lat": test_lat, "lon": test_lon}

            except Exception as e:
                # Try next offset
                continue

        logger.warning(f"Could not snap ({lat}, {lon}) to nearest road within {radius_meters}m")
        return None

    def calculate_routes(
        self,
        origin: Dict[str, float],
        destination: Dict[str, float],
        avoid_disasters: bool = True,
        alternatives: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Calculate alternative routes from origin to destination.

        Args:
            origin: {"lat": float, "lon": float}
            destination: {"lat": float, "lon": float}
            avoid_disasters: Whether to avoid disaster zones (default: True)
            alternatives: Number of alternative routes to request (1-3, default: 3)

        Returns:
            List of route dictionaries, each containing:
            - route_id: Unique identifier
            - distance_mi: Total distance in miles
            - duration_seconds: Estimated duration in seconds
            - estimated_arrival: ISO timestamp of expected arrival
            - waypoints: List of navigation instructions
            - geometry: List of [lon, lat] coordinates
            - safety_score: 0-100 score (higher is safer)
            - is_fastest: Boolean indicating if this is the fastest route
            - is_safest: Boolean indicating if this is the safest route
            - intersects_disasters: Boolean indicating disaster zone intersection
            - disasters_nearby: Count of disasters within 6.2 miles
            - min_disaster_distance_mi: Closest disaster distance

        Example:
            >>> service = RouteCalculationService(api_key="your_key", db=db_ref)
            >>> routes = service.calculate_routes(
            ...     origin={"lat": 37.7749, "lon": -122.4194},
            ...     destination={"lat": 34.0522, "lon": -118.2437}
            ... )
            >>> print(f"Found {len(routes)} routes")
            >>> safest = next(r for r in routes if r['is_safest'])
            >>> print(f"Safest route: {safest['distance_mi']:.1f}mi, safety: {safest['safety_score']:.0f}/100")
        """
        logger.info(f"Calculating routes from ({origin['lat']}, {origin['lon']}) to ({destination['lat']}, {destination['lon']})")

        # Validate inputs
        if not self._validate_coordinates(origin) or not self._validate_coordinates(destination):
            logger.error("Invalid origin or destination coordinates")
            return []

        # Road snapping disabled - causes ORS rate limit exhaustion
        # Users must be on or near a drivable road for routing to work

        alternatives = max(1, min(3, alternatives))  # Clamp to 1-3

        # Step 1: Get disaster polygons if avoidance is enabled
        disaster_polygons = []
        active_disasters = []
        if avoid_disasters:
            try:
                disaster_polygons, active_disasters = self.get_disaster_polygons(origin, destination)
                logger.info(f"Generated {len(disaster_polygons)} disaster avoidance polygons from {len(active_disasters)} active disasters")
            except Exception as e:
                logger.error(f"Failed to generate disaster polygons: {e}", exc_info=True)
                # Continue without disaster avoidance

        # Step 2: Build ORS API request
        try:
            request_payload = self.build_ors_request(origin, destination, disaster_polygons, alternatives)
        except Exception as e:
            logger.error(f"Failed to build ORS request: {e}", exc_info=True)
            return []

        # Step 3: Call ORS API
        try:
            response = requests.post(
                self.ORS_BASE_URL,
                json=request_payload,
                headers={
                    'Authorization': self.api_key,
                    'Content-Type': 'application/json',
                    'Accept': 'application/geo+json'
                },
                timeout=self.ORS_TIMEOUT_SECONDS
            )
            # Check for ORS-specific errors before raising HTTP errors
            ors_data = response.json()

            # ORS returns error details even with 404 status
            if 'error' in ors_data:
                error_code = ors_data['error'].get('code')
                error_msg = ors_data['error'].get('message', 'Unknown error')

                if error_code in [2010, 2018]:
                    # Error 2010: No routable point found near coordinates
                    # Error 2018: Alternatives not supported with avoid_polygons
                    logger.warning(f"ORS error {error_code}: {error_msg}")
                    if error_code == 2010:
                        logger.warning("This usually means the location is not near a road (e.g., in a park, water, restricted area)")

                    # Try HERE API fallback if available
                    if self.here_service and self.here_service.is_enabled():
                        logger.info("Attempting HERE API fallback for better road data coverage")
                        try:
                            here_result = self.here_service.calculate_routes(
                                origin=origin,
                                destination=destination,
                                disaster_polygons=[p.__geo_interface__ for p in disaster_polygons] if disaster_polygons else [],
                                alternatives=alternatives
                            )

                            if here_result and here_result.get('routes'):
                                logger.info(f"HERE API fallback succeeded with {len(here_result['routes'])} routes")
                                # Use HERE routes instead of returning empty
                                routes = here_result['routes']

                                # Add warning to all routes if polygons were too many
                                route_warning = here_result.get('warning')

                                # Continue to Step 5 (safety scoring) with HERE routes
                                for route in routes:
                                    try:
                                        route_geometry = LineString([(coord[0], coord[1]) for coord in route['geometry']])
                                        safety_metrics = self.calculate_route_safety_score(route_geometry, active_disasters)

                                        route['safety_score'] = safety_metrics['score']
                                        route['min_disaster_distance_mi'] = safety_metrics['min_distance_mi']
                                        route['disasters_nearby'] = safety_metrics['nearby_count']
                                        route['intersects_disasters'] = self.check_route_disaster_intersection(
                                            route_geometry, disaster_polygons
                                        )

                                        # Add warning if polygons were too many
                                        if route_warning:
                                            route['warning'] = route_warning
                                    except Exception as e:
                                        logger.error(f"Failed to calculate safety score for HERE route {route.get('route_id')}: {e}", exc_info=True)
                                        route['safety_score'] = 0.0
                                        route['min_disaster_distance_mi'] = None  # None instead of float('inf') for JSON compatibility
                                        route['disasters_nearby'] = 0
                                        route['intersects_disasters'] = False

                                        # Add warning if polygons were too many
                                        if route_warning:
                                            route['warning'] = route_warning

                                # Identify fastest and safest routes
                                if routes:
                                    fastest_route = min(routes, key=lambda r: r['duration_seconds'])
                                    safest_route = max(routes, key=lambda r: r['safety_score'])

                                    for route in routes:
                                        route['is_fastest'] = (route['route_id'] == fastest_route['route_id'])
                                        route['is_safest'] = (route['route_id'] == safest_route['route_id'])

                                    logger.info(f"Successfully calculated {len(routes)} routes via HERE API")
                                    logger.info(f"Fastest: {fastest_route['distance_mi']:.1f}mi in {fastest_route['duration_seconds']/60:.0f}min")
                                    logger.info(f"Safest: {safest_route['distance_mi']:.1f}mi with safety score {safest_route['safety_score']:.0f}/100")

                                # Add Google Maps baseline route for comparison
                                if self.google_service and self.google_service.is_enabled():
                                    try:
                                        logger.info("Calculating Google Maps baseline route for comparison")
                                        baseline_result = self.google_service.calculate_baseline_route(
                                            origin=origin,
                                            destination=destination,
                                            mode="shortest"
                                        )
                                        baseline_route = baseline_result['route']

                                        # Mark this as the shortest (baseline) route
                                        baseline_route['is_shortest'] = True
                                        baseline_route['is_baseline'] = True

                                        # Calculate actual safety score for baseline route
                                        # This allows the shortest path to show as safe if no disasters are nearby
                                        try:
                                            baseline_geometry = LineString([(coord[0], coord[1]) for coord in baseline_route['geometry']])
                                            safety_metrics = self.calculate_route_safety_score(baseline_geometry, active_disasters)

                                            baseline_route['safety_score'] = safety_metrics['score']
                                            baseline_route['min_disaster_distance_mi'] = safety_metrics['min_distance_mi']
                                            baseline_route['disasters_nearby'] = safety_metrics['nearby_count']
                                            baseline_route['intersects_disasters'] = self.check_route_disaster_intersection(
                                                baseline_geometry, disaster_polygons
                                            )

                                            logger.info(f"Baseline route safety: {baseline_route['safety_score']:.1f}/100, {baseline_route['disasters_nearby']} disasters nearby")
                                        except Exception as e:
                                            logger.error(f"Failed to calculate safety score for baseline route: {e}", exc_info=True)
                                            # Keep the default 0.0 safety score from google_maps_routing_service

                                        # Add to routes list
                                        routes.append(baseline_route)

                                        logger.info(f"Added Google baseline route: {baseline_route['distance_mi']:.1f}mi in {baseline_route['duration_seconds']/60:.0f}min")
                                    except Exception as e:
                                        logger.warning(f"Failed to calculate Google Maps baseline route: {e}")

                                return routes
                            else:
                                logger.warning("HERE API fallback returned no routes")
                        except Exception as e:
                            logger.error(f"HERE API fallback failed: {e}", exc_info=True)

                    return []
                else:
                    logger.error(f"ORS API error {error_code}: {error_msg}")
                    return []

            response.raise_for_status()
            logger.info(f"ORS API response keys: {list(ors_data.keys())}")
            if 'features' in ors_data and ors_data['features']:
                logger.info(f"First feature keys: {list(ors_data['features'][0].keys())}")
        except requests.exceptions.Timeout:
            logger.error(f"ORS API request timed out after {self.ORS_TIMEOUT_SECONDS}s")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"ORS API request failed: {e}", exc_info=True)
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ORS API response: {e}", exc_info=True)
            return []

        # Step 4: Parse ORS response
        try:
            routes = self.parse_ors_response(ors_data)
        except Exception as e:
            logger.error(f"Failed to parse ORS response: {e}", exc_info=True)
            return []

        # Step 5: Calculate safety scores for each route
        for route in routes:
            try:
                route_geometry = LineString([(coord[0], coord[1]) for coord in route['geometry']])
                safety_metrics = self.calculate_route_safety_score(route_geometry, active_disasters)

                route['safety_score'] = safety_metrics['score']
                route['min_disaster_distance_mi'] = safety_metrics['min_distance_mi']
                route['disasters_nearby'] = safety_metrics['nearby_count']
                route['intersects_disasters'] = self.check_route_disaster_intersection(
                    route_geometry, disaster_polygons
                )
            except Exception as e:
                logger.error(f"Failed to calculate safety score for route {route.get('route_id')}: {e}", exc_info=True)
                route['safety_score'] = 0.0
                route['min_disaster_distance_mi'] = None  # None instead of float('inf') for JSON compatibility
                route['disasters_nearby'] = 0
                route['intersects_disasters'] = False

        # Step 6: Identify fastest and safest routes
        if routes:
            fastest_route = min(routes, key=lambda r: r['duration_seconds'])
            safest_route = max(routes, key=lambda r: r['safety_score'])

            for route in routes:
                route['is_fastest'] = (route['route_id'] == fastest_route['route_id'])
                route['is_safest'] = (route['route_id'] == safest_route['route_id'])

            logger.info(f"Successfully calculated {len(routes)} routes")
            logger.info(f"Fastest: {fastest_route['distance_mi']:.1f}mi in {fastest_route['duration_seconds']/60:.0f}min")
            logger.info(f"Safest: {safest_route['distance_mi']:.1f}mi with safety score {safest_route['safety_score']:.0f}/100")

        # Step 7: Add Google Maps baseline route (shortest path without avoidance)
        if self.google_service and self.google_service.is_enabled():
            try:
                logger.info("Calculating Google Maps baseline route for comparison")
                baseline_result = self.google_service.calculate_baseline_route(
                    origin=origin,
                    destination=destination,
                    mode="shortest"
                )
                baseline_route = baseline_result['route']

                # Mark this as the shortest (baseline) route
                baseline_route['is_shortest'] = True
                baseline_route['is_baseline'] = True

                # Calculate actual safety score for baseline route
                # This allows the shortest path to show as safe if no disasters are nearby
                try:
                    baseline_geometry = LineString([(coord[0], coord[1]) for coord in baseline_route['geometry']])
                    safety_metrics = self.calculate_route_safety_score(baseline_geometry, active_disasters)

                    baseline_route['safety_score'] = safety_metrics['score']
                    baseline_route['min_disaster_distance_mi'] = safety_metrics['min_distance_mi']
                    baseline_route['disasters_nearby'] = safety_metrics['nearby_count']
                    baseline_route['intersects_disasters'] = self.check_route_disaster_intersection(
                        baseline_geometry, disaster_polygons
                    )

                    logger.info(f"Baseline route safety: {baseline_route['safety_score']:.1f}/100, {baseline_route['disasters_nearby']} disasters nearby")
                except Exception as e:
                    logger.error(f"Failed to calculate safety score for baseline route: {e}", exc_info=True)
                    # Keep the default 0.0 safety score from google_maps_routing_service

                # Add to routes list
                routes.append(baseline_route)

                logger.info(f"Added Google baseline route: {baseline_route['distance_mi']:.1f}mi in {baseline_route['duration_seconds']/60:.0f}min")
            except Exception as e:
                logger.warning(f"Failed to calculate Google Maps baseline route: {e}")
                # Continue without baseline route

        return routes

    def get_disaster_polygons(
        self,
        origin: Dict[str, float],
        destination: Dict[str, float]
    ) -> Tuple[List[Polygon], List[Dict[str, Any]]]:
        """
        Generate buffer polygons around active disasters between origin and destination.

        Fetches disasters from Firebase and creates circular buffer zones based on
        severity levels. Filters out old disasters (>48h) and excluded types.

        Args:
            origin: {"lat": float, "lon": float}
            destination: {"lat": float, "lon": float}

        Returns:
            Tuple of (polygons, disasters):
            - polygons: List of Shapely Polygon objects representing disaster zones
            - disasters: List of disaster data dictionaries with metadata

        Notes:
            - Uses haversine distance for bounding box calculation
            - Filters disasters by type, severity, and recency
            - Creates circular approximations using 32-point polygons
        """
        if not self.db:
            logger.warning("No database connection - cannot fetch disasters")
            return [], []

        # Calculate bounding box with padding
        bbox = self._calculate_bounding_box(origin, destination, padding_km=50)
        logger.debug(f"Search bounding box: {bbox}")

        # Fetch disasters from Firebase
        active_disasters = []
        now = datetime.now(timezone.utc)
        max_age = timedelta(hours=self.MAX_DISASTER_AGE_HOURS)

        try:
            # Fetch user reports
            user_reports = self.db.reference('reports').get() or {}
            for report_id, report_data in user_reports.items():
                if self._is_disaster_relevant(report_data, bbox, now, max_age):
                    disaster = dict(report_data)
                    disaster['id'] = report_id
                    disaster['source'] = 'user_report'
                    active_disasters.append(disaster)

            logger.debug(f"Found {len(active_disasters)} relevant user reports")

            # Fetch NASA FIRMS wildfires
            wildfires_cache = self.db.reference('public_data_cache/wildfires/data').get() or []
            for wildfire in wildfires_cache:
                if self._is_disaster_relevant(wildfire, bbox, now, max_age):
                    disaster = dict(wildfire)
                    disaster['source'] = 'nasa_firms'
                    disaster['type'] = 'wildfire'
                    # Map brightness to severity
                    disaster['severity'] = self._map_wildfire_severity(wildfire.get('brightness', 0))
                    active_disasters.append(disaster)

            logger.debug(f"Found {len(wildfires_cache)} cached wildfires, {sum(1 for d in active_disasters if d['source'] == 'nasa_firms')} relevant")

            # Fetch NOAA weather alerts
            weather_alerts = self.db.reference('public_data_cache/weather_alerts/data').get() or []
            for alert in weather_alerts:
                if self._is_weather_alert_relevant(alert, bbox, now):
                    disaster = dict(alert)
                    disaster['source'] = 'noaa'
                    disaster['type'] = 'weather_alert'
                    # Map NOAA severity to our severity levels
                    disaster['severity'] = alert.get('severity', '').lower()
                    active_disasters.append(disaster)

            logger.debug(f"Found {len(weather_alerts)} cached weather alerts, {sum(1 for d in active_disasters if d['source'] == 'noaa')} relevant")

            # Fetch USGS earthquakes
            earthquakes = self.db.reference('public_data_cache/usgs_earthquakes/data').get() or []
            for earthquake in earthquakes:
                if self._is_disaster_relevant(earthquake, bbox, now, max_age):
                    disaster = dict(earthquake)
                    disaster['source'] = 'usgs'
                    disaster['type'] = 'earthquake'
                    disaster['severity'] = self._map_earthquake_severity(earthquake.get('magnitude', 0))
                    active_disasters.append(disaster)

            logger.debug(f"Found {sum(1 for d in active_disasters if d['source'] == 'usgs')} relevant earthquakes")

            # Fetch Cal Fire incidents
            cal_fire_incidents = self.db.reference('public_data_cache/cal_fire_incidents/data').get() or []
            for incident in cal_fire_incidents:
                if self._is_disaster_relevant(incident, bbox, now, max_age):
                    disaster = dict(incident)
                    disaster['source'] = 'cal_fire'
                    disaster['type'] = 'wildfire'
                    disaster['severity'] = self._map_cal_fire_severity(incident)
                    active_disasters.append(disaster)

            logger.debug(f"Found {sum(1 for d in active_disasters if d['source'] == 'cal_fire')} relevant Cal Fire incidents")

        except Exception as e:
            logger.error(f"Error fetching disasters from Firebase: {e}", exc_info=True)
            return [], []

        # Generate buffer polygons, excluding disasters that contain the origin point
        # (user is already inside disaster zone and needs to route OUT of it)
        origin_point = Point(origin['lon'], origin['lat'])
        polygons = []
        excluded_disasters = []

        for disaster in active_disasters:
            try:
                buffer_radius_mi = self._get_buffer_radius(disaster)
                polygon = self._create_circular_polygon(
                    disaster['latitude'],
                    disaster['longitude'],
                    buffer_radius_mi
                )

                # Check if origin point is inside this disaster zone
                if polygon.contains(origin_point):
                    excluded_disasters.append(disaster.get('id', 'unknown'))
                    logger.info(f"Excluding disaster {disaster.get('id', 'unknown')} - user is inside disaster zone")
                    continue

                polygons.append(polygon)
            except Exception as e:
                logger.error(f"Failed to create polygon for disaster {disaster.get('id', 'unknown')}: {e}")
                continue

        if excluded_disasters:
            logger.info(f"Excluded {len(excluded_disasters)} disasters containing origin point: {excluded_disasters}")
        logger.info(f"Generated {len(polygons)} disaster polygons from {len(active_disasters)} active disasters")
        return polygons, active_disasters

    def build_ors_request(
        self,
        origin: Dict[str, float],
        destination: Dict[str, float],
        avoid_polygons: List[Polygon],
        alternatives: int = 3
    ) -> Dict[str, Any]:
        """
        Build OpenRouteService API request payload.

        Args:
            origin: {"lat": float, "lon": float}
            destination: {"lat": float, "lon": float}
            avoid_polygons: List of Shapely Polygon objects to avoid
            alternatives: Number of alternative routes (1-3)

        Returns:
            Dictionary formatted for ORS API request

        Notes:
            - Coordinates are converted to [lon, lat] format for ORS
            - Polygons are converted to GeoJSON MultiPolygon format
            - Alternative routes configuration includes share_factor and weight_factor
        """
        # Convert coordinates to ORS format [lon, lat]
        coordinates = [
            [origin['lon'], origin['lat']],
            [destination['lon'], destination['lat']]
        ]

        payload = {
            "coordinates": coordinates,
            "instructions": True,
            "instructions_format": "text",  # Get human-readable instructions
            "language": "en",  # English instructions
            "geometry": True,  # Include route geometry
            "elevation": False,  # Don't need elevation data
            "extra_info": [],  # No extra info needed
            "preference": "recommended",  # Balance between fastest and shortest
            "units": "km"
        }

        # Add alternative routes configuration if requested
        # NOTE: ORS doesn't support alternatives with avoid_polygons (error 2018)
        # So only request alternatives if we have no polygons to avoid
        if alternatives > 1 and not avoid_polygons:
            payload["alternative_routes"] = {
                "share_factor": 0.6,  # Routes must differ by at least 40%
                "target_count": alternatives - 1,  # ORS counts alternatives separately
                "weight_factor": 1.4  # Route quality vs diversity balance
            }

        # Add avoid_polygons if provided
        if avoid_polygons:
            try:
                # Convert Shapely polygons to GeoJSON MultiPolygon
                geojson_polygons = []
                for polygon in avoid_polygons:
                    # Get exterior coordinates as list of [lon, lat]
                    coords = list(polygon.exterior.coords)
                    geojson_polygons.append([coords])

                payload["options"] = {
                    "avoid_polygons": {
                        "type": "MultiPolygon",
                        "coordinates": geojson_polygons
                    }
                }
                logger.debug(f"Added {len(avoid_polygons)} avoidance polygons to request")
            except Exception as e:
                logger.error(f"Failed to convert polygons to GeoJSON: {e}", exc_info=True)
                # Continue without avoidance polygons

        return payload

    def parse_ors_response(self, response_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse OpenRouteService API response into standardized route format.

        Handles GeoJSON FeatureCollection format from /geojson endpoint.

        Args:
            response_json: Raw JSON response from ORS API (GeoJSON FeatureCollection)

        Returns:
            List of route dictionaries with standardized fields

        Raises:
            KeyError: If response format is invalid
            ValueError: If response contains no routes
        """
        # GeoJSON format: {type: "FeatureCollection", features: [...]}
        if 'features' not in response_json or not response_json['features']:
            raise ValueError("ORS response contains no features")

        routes = []
        for idx, feature in enumerate(response_json['features']):
            try:
                # Extract properties (route metadata)
                properties = feature.get('properties', {})
                summary = properties.get('summary', {})

                # DEBUG: Log ORS distance value
                ors_distance_meters = summary.get('distance', 0)
                logger.info(f"ORS returned distance: {ors_distance_meters} meters = {ors_distance_meters/1000.0} km")

                # Extract geometry (LineString coordinates)
                geometry = feature['geometry']['coordinates']  # List of [lon, lat]

                # Calculate estimated arrival time
                duration_seconds = summary.get('duration', 0)
                arrival_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

                # Extract waypoints/instructions from segments
                waypoints = []
                segments = properties.get('segments', [])
                logger.info(f"🔍 ORS Response - Route {idx}: Found {len(segments)} segments")

                if not segments:
                    logger.warning(f"⚠️ No segments in route {idx} properties. Available keys: {list(properties.keys())}")

                for seg_idx, segment in enumerate(segments):
                    steps = segment.get('steps', [])
                    logger.info(f"🔍 Segment {seg_idx}: {len(steps)} steps")

                    if not steps:
                        logger.warning(f"⚠️ No steps in segment {seg_idx}. Available keys: {list(segment.keys())}")

                    for step_idx, step in enumerate(steps):
                        if step_idx == 0:
                            logger.info(f"🔍 First step in segment {seg_idx}: {step}")

                        # Convert type to string (ORS returns integer type codes)
                        step_type = step.get('type', 'unknown')
                        if isinstance(step_type, int):
                            step_type = str(step_type)
                        elif step_type is None:
                            step_type = 'unknown'

                        waypoint = {
                            'instruction': step.get('instruction', ''),
                            'distance_mi': step.get('distance', 0) / 1609.34,  # Convert meters to miles
                            'duration_seconds': step.get('duration', 0),
                            'type': step_type
                        }
                        waypoints.append(waypoint)

                logger.info(f"✅ Route {idx}: Extracted {len(waypoints)} waypoints")

                route = {
                    'route_id': f"route_{idx + 1}",
                    'distance_mi': summary.get('distance', 0) / 1609.34,  # Convert meters to miles
                    'duration_seconds': duration_seconds,
                    'estimated_arrival': arrival_time.isoformat(),
                    'waypoints': waypoints,
                    'geometry': geometry,  # List of [lon, lat] coordinates
                    # Safety metrics will be added by caller
                    'safety_score': 0.0,
                    'is_fastest': False,
                    'is_safest': False,
                    'intersects_disasters': False,
                    'disasters_nearby': 0,
                    'min_disaster_distance_mi': None  # None instead of float('inf') for JSON compatibility
                }

                routes.append(route)
            except (KeyError, TypeError) as e:
                logger.error(f"Failed to parse route {idx}: {e}", exc_info=True)
                continue

        if not routes:
            raise ValueError("Failed to parse any routes from ORS response")

        return routes

    def calculate_route_safety_score(
        self,
        route_geometry: LineString,
        disasters: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive safety score for a route (0-100 scale).

        Scoring factors:
        1. Minimum distance to any disaster (50% weight)
           - Uses exponential decay: score = 100 * (1 - exp(-distance/6.2mi))
        2. Number of disasters within 6.2 miles (30% weight)
           - Penalizes routes with many nearby disasters
        3. Route deviation from direct path (20% weight)
           - Rewards routes that don't deviate excessively

        Args:
            route_geometry: Shapely LineString representing route path
            disasters: List of disaster dictionaries with lat/lon

        Returns:
            Dictionary with:
            - score: Overall safety score (0-100)
            - min_distance_mi: Distance to closest disaster
            - nearby_count: Number of disasters within 6.2 miles
            - deviation_factor: Route length / direct distance ratio
        """
        if not disasters:
            return {
                'score': 100.0,
                'min_distance_mi': None,  # None instead of float('inf') for JSON compatibility
                'nearby_count': 0,
                'deviation_factor': 1.0
            }

        # Component 1: Minimum distance to any disaster (50% weight)
        min_distance_mi = None
        nearby_count = 0

        for disaster in disasters:
            try:
                disaster_point = Point(disaster['longitude'], disaster['latitude'])
                distance_meters = route_geometry.distance(disaster_point) * 111320  # Rough deg to meters
                distance_mi = distance_meters / 1609.34  # Convert meters to miles

                if min_distance_mi is None:
                    min_distance_mi = distance_mi
                else:
                    min_distance_mi = min(min_distance_mi, distance_mi)

                if distance_mi <= self.NEARBY_DISASTER_THRESHOLD_MI:
                    nearby_count += 1
            except Exception as e:
                logger.error(f"Error calculating distance to disaster: {e}")
                continue

        # Score for minimum distance (exponential decay)
        if min_distance_mi is None:
            distance_score = 100.0
        else:
            import math
            distance_score = 100.0 * (1.0 - math.exp(-min_distance_mi / 6.2))

        # Component 2: Number of nearby disasters (30% weight)
        # Penalty increases with number of nearby disasters
        if nearby_count == 0:
            nearby_score = 100.0
        else:
            nearby_score = max(0.0, 100.0 - (nearby_count * 15.0))  # -15 points per disaster

        # Component 3: Route deviation (20% weight)
        # Compare route length to direct haversine distance
        try:
            route_coords = list(route_geometry.coords)
            start = route_coords[0]
            end = route_coords[-1]

            direct_distance_mi = haversine_distance(
                start[1], start[0],  # lat, lon
                end[1], end[0]
            )

            route_distance_mi = route_geometry.length * 69.1  # Rough deg to miles
            deviation_factor = route_distance_mi / max(direct_distance_mi, 0.1)

            # Score: 100 for no deviation, penalty for excessive deviation
            if deviation_factor <= 1.1:
                deviation_score = 100.0
            elif deviation_factor <= 1.5:
                deviation_score = 100.0 - ((deviation_factor - 1.1) * 50.0)
            else:
                deviation_score = max(0.0, 100.0 - ((deviation_factor - 1.0) * 100.0))
        except Exception as e:
            logger.error(f"Error calculating route deviation: {e}")
            deviation_factor = 1.0
            deviation_score = 100.0

        # Weighted final score
        final_score = (
            distance_score * self.WEIGHT_MIN_DISTANCE +
            nearby_score * self.WEIGHT_NEARBY_DISASTERS +
            deviation_score * self.WEIGHT_ROUTE_DEVIATION
        )

        return {
            'score': round(final_score, 1),
            'min_distance_mi': round(min_distance_mi, 2) if min_distance_mi is not None else None,
            'nearby_count': nearby_count,
            'deviation_factor': round(deviation_factor, 2)
        }

    def check_route_disaster_intersection(
        self,
        route_geometry: LineString,
        disaster_polygons: List[Polygon]
    ) -> bool:
        """
        Check if route intersects any disaster buffer zones.

        Args:
            route_geometry: Shapely LineString representing route
            disaster_polygons: List of Shapely Polygon disaster zones

        Returns:
            True if route intersects any disaster zone, False otherwise
        """
        for polygon in disaster_polygons:
            try:
                if route_geometry.intersects(polygon):
                    return True
            except Exception as e:
                logger.error(f"Error checking polygon intersection: {e}")
                continue

        return False

    # ========== Private Helper Methods ==========

    def _validate_coordinates(self, coord: Dict[str, float]) -> bool:
        """
        Validate latitude and longitude ranges.

        Uses centralized CoordinateValidator for consistency.
        """
        return CoordinateValidator.validate_coordinate_dict(coord)

    def _calculate_bounding_box(
        self,
        origin: Dict[str, float],
        destination: Dict[str, float],
        padding_km: float = 50
    ) -> Dict[str, float]:
        """
        Calculate bounding box encompassing origin and destination with padding.

        Returns:
            {"min_lat": float, "max_lat": float, "min_lon": float, "max_lon": float}
        """
        lats = [origin['lat'], destination['lat']]
        lons = [origin['lon'], destination['lon']]

        # Calculate padding in degrees (rough approximation)
        lat_padding = padding_km / 111.32  # 1 degree lat ≈ 111.32 km
        lon_padding = padding_km / (111.32 * abs(max(lats)))  # Adjust for latitude

        return {
            'min_lat': min(lats) - lat_padding,
            'max_lat': max(lats) + lat_padding,
            'min_lon': min(lons) - lon_padding,
            'max_lon': max(lons) + lon_padding
        }

    def _is_disaster_relevant(
        self,
        disaster: Dict[str, Any],
        bbox: Dict[str, float],
        now: datetime,
        max_age: timedelta
    ) -> bool:
        """
        Check if disaster is relevant for route planning.

        Filters by:
        - Bounding box (spatial)
        - Disaster type (included types only)
        - Recency (< 48 hours)
        - Severity (excludes 'low' for some types)
        """
        try:
            # Check spatial bounds
            lat = disaster.get('latitude')
            lon = disaster.get('longitude')
            if not lat or not lon:
                return False

            if not (bbox['min_lat'] <= lat <= bbox['max_lat'] and
                    bbox['min_lon'] <= lon <= bbox['max_lon']):
                return False

            # Check disaster type
            disaster_type = disaster.get('type', '').lower()
            if disaster_type not in self.INCLUDED_DISASTER_TYPES:
                return False

            # Check recency
            timestamp_str = disaster.get('timestamp')
            if timestamp_str:
                try:
                    disaster_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    if now - disaster_time > max_age:
                        return False
                except (ValueError, AttributeError):
                    pass  # Continue if timestamp parsing fails

            # Check severity (exclude very low severity disasters)
            severity = disaster.get('severity', '').lower()
            if severity == 'low' and disaster_type in ['earthquake', 'flood']:
                return False  # Small earthquakes/floods don't affect routes

            return True
        except Exception as e:
            logger.error(f"Error checking disaster relevance: {e}")
            return False

    def _is_weather_alert_relevant(
        self,
        alert: Dict[str, Any],
        bbox: Dict[str, float],
        now: datetime
    ) -> bool:
        """Check if NOAA weather alert is relevant."""
        try:
            # Check spatial bounds
            lat = alert.get('latitude')
            lon = alert.get('longitude')
            if not lat or not lon:
                return False

            if not (bbox['min_lat'] <= lat <= bbox['max_lat'] and
                    bbox['min_lon'] <= lon <= bbox['max_lon']):
                return False

            # Check severity
            severity = alert.get('severity', '')
            if severity not in self.SEVERE_WEATHER_SEVERITIES:
                return False

            # Check expiration
            expires_str = alert.get('expires')
            if expires_str:
                try:
                    expires_time = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
                    if now >= expires_time:
                        return False  # Alert has expired
                except (ValueError, AttributeError):
                    pass

            return True
        except Exception as e:
            logger.error(f"Error checking weather alert relevance: {e}")
            return False

    def _get_buffer_radius(self, disaster: Dict[str, Any]) -> float:
        """Get buffer radius in miles based on disaster severity."""
        severity = disaster.get('severity', '').lower()
        return self.BUFFER_RADII_MI.get(severity, self.DEFAULT_BUFFER_MI)

    def _create_circular_polygon(self, lat: float, lon: float, radius_mi: float) -> Polygon:
        """
        Create circular polygon approximation using 32 points.

        Args:
            lat: Center latitude
            lon: Center longitude
            radius_mi: Radius in miles

        Returns:
            Shapely Polygon approximating a circle
        """
        import math

        # Convert radius to degrees (rough approximation)
        # 1 degree ≈ 69.1 miles at equator
        radius_deg_lat = radius_mi / 69.1
        radius_deg_lon = radius_mi / (69.1 * math.cos(math.radians(lat)))

        # Generate 32 points around circle
        points = []
        for i in range(32):
            angle = 2 * math.pi * i / 32
            point_lon = lon + radius_deg_lon * math.cos(angle)
            point_lat = lat + radius_deg_lat * math.sin(angle)
            points.append((point_lon, point_lat))

        return Polygon(points)

    def _map_wildfire_severity(self, brightness: float) -> str:
        """Map NASA FIRMS brightness to severity level."""
        if brightness >= 400:
            return 'critical'
        elif brightness >= 360:
            return 'high'
        elif brightness >= 330:
            return 'medium'
        else:
            return 'low'

    def _map_earthquake_severity(self, magnitude: float) -> str:
        """Map earthquake magnitude to severity level."""
        if magnitude >= 7.0:
            return 'critical'
        elif magnitude >= 6.0:
            return 'high'
        elif magnitude >= 5.0:
            return 'medium'
        else:
            return 'low'

    def _map_cal_fire_severity(self, incident: Dict[str, Any]) -> str:
        """Map Cal Fire incident to severity level based on acres burned."""
        acres = incident.get('acres_burned', 0)
        try:
            acres = float(acres)
            if acres >= 5000:
                return 'critical'
            elif acres >= 1000:
                return 'high'
            elif acres >= 100:
                return 'medium'
            else:
                return 'low'
        except (ValueError, TypeError):
            return 'medium'

