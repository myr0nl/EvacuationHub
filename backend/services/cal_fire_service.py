"""
Cal Fire ArcGIS Integration
Fetches active wildfire incidents from Cal Fire's ArcGIS REST API
Documentation: https://gis.data.ca.gov/datasets/CALFIRE-Forestry::california-fire-perimeters
"""
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class CalFireService:
    """Service to fetch wildfire incident data from Cal Fire ArcGIS"""

    # Cal Fire ArcGIS REST API endpoint
    BASE_URL = "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/California_Fire_Perimeters/FeatureServer/0/query"

    def __init__(self, confidence_scorer=None):
        """
        Initialize Cal Fire service

        Args:
            confidence_scorer: Optional ConfidenceScorer instance for scoring incidents
        """
        self.confidence_scorer = confidence_scorer
        if not self.confidence_scorer:
            # Lazy import to avoid circular dependency
            from services.confidence_scorer import ConfidenceScorer
            self.confidence_scorer = ConfidenceScorer()

    def fetch_active_incidents(self) -> List[Dict]:
        """
        Fetch active wildfire incidents from Cal Fire ArcGIS API

        Filters for fires from the last 30 days to focus on recent/active incidents.

        Returns:
            list: List of active wildfire incidents in standardized format
        """
        try:
            # Calculate date 30 days ago in milliseconds (ArcGIS epoch format)
            from datetime import datetime, timedelta
            days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            epoch_ms = int(days_ago.timestamp() * 1000)

            # Query parameters for ArcGIS REST API
            # Filter by ALARM_DATE (fire start date) within last 30 days
            # Note: ArcGIS expects epoch milliseconds without 'timestamp' keyword
            params = {
                'where': f'ALARM_DATE >= {epoch_ms}',  # Recent fires only (epoch ms)
                'outFields': '*',  # Get all fields
                'f': 'geojson',  # Return GeoJSON format
                'returnGeometry': 'true'
            }

            logger.info("Cal Fire: Fetching active incidents from ArcGIS API")
            logger.info(f"Cal Fire: URL: {self.BASE_URL}")
            logger.info(f"Cal Fire: Filtering for fires started after: {days_ago.strftime('%Y-%m-%d')}")

            response = requests.get(self.BASE_URL, params=params, timeout=30)
            logger.info(f"Cal Fire: Status code: {response.status_code}")

            response.raise_for_status()

            # Parse GeoJSON response
            geojson_data = response.json()

            if 'features' not in geojson_data:
                logger.warning("Cal Fire: No features found in response")
                return []

            logger.info(f"Cal Fire: Received {len(geojson_data['features'])} features")

            # Parse and transform incidents
            incidents = self._parse_arcgis_response(geojson_data)

            logger.info(f"Cal Fire: Successfully parsed {len(incidents)} active wildfire incidents")
            return incidents

        except requests.exceptions.RequestException as e:
            logger.error(f"Cal Fire ERROR: Request exception: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Cal Fire ERROR: Processing exception: {e}", exc_info=True)
            return []

    def get_cached_incidents(self, cache_manager) -> List[Dict]:
        """
        Get Cal Fire incidents from cache or fetch fresh data

        Uses 30-minute cache TTL to avoid API spam while keeping data fresh

        Args:
            cache_manager: CacheManager instance for Firebase caching

        Returns:
            list: List of Cal Fire incidents
        """
        try:
            # Check if cache needs updating
            if cache_manager.should_update('cal_fire'):
                logger.info("Cal Fire: Cache expired, fetching fresh data")
                fresh_data = self.fetch_active_incidents()
                cache_manager.update_cache('cal_fire', fresh_data)
                return fresh_data
            else:
                logger.info("Cal Fire: Using cached data")
                return cache_manager.get_cached_data('cal_fire')

        except Exception as e:
            logger.error(f"Cal Fire ERROR: Cache operation failed: {e}")
            # Fall back to cached data on error
            return cache_manager.get_cached_data('cal_fire')

    def _parse_arcgis_response(self, geojson_data: Dict) -> List[Dict]:
        """
        Parse ArcGIS GeoJSON response into standardized incident format

        Args:
            geojson_data: GeoJSON response from ArcGIS API

        Returns:
            list: List of standardized incident dictionaries
        """
        incidents = []

        for feature in geojson_data.get('features', []):
            try:
                properties = feature.get('properties', {})
                geometry = feature.get('geometry', {})

                # Extract centroid coordinates from geometry
                latitude, longitude = self._extract_centroid(geometry)

                if latitude is None or longitude is None:
                    logger.warning("Cal Fire: Skipping feature with missing coordinates")
                    continue

                # Extract incident details from properties
                incident_name = properties.get('FIRE_NAME', properties.get('INCIDENT_NAME', 'Unknown'))
                county = properties.get('COUNTY', properties.get('LOCATION', 'Unknown'))
                acres_burned = self._safe_float(properties.get('GIS_ACRES', properties.get('ACRES', 0)))
                percent_contained = self._safe_float(properties.get('PERCENT_CONTAINED', properties.get('CONTAINMENT', 0)))

                # Parse start date
                started = self._parse_date_field(
                    properties.get('ALARM_DATE', properties.get('START_DATE', properties.get('DISCOVERY_DOC', '')))
                )

                # Create unique ID from incident details
                incident_id = self._generate_incident_id(incident_name, county, latitude, longitude)

                # Determine severity based on acres burned and containment
                severity = self._determine_severity(acres_burned, percent_contained)

                # Use actual fire start date as timestamp (not current time)
                # This ensures proper aging and cleanup of old fires
                timestamp = started if started else datetime.now(timezone.utc).isoformat()

                # Build standardized incident object
                incident = {
                    'id': incident_id,
                    'source': 'cal_fire',
                    'type': 'wildfire',
                    'name': incident_name,
                    'county': county,
                    'latitude': latitude,
                    'longitude': longitude,
                    'acres_burned': acres_burned,
                    'percent_contained': percent_contained,
                    'started': started,
                    'timestamp': timestamp,  # Use actual fire date, not current time
                    'severity': severity,
                    'confidence_score': 0.95,  # Cal Fire official data is highly reliable
                    'confidence_level': 'High'
                }

                # Add confidence scoring breakdown using scorer
                if self.confidence_scorer:
                    confidence_result = self.confidence_scorer.calculate_confidence(incident)
                    incident['confidence_score'] = confidence_result['confidence_score']
                    incident['confidence_level'] = confidence_result['confidence_level']
                    incident['confidence_breakdown'] = confidence_result['breakdown']

                incidents.append(incident)

            except Exception as e:
                logger.warning(f"Cal Fire: Error parsing feature: {e}")
                continue

        return incidents

    def _extract_centroid(self, geometry: Dict) -> tuple:
        """
        Extract centroid coordinates from GeoJSON geometry

        Handles Point, Polygon, and MultiPolygon geometries

        Args:
            geometry: GeoJSON geometry object

        Returns:
            tuple: (latitude, longitude) or (None, None) if extraction fails
        """
        try:
            geom_type = geometry.get('type', '')

            if geom_type == 'Point':
                # Point geometry: coordinates are [lon, lat]
                coords = geometry.get('coordinates', [])
                if len(coords) >= 2:
                    return coords[1], coords[0]  # Return (lat, lon)

            elif geom_type == 'Polygon':
                # Polygon geometry: calculate centroid from outer ring
                coords = geometry.get('coordinates', [[]])
                if coords and len(coords[0]) > 0:
                    return self._calculate_polygon_centroid(coords[0])

            elif geom_type == 'MultiPolygon':
                # MultiPolygon: use first polygon's centroid
                coords = geometry.get('coordinates', [[[]]])
                if coords and len(coords[0]) > 0 and len(coords[0][0]) > 0:
                    return self._calculate_polygon_centroid(coords[0][0])

        except Exception as e:
            logger.warning(f"Cal Fire: Error extracting centroid: {e}")

        return None, None

    def _calculate_polygon_centroid(self, coordinates: List[List[float]]) -> tuple:
        """
        Calculate centroid of a polygon from its coordinates

        Args:
            coordinates: List of [lon, lat] coordinate pairs

        Returns:
            tuple: (latitude, longitude)
        """
        if not coordinates:
            return None, None

        # Simple centroid calculation (average of all points)
        lons = [coord[0] for coord in coordinates]
        lats = [coord[1] for coord in coordinates]

        avg_lon = sum(lons) / len(lons)
        avg_lat = sum(lats) / len(lats)

        return avg_lat, avg_lon

    def _safe_float(self, value, default=0.0) -> float:
        """
        Safely convert value to float

        Args:
            value: Value to convert
            default: Default value if conversion fails

        Returns:
            float: Converted value or default
        """
        try:
            return float(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    def _parse_date_field(self, date_value) -> str:
        """
        Parse various date formats from ArcGIS API

        Args:
            date_value: Date value (string, timestamp, or None)

        Returns:
            str: ISO 8601 formatted date string
        """
        if not date_value:
            return datetime.now(timezone.utc).isoformat()

        try:
            # Handle Unix timestamp (milliseconds)
            if isinstance(date_value, (int, float)):
                dt = datetime.fromtimestamp(date_value / 1000, tz=timezone.utc)
                return dt.isoformat()

            # Handle string dates
            if isinstance(date_value, str):
                # Try common date formats
                for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%Y-%m-%dT%H:%M:%S']:
                    try:
                        dt = datetime.strptime(date_value, fmt)
                        dt = dt.replace(tzinfo=timezone.utc)
                        return dt.isoformat()
                    except ValueError:
                        continue

        except Exception as e:
            logger.warning(f"Cal Fire: Error parsing date '{date_value}': {e}")

        # Return current time if parsing fails
        return datetime.now(timezone.utc).isoformat()

    def _generate_incident_id(self, name: str, county: str, lat: float, lon: float) -> str:
        """
        Generate unique incident ID from incident details

        Args:
            name: Incident name
            county: County name
            lat: Latitude
            lon: Longitude

        Returns:
            str: Unique incident identifier
        """
        # Clean name and county for ID
        clean_name = name.replace(' ', '_').replace('/', '_')
        clean_county = county.replace(' ', '_').replace('/', '_')

        return f"calfire_{clean_name}_{clean_county}_{lat:.4f}_{lon:.4f}"

    def _determine_severity(self, acres_burned: float, percent_contained: float) -> str:
        """
        Determine wildfire severity from acres burned and containment

        Args:
            acres_burned: Number of acres burned
            percent_contained: Percentage of fire contained (0-100)

        Returns:
            str: Severity level ('low', 'medium', 'high', 'critical')
        """
        # Uncontained large fires are most critical
        if acres_burned > 10000 and percent_contained < 50:
            return 'critical'
        elif acres_burned > 5000 and percent_contained < 70:
            return 'critical'
        elif acres_burned > 1000 and percent_contained < 80:
            return 'high'
        elif acres_burned > 500 or percent_contained < 90:
            return 'medium'
        else:
            return 'low'
