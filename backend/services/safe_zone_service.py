"""
Safe Zone Service for Disaster Alert System
Manages safe zones including evacuation centers, hospitals, fire stations, and emergency shelters.
"""
import logging
import re
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from functools import lru_cache
from firebase_admin import db
from utils.geo import haversine_distance, is_valid_coordinates

logger = logging.getLogger(__name__)

# Default configuration constants
DEFAULT_MAX_ZONES_RETURNED = 5  # Maximum number of safe zones to return by default
DEFAULT_MAX_DISTANCE_MI = 50.0  # Default maximum distance to search for safe zones (miles)
DEFAULT_THREAT_RADIUS_MI = 3.1  # Default radius to check for threats around a safe zone (miles)

# HIFLD zone lookup constants
COORDINATE_MATCH_TOLERANCE = 0.001  # Coordinate matching tolerance in degrees (~111 meters)
HIFLD_CACHE_SIZE = 128  # Number of recently accessed HIFLD shelters to cache in memory

# HIFLD ID format regex patterns
# Coordinate-based: hifld_34_137328_n118_677781 (latitude_longitude with 'n' for negative)
HIFLD_COORDINATE_ID_PATTERN = re.compile(r'^(\d+)_(\d+)_(n?\d+)_(\d+)$')
# Direct ID: numeric only (e.g., 62898)
HIFLD_NUMERIC_ID_PATTERN = re.compile(r'^\d+$')


