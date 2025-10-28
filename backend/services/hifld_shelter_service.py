"""
HIFLD National Shelter System Integration
Fetches emergency evacuation centers and shelters from HIFLD Open Data
Documentation: https://hifld-geoplatform.opendata.arcgis.com/datasets/national-shelter-system-facilities

API Reference: https://maps.nccs.nasa.gov/mapping/rest/services/hifld_open/emergency_services/MapServer/7
Field Schema (lowercase):
  - id: Shelter ID (string)
  - name: Facility name
  - address, city, state, zip: Location details
  - evac_cap, post_cap: Capacity (evacuation and post-disaster)
  - status: Operational status (OPEN, CLOSED, etc.)
  - type: Shelter type (BOTH, EVACUATION, POST, etc.)
  - ada, wheel, electric, pet_code: Amenity flags
  - telephone, website: Contact information
"""
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Input validation constants
MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0
MIN_RADIUS_MI = 0.1  # Minimum search radius in miles
MAX_RADIUS_MI = 500.0  # Maximum search radius in miles


class HIFLDShelterService:
    """Service to fetch National Shelter System facilities from HIFLD Open Data (ArcGIS MapServer)"""

    # HIFLD Emergency Services MapServer - National Shelter System Facilities (Layer 7)
    BASE_URL = "https://maps.nccs.nasa.gov/mapping/rest/services/hifld_open/emergency_services/MapServer/7/query"

    # Maximum records to fetch per query (API limit is 100,000)
    MAX_RECORDS = 10000

    # Timeout for API requests
    TIMEOUT_SECONDS = 30

    def __init__(self, confidence_scorer=None):
        """
        Initialize HIFLD Shelter Service

        Args:
            confidence_scorer: Optional confidence scorer for adding scores to shelters
        """
        self.confidence_scorer = confidence_scorer
        if not self.confidence_scorer:
            # Lazy import to avoid circular dependency
            from services.confidence_scorer import ConfidenceScorer
            self.confidence_scorer = ConfidenceScorer()

    def get_shelters_in_bbox(
        self,
        min_lat: float,
        max_lat: float,
        min_lon: float,
        max_lon: float
    ) -> List[Dict[str, Any]]:
        """
        Fetch shelters within a bounding box

        Args:
            min_lat: Minimum latitude (-90 to 90)
            max_lat: Maximum latitude (-90 to 90)
            min_lon: Minimum longitude (-180 to 180)
            max_lon: Maximum longitude (-180 to 180)

        Returns:
            List of shelter data points

        Raises:
            ValueError: If coordinates are invalid or out of range
        """
        # Validate latitude ranges
        if not (MIN_LATITUDE <= min_lat <= MAX_LATITUDE):
            raise ValueError(f"min_lat must be between {MIN_LATITUDE} and {MAX_LATITUDE}, got {min_lat}")
        if not (MIN_LATITUDE <= max_lat <= MAX_LATITUDE):
            raise ValueError(f"max_lat must be between {MIN_LATITUDE} and {MAX_LATITUDE}, got {max_lat}")

        # Validate longitude ranges
        if not (MIN_LONGITUDE <= min_lon <= MAX_LONGITUDE):
            raise ValueError(f"min_lon must be between {MIN_LONGITUDE} and {MAX_LONGITUDE}, got {min_lon}")
        if not (MIN_LONGITUDE <= max_lon <= MAX_LONGITUDE):
            raise ValueError(f"max_lon must be between {MIN_LONGITUDE} and {MAX_LONGITUDE}, got {max_lon}")

        # Validate bbox logic
        if min_lat >= max_lat:
            raise ValueError(f"min_lat ({min_lat}) must be less than max_lat ({max_lat})")
        if min_lon >= max_lon:
            raise ValueError(f"min_lon ({min_lon}) must be less than max_lon ({max_lon})")

        logger.info(f"HIFLD: Fetching shelters in bounding box ({min_lat},{min_lon}) to ({max_lat},{max_lon})")
        try:
            # Build geometry envelope for bounding box
            # Format: xmin,ymin,xmax,ymax (lon,lat,lon,lat)
            envelope = f"{min_lon},{min_lat},{max_lon},{max_lat}"

            params = {
                'geometry': envelope,
                'geometryType': 'esriGeometryEnvelope',
                'spatialRel': 'esriSpatialRelIntersects',
                'outFields': '*',  # Get all fields
                'returnGeometry': 'true',
                'f': 'geojson',  # Request GeoJSON format for easy parsing
                'resultRecordCount': self.MAX_RECORDS
            }

            logger.info(f"HIFLD: Fetching shelters in bbox ({min_lat},{min_lon}) to ({max_lat},{max_lon})")

            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=self.TIMEOUT_SECONDS
            )
            response.raise_for_status()

            data = response.json()
            features = data.get('features', [])

            logger.info(f"HIFLD: Received {len(features)} shelter features")

            # Parse and transform data
            shelters = self._parse_hifld_response(features)

            logger.info(f"HIFLD: Successfully parsed {len(shelters)} shelters")
            return shelters

        except requests.exceptions.RequestException as e:
            logger.error(f"HIFLD ERROR: Request exception: {e}")
            return []
        except Exception as e:
            logger.error(f"HIFLD ERROR: Processing exception: {e}", exc_info=True)
            return []

    def get_shelters_in_radius(
        self,
        lat: float,
        lon: float,
        radius_mi: float
    ) -> List[Dict[str, Any]]:
        """
        Fetch shelters within a radius of a point

        Args:
            lat: Center latitude (-90 to 90)
            lon: Center longitude (-180 to 180)
            radius_mi: Search radius in miles (0.1 to 500)

        Returns:
            List of shelter data points

        Raises:
            ValueError: If coordinates or radius are invalid
        """
        # Validate latitude
        if not (MIN_LATITUDE <= lat <= MAX_LATITUDE):
            raise ValueError(f"Latitude must be between {MIN_LATITUDE} and {MAX_LATITUDE}, got {lat}")

        # Validate longitude
        if not (MIN_LONGITUDE <= lon <= MAX_LONGITUDE):
            raise ValueError(f"Longitude must be between {MIN_LONGITUDE} and {MAX_LONGITUDE}, got {lon}")

        # Validate radius
        if not (MIN_RADIUS_MI <= radius_mi <= MAX_RADIUS_MI):
            raise ValueError(f"Radius must be between {MIN_RADIUS_MI} and {MAX_RADIUS_MI} miles, got {radius_mi}")

        logger.info(f"HIFLD: Fetching shelters within {radius_mi} miles of ({lat},{lon})")

        try:
            # Convert radius from miles to meters (1 mile = 1609.34 meters)
            radius_m = radius_mi * 1609.34

            params = {
                'geometry': f'{lon},{lat}',  # Center point (lon, lat)
                'geometryType': 'esriGeometryPoint',
                'distance': radius_m,
                'units': 'esriSRUnit_Meter',
                'spatialRel': 'esriSpatialRelIntersects',
                'outFields': '*',  # Get all fields
                'returnGeometry': 'true',
                'f': 'geojson',
                'resultRecordCount': self.MAX_RECORDS
            }

            logger.info(f"HIFLD: Fetching shelters within {radius_mi} miles of ({lat},{lon})")

            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=self.TIMEOUT_SECONDS
            )
            response.raise_for_status()

            data = response.json()
            features = data.get('features', [])

            logger.info(f"HIFLD: Received {len(features)} shelter features")

            # Parse and transform data
            shelters = self._parse_hifld_response(features)

            logger.info(f"HIFLD: Successfully parsed {len(shelters)} shelters")
            return shelters

        except requests.exceptions.RequestException as e:
            logger.error(f"HIFLD ERROR: Request exception: {e}")
            return []
        except Exception as e:
            logger.error(f"HIFLD ERROR: Processing exception: {e}", exc_info=True)
            return []

    def _parse_hifld_response(self, features):
        """
        Parse HIFLD GeoJSON features and transform to standard format

        Args:
            features (list): GeoJSON features from HIFLD API

        Returns:
            list: Transformed shelter data
        """
        shelters = []

        for feature in features:
            try:
                # Extract properties and geometry
                props = feature.get('properties', {})
                geom = feature.get('geometry', {})

                # Extract coordinates (GeoJSON format is [lon, lat])
                coordinates = geom.get('coordinates', [])
                if not coordinates or len(coordinates) < 2:
                    logger.warning(f"HIFLD: Skipping shelter with invalid coordinates: {props.get('SHELTER_ID')}")
                    continue

                longitude = coordinates[0]
                latitude = coordinates[1]

                # Validate coordinates
                if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                    logger.warning(f"HIFLD: Skipping shelter with out-of-range coordinates: ({latitude},{longitude})")
                    continue

                # Extract shelter information
                # HIFLD uses lowercase field names: id, name, address, city, state, zip, etc.
                shelter_id = props.get('id') or props.get('objectid') or props.get('fema_id')

                # If no ID available, generate one from coordinates (unique identifier)
                if not shelter_id:
                    # Create a unique ID from lat/lon coordinates (rounded to 6 decimals for uniqueness)
                    shelter_id = f"{round(latitude, 6)}_{round(longitude, 6)}".replace('.', '_').replace('-', 'n')

                shelter_name = props.get('name') or 'Unknown Shelter'
                shelter_type = props.get('type') or 'evacuation_center'
                address = props.get('address') or ''
                city = props.get('city') or ''
                state = props.get('state') or ''
                zipcode = props.get('zip') or ''

                # Build full address
                full_address = self._build_address(address, city, state, zipcode)

                # Extract capacity
                # HIFLD uses: evac_cap (evacuation capacity) and post_cap (post-disaster capacity)
                capacity = props.get('evac_cap') or props.get('post_cap') or props.get('population') or 0
                try:
                    capacity = int(capacity) if capacity else 0
                except (ValueError, TypeError):
                    capacity = 0

                # Extract operational status
                status = props.get('status') or 'unknown'
                operational_status = self._map_status(status)

                # Extract amenities if available (pass shelter_type for context-aware defaults)
                amenities = self._parse_amenities(props, shelter_type)

                # Extract contact information
                contact = self._parse_contact(props)

                # Create shelter object matching SafeZoneService schema
                shelter = {
                    'id': f"hifld_{shelter_id}",
                    'name': shelter_name,
                    'type': self._map_shelter_type(shelter_type),
                    'location': {
                        'latitude': latitude,
                        'longitude': longitude
                    },
                    'address': full_address,
                    'city': city,
                    'state': state,
                    'zipcode': zipcode,
                    'capacity': capacity,
                    'amenities': amenities,
                    'contact': contact,
                    'operational_status': operational_status,
                    'source': 'hifld_nss',  # National Shelter System
                    'last_updated': datetime.now(timezone.utc).isoformat(),
                    # COMPATIBILITY NOTE: Coordinates stored in both formats for backward compatibility
                    # - location.latitude/longitude: Standard nested format (RECOMMENDED)
                    # - Top-level latitude/longitude: Legacy format for route_calculation_service.py
                    #   and other services that expect flat structure. Required by RouteCalculationService
                    #   (see backend/services/route_calculation_service.py:255, 262)
                    # TODO: Deprecate top-level format in v2.0 after migrating all consumers
                    'latitude': latitude,
                    'longitude': longitude,
                    # Additional HIFLD-specific metadata
                    'hifld_metadata': {
                        'shelter_id': shelter_id,
                        'original_type': shelter_type,
                        'original_status': status
                    }
                }

                # Add confidence scoring for this shelter
                if self.confidence_scorer:
                    confidence_result = self.confidence_scorer.calculate_confidence(shelter)
                    shelter['confidence_score'] = confidence_result['confidence_score']
                    shelter['confidence_level'] = confidence_result['confidence_level']
                    shelter['confidence_breakdown'] = confidence_result['breakdown']
                else:
                    # Default high confidence for official HIFLD source
                    shelter['confidence_score'] = 0.95
                    shelter['confidence_level'] = 'High'

                shelters.append(shelter)

            except Exception as e:
                logger.warning(f"HIFLD: Error parsing shelter feature: {e}")
                continue

        return shelters

    def _build_address(self, address, city, state, zipcode):
        """Build full address string from components"""
        parts = []
        if address:
            parts.append(address)
        if city:
            parts.append(city)
        if state:
            parts.append(state)
        if zipcode:
            parts.append(zipcode)
        return ', '.join(parts) if parts else ''

    def _map_shelter_type(self, hifld_type):
        """
        Map HIFLD shelter type to SafeZoneService type schema

        Args:
            hifld_type (str): HIFLD shelter type

        Returns:
            str: Mapped shelter type
        """
        if not hifld_type:
            return 'evacuation_center'

        hifld_type_lower = str(hifld_type).lower()

        # Type mapping - order matters! Check more specific types first
        if 'hospital' in hifld_type_lower or 'medical' in hifld_type_lower:
            return 'hospital'
        elif 'fire' in hifld_type_lower:
            return 'fire_station'
        elif 'police' in hifld_type_lower or 'law enforcement' in hifld_type_lower:
            return 'police_station'
        elif 'evacuation' in hifld_type_lower:
            return 'evacuation_center'
        elif 'shelter' in hifld_type_lower or 'emergency' in hifld_type_lower:
            return 'emergency_shelter'
        elif 'community' in hifld_type_lower:
            return 'community_center'
        elif 'center' in hifld_type_lower:
            # Generic "center" defaults to evacuation center
            return 'evacuation_center'
        else:
            # Default to evacuation_center for unknown types
            return 'evacuation_center'

    def _map_status(self, hifld_status):
        """
        Map HIFLD operational status to SafeZoneService status schema

        Args:
            hifld_status (str): HIFLD operational status

        Returns:
            str: Mapped status ('open', 'closed', 'at_capacity', 'damaged', 'unknown')
        """
        if not hifld_status:
            return 'unknown'

        status_lower = str(hifld_status).lower()

        # Status mapping
        status_map = {
            'open': 'open',
            'active': 'open',
            'available': 'open',
            'operational': 'open',
            'closed': 'closed',
            'inactive': 'closed',
            'unavailable': 'closed',
            'at capacity': 'at_capacity',
            'full': 'at_capacity',
            'damaged': 'damaged',
            'destroyed': 'damaged',
            'compromised': 'damaged'
        }

        # Try exact match
        if status_lower in status_map:
            return status_map[status_lower]

        # Try partial match
        for key, value in status_map.items():
            if key in status_lower:
                return value

        # Default to unknown
        return 'unknown'

    def _parse_amenities(self, props: Dict[str, Any], shelter_type: str) -> List[str]:
        """
        Parse amenities from HIFLD properties with context-aware defaults

        Args:
            props: HIFLD feature properties
            shelter_type: HIFLD shelter type (used to determine appropriate defaults)

        Returns:
            List of amenity strings
        """
        amenities = []

        # HIFLD-specific amenity flags (lowercase field names)
        # ADA accessibility
        if props.get('ada') == 'YES' or props.get('wheel') == 'YES':
            amenities.append('wheelchair_accessible')

        # Power/Electric
        if props.get('electric') == 'YES':
            amenities.append('power')

        # Pet-friendly (based on pet_code/pet_desc)
        if props.get('pet_code') and props.get('pet_code') != 'NOT AVAILABLE':
            amenities.append('pets_allowed')

        # Add default amenities based on facility type
        # Only evacuation centers and emergency shelters are expected to have basic supplies
        # Hospitals, police stations, fire stations may not have food/water/shelter supplies
        shelter_type_lower = shelter_type.lower() if shelter_type else ''

        if any(keyword in shelter_type_lower for keyword in ['evacuation', 'shelter', 'both']):
            # Evacuation centers and emergency shelters typically provide:
            amenities.extend(['shelter', 'water', 'food'])

        # Remove duplicates and return
        return list(set(amenities))

    def _parse_contact(self, props):
        """
        Parse contact information from HIFLD properties

        Args:
            props (dict): HIFLD feature properties

        Returns:
            dict: Contact information
        """
        contact = {}

        # Phone number - HIFLD uses lowercase 'telephone'
        phone = props.get('telephone')
        if phone and phone != 'NOT AVAILABLE':
            contact['phone'] = str(phone)

        # Website - HIFLD uses lowercase 'website'
        website = props.get('website')
        if website and website != 'NOT AVAILABLE':
            contact['website'] = str(website)

        return contact if contact else None
