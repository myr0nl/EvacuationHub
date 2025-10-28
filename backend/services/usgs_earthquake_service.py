"""
USGS Earthquake Data Integration
Fetches earthquake data from USGS Earthquake Hazards Program
Documentation: https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
"""
import requests
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class USGSEarthquakeService:
    """Service to fetch earthquake data from USGS Earthquake API"""

    # USGS GeoJSON Feed URLs (magnitude 2.5+ from past week)
    BASE_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary"

    def __init__(self, confidence_scorer=None):
        """
        Initialize USGS Earthquake Service

        Args:
            confidence_scorer: Optional ConfidenceScorer instance for scoring earthquakes
        """
        # Import confidence scorer to add scoring to earthquakes
        self.confidence_scorer = confidence_scorer
        if not self.confidence_scorer:
            # Lazy import to avoid circular dependency
            from services.confidence_scorer import ConfidenceScorer
            self.confidence_scorer = ConfidenceScorer()

    def get_us_earthquakes(self, days=7):
        """
        Fetch earthquake data for the United States from USGS

        Args:
            days (int): Number of days of data to retrieve (1-30 supported)
                       Default: 7 days (matches 2.5_week feed)

        Returns:
            list: List of earthquake data points
        """
        try:
            # USGS provides pre-aggregated feeds for different time periods
            # We'll use the appropriate feed based on requested days
            if days <= 1:
                feed_url = f"{self.BASE_URL}/2.5_day.geojson"
            elif days <= 7:
                feed_url = f"{self.BASE_URL}/2.5_week.geojson"
            else:
                feed_url = f"{self.BASE_URL}/2.5_month.geojson"

            logger.info(f"USGS Earthquakes: Fetching from {feed_url}")

            response = requests.get(feed_url, timeout=30)
            logger.info(f"USGS Earthquakes: Status code: {response.status_code}")

            response.raise_for_status()

            # Parse GeoJSON response
            geojson_data = response.json()

            # Extract features (individual earthquakes)
            features = geojson_data.get('features', [])
            logger.info(f"USGS Earthquakes: Received {len(features)} earthquakes")

            # Parse and filter earthquakes
            earthquakes = self._parse_usgs_geojson(features, days)

            logger.info(f"USGS Earthquakes: Successfully parsed {len(earthquakes)} US earthquakes")
            return earthquakes

        except requests.exceptions.RequestException as e:
            logger.error(f"USGS Earthquakes ERROR: Request exception: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"USGS Earthquakes ERROR: Processing exception: {e}", exc_info=True)
            return []

    def _parse_usgs_geojson(self, features, days_filter=7):
        """
        Parse USGS GeoJSON features into standardized earthquake data

        Args:
            features (list): List of GeoJSON feature objects
            days_filter (int): Only include earthquakes from the last N days

        Returns:
            list: Parsed earthquake data
        """
        earthquakes = []
        cutoff_timestamp = datetime.now(timezone.utc).timestamp() * 1000 - (days_filter * 24 * 60 * 60 * 1000)

        for feature in features:
            try:
                # Extract properties and geometry
                properties = feature.get('properties', {})
                geometry = feature.get('geometry', {})
                coordinates = geometry.get('coordinates', [])

                # Validate required fields
                if len(coordinates) < 3:
                    continue

                longitude = float(coordinates[0])
                latitude = float(coordinates[1])
                depth_km = float(coordinates[2])

                # Filter to US territory only
                if not self._is_in_us(latitude, longitude):
                    continue

                # Filter by time (only last N days)
                time_ms = properties.get('time')
                if not time_ms or time_ms < cutoff_timestamp:
                    continue

                # Extract earthquake properties
                magnitude = float(properties.get('mag', 0))
                place = properties.get('place', 'Unknown location')
                event_id = properties.get('id', '')

                # Skip if magnitude is below 2.5 (shouldn't happen with 2.5+ feed, but safety check)
                if magnitude < 2.5:
                    continue

                # Parse timestamp
                timestamp = self._parse_timestamp(time_ms)

                # Determine severity based on magnitude
                severity = self._determine_severity(magnitude)

                # Create standardized earthquake object
                earthquake = {
                    'id': f"usgs_{event_id}",
                    'source': 'usgs',
                    'type': 'earthquake',
                    'latitude': latitude,
                    'longitude': longitude,
                    'magnitude': magnitude,
                    'depth_km': depth_km,
                    'place': place,
                    'timestamp': timestamp,
                    'severity': severity,
                    'event_type': properties.get('type', 'earthquake'),
                    'status': properties.get('status', 'automatic'),
                    'tsunami': properties.get('tsunami', 0),
                    'felt_reports': properties.get('felt'),
                    'significance': properties.get('sig'),
                    'url': properties.get('url', '')
                }

                # Add confidence scoring for this earthquake
                # USGS data is seismometer-verified, so high confidence (0.98)
                if self.confidence_scorer:
                    confidence_result = self.confidence_scorer.calculate_confidence(earthquake)
                    earthquake['confidence_score'] = confidence_result['confidence_score']
                    earthquake['confidence_level'] = confidence_result['confidence_level']
                    earthquake['confidence_breakdown'] = confidence_result['breakdown']

                earthquakes.append(earthquake)

            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"USGS Earthquakes: Error parsing feature: {e}")
                continue

        return earthquakes

    def _is_in_us(self, latitude, longitude):
        """
        Check if coordinates are within US territory (50 states only)

        Args:
            latitude (float): Latitude in decimal degrees
            longitude (float): Longitude in decimal degrees

        Returns:
            bool: True if coordinates are in US 50 states
        """
        # Alaska: -180 to -130°W, 51 to 72°N
        if -180 <= longitude <= -130 and 51 <= latitude <= 72:
            return True

        # Hawaii: -160 to -154°W, 18 to 23°N
        if -160 <= longitude <= -154 and 18 <= latitude <= 23:
            return True

        # Continental US: -125 to -66°W, 24 to 49°N
        # Exclude Canada by checking longitude-dependent latitude boundaries
        if -125 <= longitude <= -66 and 24 <= latitude <= 49:
            # US-Canada border is complex, but approximate checks:
            # Eastern region (Great Lakes): longitude > -83 and latitude > 42.5 is likely Canada
            # This excludes Toronto (43.6532°N, -79.3832°W) but keeps Detroit/Buffalo
            if longitude > -83 and latitude > 42.5:
                return False

            return True

        return False

    def _determine_severity(self, magnitude):
        """
        Determine earthquake severity from magnitude

        Richter scale interpretation:
        - 2.5-3.9: Minor (often felt, rarely causes damage)
        - 4.0-4.9: Light (noticeable shaking, minimal damage)
        - 5.0-5.9: Moderate (can cause damage to poorly constructed buildings)
        - 6.0-6.9: Strong (can be destructive in populated areas)
        - 7.0+: Major/Great (serious damage over large areas)

        Args:
            magnitude (float): Richter magnitude

        Returns:
            str: Severity level ('low', 'medium', 'high', 'critical')
        """
        if magnitude >= 7.0:
            return 'critical'  # Major/Great earthquake
        elif magnitude >= 6.0:
            return 'high'  # Strong earthquake
        elif magnitude >= 5.0:
            return 'medium'  # Moderate earthquake
        else:
            return 'low'  # Minor/Light earthquake

    def _parse_timestamp(self, time_ms):
        """
        Parse USGS timestamp (milliseconds since epoch) to ISO format

        Args:
            time_ms (int): Milliseconds since Unix epoch

        Returns:
            str: ISO 8601 timestamp with timezone
        """
        try:
            # Convert milliseconds to seconds
            dt = datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc)
            return dt.isoformat()
        except Exception:
            return datetime.now(timezone.utc).isoformat()