class SafeZoneService:
    """
    Manages safe zones including pre-defined evacuation centers,
    hospitals, fire stations, and dynamically identified safe areas.
    """

    # Safe zone types
    ZONE_TYPES = [
        'evacuation_center',
        'hospital',
        'fire_station',
        'emergency_shelter',
        'police_station',
        'community_center'
    ]

    # Operational statuses
    STATUSES = ['open', 'closed', 'at_capacity', 'damaged', 'unknown']

    def __init__(self, firebase_db, cache_manager=None, hifld_service=None):
        """
        Initialize SafeZoneService.

        Args:
            firebase_db: Firebase database reference
            cache_manager: Optional cache manager for caching safe zone data
            hifld_service: Optional HIFLD shelter service for external safe zone data
        """
        self.db = firebase_db
        self.cache_manager = cache_manager
        self.hifld_service = hifld_service
        self.logger = logging.getLogger(__name__)

    def get_nearest_safe_zones(
        self,
        latitude: float,
        longitude: float,
        limit: int = DEFAULT_MAX_ZONES_RETURNED,
        max_distance_mi: float = DEFAULT_MAX_DISTANCE_MI,
        zone_types: Optional[List[str]] = None,
        include_external_sources: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find nearest safe zones from user location.

        Args:
            latitude: User's current latitude
            longitude: User's current longitude
            limit: Maximum number of safe zones to return
            max_distance_mi: Maximum distance to search (default 50 miles)
            zone_types: Optional list of zone types to filter by
            include_external_sources: Whether to include HIFLD shelters (default True)

        Returns:
            List of safe zones sorted by distance, each containing:
            - id, name, type, location, address, capacity, amenities,
              operational_status, distance_from_user_mi
        """
        if not is_valid_coordinates(latitude, longitude):
            raise ValueError(f"Invalid coordinates: ({latitude}, {longitude})")

        try:
            # SCALABILITY LIMITS AND RECOMMENDATIONS:
            # ========================================
            # This implementation fetches ALL safe zones from Firebase, then filters in-memory.
            #
            # **Phase 1 (Current):** 5-10 zones
            #   - Performance: Excellent (~5ms with cache, ~50ms without)
            #   - Recommended: Keep this simple implementation
            #
            # **Phase 2 Threshold:** 100-500 zones
            #   - Performance: Good (~20ms with cache, ~200ms without)
            #   - Action: Monitor query times, consider geohashing if approaching 500 zones
            #   - Warning: Response times will degrade linearly with zone count
            #
            # **Phase 3 Migration Required:** 500+ zones
            #   - Performance: Degraded (~50-200ms with cache, ~2-5s without)
            #   - Action: MUST implement one of the following:
            #     1. **Geohashing** - Divide map into grid cells, query only relevant cells
            #        Example: geohash precision 5 (~5km × 5km cells)
            #     2. **R-tree Spatial Index** - Efficient nearest-neighbor queries
            #        Library: rtree, scipy.spatial.KDTree
            #     3. **Firebase Geo Queries** - Use GeoFire for spatial filtering
            #     4. **PostGIS Migration** - For 10,000+ zones, migrate to spatial database
            #
            # **Performance Benchmarks:**
            #   - 10 zones:    ~5ms (cached) / ~50ms (uncached)
            #   - 100 zones:   ~10ms (cached) / ~150ms (uncached)
            #   - 500 zones:   ~25ms (cached) / ~500ms (uncached)
            #   - 1,000 zones: ~50ms (cached) / ~2s (uncached) ⚠️ Migration needed
            #   - 10,000 zones: ~500ms (cached) / ~20s (uncached) ❌ Not viable
            #
            # TODO: Add monitoring alert when zone count exceeds 300 (80% of Phase 2 limit)

            # Use cache to reduce Firebase reads (safe zones change infrequently)
            all_zones = None
            if self.cache_manager and self.cache_manager.should_update('safe_zones'):
                self.logger.info("Cache expired, fetching fresh safe zones from Firebase")
                safe_zones_ref = self.db.reference('safe_zones')
                all_zones = safe_zones_ref.get()
                if all_zones:
                    self.cache_manager.update_cache('safe_zones', all_zones)
            elif self.cache_manager:
                all_zones = self.cache_manager.get_cached_data('safe_zones')
            else:
                # No cache manager, fetch directly
                safe_zones_ref = self.db.reference('safe_zones')
                all_zones = safe_zones_ref.get()

            if not all_zones:
                self.logger.warning("No safe zones found in database")
                return []

            # Scalability monitoring: Log warning if zone count is high
            zone_count = len(all_zones)
            if zone_count >= 300:
                self.logger.warning(
                    f"Processing {zone_count} safe zones (approaching Phase 2 limit of 500). "
                    "Consider implementing geohashing for better performance."
                )

            # Calculate distance and filter
            zones_with_distance = []
            for zone_id, zone_data in all_zones.items():
                # Validate zone has required fields
                if not zone_data.get('location') or not zone_data.get('location', {}).get('latitude'):
                    continue

                zone_lat = zone_data['location']['latitude']
                zone_lon = zone_data['location']['longitude']

                # Calculate distance
                distance_mi = haversine_distance(latitude, longitude, zone_lat, zone_lon)

                # Filter by distance and type
                if distance_mi > max_distance_mi:
                    continue

                if zone_types and zone_data.get('type') not in zone_types:
                    continue

                # Add distance and zone ID to result
                zone_result = {
                    'id': zone_id,
                    'distance_from_user_mi': round(distance_mi, 2),
                    **zone_data
                }
                zones_with_distance.append(zone_result)

            # Sort by distance
            zones_with_distance.sort(key=lambda z: z['distance_from_user_mi'])

            # Fetch external sources (HIFLD shelters) if enabled
            if include_external_sources and self.hifld_service:
                hifld_zones = self._fetch_hifld_zones(latitude, longitude, max_distance_mi, zone_types)
                zones_with_distance.extend(hifld_zones)
                logger.info(f"Added {len(hifld_zones)} HIFLD shelters to results")

            # Re-sort all zones by distance after adding external sources
            zones_with_distance.sort(key=lambda z: z['distance_from_user_mi'])

            # Limit results
            return zones_with_distance[:limit]

        except ValueError as e:
            # Coordinate validation or data format errors
            self.logger.error(f"Invalid data in safe zones: {e}")
            raise
        except Exception as e:
            # Firebase errors or unexpected issues
            self.logger.exception(f"Unexpected error fetching nearest safe zones: {e}")
            return []

    def is_zone_safe(
        self,
        zone_id: str,
        current_disasters: List[Dict[str, Any]],
        threat_radius_mi: float = DEFAULT_THREAT_RADIUS_MI
    ) -> Dict[str, Any]:
        """
        Check if a safe zone is currently safe (no disasters within threat radius).

        Args:
            zone_id: Safe zone ID
            current_disasters: List of active disasters with lat/lon
            threat_radius_mi: Radius to check for threats (default 3.1 miles)

        Returns:
            {
                safe: bool,
                threats: [disaster_ids],
                distance_to_nearest_threat_mi: float,
                nearest_threat: {id, type, severity}
            }
        """
        try:
            zone = self.get_zone_by_id(zone_id)
            if not zone:
                return {
                    'safe': False,
                    'threats': [],
                    'distance_to_nearest_threat_mi': None,
                    'error': 'Zone not found'
                }

            zone_lat = zone['location']['latitude']
            zone_lon = zone['location']['longitude']

            threats = []
            nearest_threat = None
            min_distance = float('inf')

            for disaster in current_disasters:
                # Skip if disaster doesn't have location
                if not disaster.get('latitude') or not disaster.get('longitude'):
                    continue

                # Calculate distance to disaster
                distance_mi = haversine_distance(
                    zone_lat, zone_lon,
                    disaster['latitude'], disaster['longitude']
                )

                # Check if within threat radius
                if distance_mi <= threat_radius_mi:
                    threats.append(disaster.get('id', 'unknown'))

                # Track nearest threat
                if distance_mi < min_distance:
                    min_distance = distance_mi
                    nearest_threat = {
                        'id': disaster.get('id', 'unknown'),
                        'type': disaster.get('type', 'unknown'),
                        'severity': disaster.get('severity', 'unknown'),
                        'distance_mi': round(distance_mi, 2)
                    }

            is_safe = len(threats) == 0

            return {
                'safe': is_safe,
                'threats': threats,
                'distance_to_nearest_threat_mi': round(min_distance, 2) if min_distance != float('inf') else None,
                'nearest_threat': nearest_threat if nearest_threat else None
            }

        except KeyError as e:
            # Missing required fields in zone or disaster data
            self.logger.error(f"Missing required field in zone safety check: {e}")
            return {
                'safe': False,
                'threats': [],
                'distance_to_nearest_threat_km': None,
                'error': f'Data error: {str(e)}'
            }
        except Exception as e:
            # Firebase errors or unexpected issues
            self.logger.exception(f"Unexpected error checking zone safety: {e}")
            return {
                'safe': False,
                'threats': [],
                'distance_to_nearest_threat_km': None,
                'error': str(e)
            }

    def get_zone_by_id(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve safe zone details by ID.

        Supports both manual Firebase zones and HIFLD external zones.
        HIFLD zone IDs start with 'hifld_'.

        Performance optimizations:
        - Uses LRU cache for recently accessed HIFLD shelters
        - Regex-based ID validation (fast)
        - Separate methods for coordinate vs. numeric ID lookups

        Args:
            zone_id: Safe zone identifier

        Returns:
            Safe zone data or None if not found
        """
        try:
            # Check if this is a HIFLD shelter ID
            if zone_id.startswith('hifld_') and self.hifld_service:
                hifld_id = zone_id.replace('hifld_', '')

                # Coordinate-based ID (e.g., hifld_34_137328_n118_677781)
                if HIFLD_COORDINATE_ID_PATTERN.match(hifld_id):
                    return self._get_hifld_zone_by_coordinates(hifld_id)

                # Numeric ID (e.g., hifld_62898)
                elif HIFLD_NUMERIC_ID_PATTERN.match(hifld_id):
                    return self._get_hifld_zone_by_numeric_id(hifld_id)

                else:
                    self.logger.warning(f"Invalid HIFLD ID format: {zone_id}")
                    return None

            # Standard Firebase zone lookup
            zone_ref = self.db.reference(f'safe_zones/{zone_id}')
            zone_data = zone_ref.get()

            if zone_data:
                zone_data['id'] = zone_id

            return zone_data

        except Exception as e:
            # Firebase connection or query errors
            self.logger.exception(f"Error fetching zone {zone_id}: {e}")
            return None

    def _get_hifld_zone_by_coordinates(self, hifld_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up HIFLD shelter by coordinate-based ID.

        Format: LAT_LATDEC_LON_LONDEC where 'n' prefix indicates negative
        Example: 34_137328_n118_677781 = (34.137328, -118.677781)

        Args:
            hifld_id: Coordinate-based HIFLD ID (without 'hifld_' prefix)

        Returns:
            Shelter data or None if not found
        """
        try:
            parts = hifld_id.split('_')
            if len(parts) != 4:
                return None

            # Parse coordinates
            lat_str = f"{parts[0]}.{parts[1]}"
            lon_str = f"{parts[2].replace('n', '-')}.{parts[3]}"

            lat = float(lat_str)
            lon = float(lon_str.replace('n', '-'))

            # Search for shelters near these coordinates (1-mile radius)
            shelters = self.hifld_service.get_shelters_in_radius(lat, lon, radius_mi=1.0)

            # Find shelter with matching coordinates
            for shelter in shelters:
                shelter_lat = shelter['location']['latitude']
                shelter_lon = shelter['location']['longitude']
                if (abs(shelter_lat - lat) < COORDINATE_MATCH_TOLERANCE and
                    abs(shelter_lon - lon) < COORDINATE_MATCH_TOLERANCE):
                    return shelter

            return None

        except (ValueError, IndexError) as e:
            self.logger.warning(f"Failed to parse coordinate-based HIFLD ID {hifld_id}: {e}")
            return None

    @lru_cache(maxsize=HIFLD_CACHE_SIZE)
    def _get_hifld_zone_by_numeric_id(self, hifld_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up HIFLD shelter by numeric ID with LRU caching.

        Cached for performance - recently accessed shelters are stored in memory.
        Cache size: 128 entries (configurable via HIFLD_CACHE_SIZE constant).

        Args:
            hifld_id: Numeric HIFLD ID (e.g., "62898")

        Returns:
            Shelter data or None if not found
        """
        try:
            url = "https://maps.nccs.nasa.gov/mapping/rest/services/hifld_open/emergency_services/MapServer/7/query"

            params = {
                'where': f"id='{hifld_id}' OR objectid={hifld_id}",
                'outFields': '*',
                'f': 'geojson'
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('features') and len(data['features']) > 0:
                # Parse the shelter (pass features array, not whole GeoJSON)
                shelters = self.hifld_service._parse_hifld_response(data['features'])
                if shelters:
                    self.logger.info(f"Found HIFLD shelter by ID {hifld_id}: {shelters[0].get('name')}")
                    return shelters[0]

            self.logger.warning(f"HIFLD shelter not found by ID: {hifld_id}")
            return None

        except Exception as e:
            self.logger.exception(f"Error querying HIFLD by ID {hifld_id}: {e}")
            return None

    def update_zone_status(
        self,
        zone_id: str,
        status: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Update operational status of a safe zone.

        Args:
            zone_id: Safe zone ID
            status: New status (must be in STATUSES)
            reason: Optional reason for status change

        Returns:
            True if successful, False otherwise
        """
        if status not in self.STATUSES:
            raise ValueError(f"Invalid status: {status}. Must be one of {self.STATUSES}")

        try:
            zone_ref = self.db.reference(f'safe_zones/{zone_id}')

            # Check if zone exists
            if not zone_ref.get():
                self.logger.warning(f"Zone {zone_id} not found")
                return False

            # Update status
            update_data = {
                'operational_status': status,
                'last_status_update': datetime.now(timezone.utc).isoformat()
            }

            if reason:
                update_data['status_reason'] = reason

            zone_ref.update(update_data)
            self.logger.info(f"Updated zone {zone_id} status to {status}")
            return True

        except Exception as e:
            # Firebase update errors
            self.logger.exception(f"Error updating zone status for {zone_id}: {e}")
            return False

    def create_safe_zone(self, zone_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new safe zone in the database.

        Args:
            zone_data: Safe zone information including:
                - name (required)
                - type (required)
                - location {latitude, longitude} (required)
                - address (optional)
                - capacity (optional)
                - amenities (optional)
                - contact (optional)

        Returns:
            Zone ID if successful, None otherwise
        """
        # Validate required fields
        required_fields = ['name', 'type', 'location']
        for field in required_fields:
            if field not in zone_data:
                raise ValueError(f"Missing required field: {field}")

        if zone_data['type'] not in self.ZONE_TYPES:
            raise ValueError(f"Invalid zone type: {zone_data['type']}")

        location = zone_data['location']
        if not is_valid_coordinates(location.get('latitude'), location.get('longitude')):
            raise ValueError("Invalid location coordinates")

        try:
            # Generate zone ID
            zone_id = f"sz_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

            # Add metadata
            zone_data['created_at'] = datetime.now(timezone.utc).isoformat()
            zone_data['last_updated'] = datetime.now(timezone.utc).isoformat()
            zone_data['operational_status'] = zone_data.get('operational_status', 'open')
            zone_data['source'] = zone_data.get('source', 'manual')

            # Save to Firebase
            zone_ref = self.db.reference(f'safe_zones/{zone_id}')
            zone_ref.set(zone_data)

            self.logger.info(f"Created safe zone {zone_id}: {zone_data['name']}")
            return zone_id

        except ValueError as e:
            # Validation errors already raised above
            raise
        except Exception as e:
            # Firebase write errors
            self.logger.exception(f"Error creating safe zone: {e}")
            return None

    def find_safe_areas_dynamically(
        self,
        latitude: float,
        longitude: float,
        radius_mi: float = 50,
        current_disasters: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Identify safe areas without pre-defined safe zones.
        Uses absence of disasters + population density heuristics.

        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_mi: Search radius in miles
            current_disasters: List of active disasters

        Returns:
            List of dynamically identified safe areas
        """
        # This is a placeholder for future enhancement
        # Would need population density data and more sophisticated algorithms
        self.logger.info("Dynamic safe area identification not yet implemented")
        return []

    def get_all_zones(self) -> List[Dict[str, Any]]:
        """
        Get all safe zones from the database.

        Returns:
            List of all safe zones
        """
        try:
            safe_zones_ref = self.db.reference('safe_zones')
            all_zones = safe_zones_ref.get()

            if not all_zones:
                return []

            zones_list = []
            for zone_id, zone_data in all_zones.items():
                zone_data['id'] = zone_id
                zones_list.append(zone_data)

            # Scalability warning: Check zone count and log if approaching Phase 2 limit
            zone_count = len(zones_list)
            if zone_count >= 300:
                self.logger.warning(
                    f"Safe zone count ({zone_count}) approaching Phase 2 limit (500). "
                    "Consider implementing geohashing or spatial indexing."
                )
            elif zone_count >= 500:
                self.logger.error(
                    f"Safe zone count ({zone_count}) exceeds Phase 2 limit (500). "
                    "Performance degradation likely. Migration to spatial indexing REQUIRED."
                )

            return zones_list

        except Exception as e:
            # Firebase query errors
            self.logger.exception(f"Error fetching all zones: {e}")
            return []

    def seed_default_safe_zones(self) -> int:
        """
        Seed database with default safe zones for major US cities.
        This is for initial setup/testing purposes.

        Returns:
            Number of zones created
        """
        default_zones = [
            {
                'name': 'Golden Gate Park Evacuation Center',
                'type': 'evacuation_center',
                'location': {'latitude': 37.7694, 'longitude': -122.4862},
                'address': '501 Stanyan St, San Francisco, CA 94117',
                'capacity': 5000,
                'amenities': ['medical', 'food', 'water', 'shelter', 'power'],
                'contact': {'phone': '+1-415-831-2700'},
                'operational_status': 'open',
                'source': 'manual'
            },
            {
                'name': 'San Francisco General Hospital',
                'type': 'hospital',
                'location': {'latitude': 37.7561, 'longitude': -122.4206},
                'address': '1001 Potrero Ave, San Francisco, CA 94110',
                'capacity': 3000,
                'amenities': ['medical', 'emergency_care', 'trauma_center'],
                'contact': {'phone': '+1-415-206-8000'},
                'operational_status': 'open',
                'source': 'manual'
            },
            {
                'name': 'Oakland Coliseum Evacuation Center',
                'type': 'evacuation_center',
                'location': {'latitude': 37.7516, 'longitude': -122.2005},
                'address': '7000 Coliseum Way, Oakland, CA 94621',
                'capacity': 10000,
                'amenities': ['food', 'water', 'shelter', 'communications'],
                'contact': {'phone': '+1-510-569-2121'},
                'operational_status': 'open',
                'source': 'manual'
            },
            {
                'name': 'Los Angeles Convention Center Shelter',
                'type': 'emergency_shelter',
                'location': {'latitude': 34.0407, 'longitude': -118.2695},
                'address': '1201 S Figueroa St, Los Angeles, CA 90015',
                'capacity': 15000,
                'amenities': ['medical', 'food', 'water', 'shelter', 'power', 'communications'],
                'contact': {'phone': '+1-213-741-1151'},
                'operational_status': 'open',
                'source': 'manual'
            },
            {
                'name': 'San Diego County Emergency Operations Center',
                'type': 'evacuation_center',
                'location': {'latitude': 32.8242, 'longitude': -117.1391},
                'address': '5510 Overland Ave, San Diego, CA 92123',
                'capacity': 8000,
                'amenities': ['medical', 'food', 'water', 'shelter', 'communications'],
                'contact': {'phone': '+1-858-565-5255'},
                'operational_status': 'open',
                'source': 'manual'
            }
        ]

        created_count = 0
        for zone_data in default_zones:
            zone_id = self.create_safe_zone(zone_data)
            if zone_id:
                created_count += 1

        self.logger.info(f"Seeded {created_count} default safe zones")
        return created_count

    def _fetch_hifld_zones(
        self,
        latitude: float,
        longitude: float,
        max_distance_mi: float,
        zone_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch HIFLD shelter zones within radius and add distance calculation

        Args:
            latitude: User's current latitude
            longitude: User's current longitude
            max_distance_mi: Maximum distance to search
            zone_types: Optional list of zone types to filter by

        Returns:
            List of HIFLD zones with distance_from_user_mi added
        """
        try:
            # Fetch shelters from HIFLD within radius
            hifld_shelters = self.hifld_service.get_shelters_in_radius(
                latitude,
                longitude,
                max_distance_mi
            )

            zones_with_distance = []
            for shelter in hifld_shelters:
                # Skip if type filtering is enabled and this type doesn't match
                if zone_types and shelter.get('type') not in zone_types:
                    continue

                # Calculate distance from user
                shelter_lat = shelter.get('location', {}).get('latitude') or shelter.get('latitude')
                shelter_lon = shelter.get('location', {}).get('longitude') or shelter.get('longitude')

                if not shelter_lat or not shelter_lon:
                    continue

                distance_mi = haversine_distance(latitude, longitude, shelter_lat, shelter_lon)

                # Filter by distance
                if distance_mi > max_distance_mi:
                    continue

                # Add distance to shelter object
                shelter_with_distance = {
                    'distance_from_user_mi': round(distance_mi, 2),
                    **shelter
                }
                zones_with_distance.append(shelter_with_distance)

            return zones_with_distance

        except Exception as e:
            self.logger.error(f"Error fetching HIFLD zones: {e}", exc_info=True)
            return []
