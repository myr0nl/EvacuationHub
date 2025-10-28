"""
NOAA Weather Alerts Integration
Fetches active weather alerts from NOAA's National Weather Service API
Documentation: https://www.weather.gov/documentation/services-web-api
"""
import requests
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class NOAAWeatherService:
    """Service to fetch weather alerts from NOAA National Weather Service"""

    BASE_URL = "https://api.weather.gov/alerts/active"

    def __init__(self, confidence_scorer=None):
        self.headers = {
            'User-Agent': 'DisasterAlertSystem/1.0 (contact@example.com)',
            'Accept': 'application/geo+json'
        }

        # Import confidence scorer to add scoring to alerts
        self.confidence_scorer = confidence_scorer
        if not self.confidence_scorer:
            # Lazy import to avoid circular dependency
            from services.confidence_scorer import ConfidenceScorer
            self.confidence_scorer = ConfidenceScorer()

    def get_us_weather_alerts(self, severity_threshold='Minor'):
        """
        Fetch active weather alerts for the United States

        Args:
            severity_threshold (str): Minimum severity level (Extreme, Severe, Moderate, Minor, Unknown)

        Returns:
            list: List of weather alert data points
        """
        try:
            # Fetch active alerts - API returns all US alerts by default
            # Don't use 'area' parameter as it causes 400 Bad Request
            response = requests.get(
                self.BASE_URL,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            features = data.get('features', [])

            alerts = []
            severity_order = {'Extreme': 4, 'Severe': 3, 'Moderate': 2, 'Minor': 1, 'Unknown': 0}
            min_severity = severity_order.get(severity_threshold, 0)

            for feature in features:
                properties = feature.get('properties', {})
                geometry = feature.get('geometry')

                # Filter by severity
                severity = properties.get('severity', 'Unknown')
                if severity_order.get(severity, 0) < min_severity:
                    continue

                # Extract coordinates (use first point or centroid)
                # Many NOAA alerts have null geometry - use fallback coordinate
                coordinates = self._extract_coordinates(geometry)

                # If no geometry, use fallback coordinate (center of continental US)
                # This allows county/zone-based alerts to still appear on the map
                if not coordinates:
                    # Use center of continental US as fallback
                    # This ensures the alert is visible even without precise coordinates
                    coordinates = (-98.5795, 39.8283)  # Geographic center of USA (Kansas)
                    # Note: area_desc field will contain specific county/zone names

                # Filter to US only (continental US + Alaska + Hawaii)
                # Only apply location filter if alert has actual geometry
                # Skip filter for fallback coordinates since they're already US-centered
                if geometry and not self._is_us_location(coordinates[0], coordinates[1]):
                    continue

                # Parse timestamp with timezone awareness
                sent_time = properties.get('sent')
                if sent_time:
                    try:
                        # NOAA timestamps are already in ISO format
                        timestamp = datetime.fromisoformat(sent_time.replace('Z', '+00:00')).isoformat()
                    except (ValueError, AttributeError):
                        timestamp = datetime.now(timezone.utc).isoformat()
                else:
                    timestamp = datetime.now(timezone.utc).isoformat()

                alert = {
                    'id': properties.get('id', f"noaa_{datetime.now(timezone.utc).timestamp()}"),
                    'source': 'noaa',
                    'type': 'weather_alert',
                    'event': properties.get('event', 'Weather Alert'),
                    'headline': properties.get('headline', ''),
                    'description': properties.get('description', ''),
                    'instruction': properties.get('instruction', ''),
                    'severity': severity.lower() if severity != 'Unknown' else 'medium',  # Normalize to lowercase
                    'urgency': properties.get('urgency', 'Unknown'),
                    'certainty': properties.get('certainty', 'Unknown'),
                    'latitude': coordinates[1],
                    'longitude': coordinates[0],
                    'area_desc': properties.get('areaDesc', ''),
                    'onset': properties.get('onset'),
                    'expires': properties.get('expires'),
                    'timestamp': timestamp
                }

                # Add confidence scoring for this alert
                if self.confidence_scorer:
                    try:
                        confidence_result = self.confidence_scorer.calculate_confidence(alert)
                        alert['confidence_score'] = confidence_result.get('confidence_score')
                        alert['confidence_level'] = confidence_result.get('confidence_level')
                        alert['confidence_breakdown'] = confidence_result.get('breakdown')

                        # Default to high confidence for official sources if calculation failed
                        if alert['confidence_score'] is None:
                            alert['confidence_score'] = 0.95
                            alert['confidence_level'] = 'High'
                            alert['confidence_breakdown'] = {
                                'source': 'noaa',
                                'default_fallback': True,
                                'note': 'Official government source - defaulted to high confidence'
                            }
                    except Exception as e:
                        # If confidence calculation fails, default to high confidence for official source
                        logger.warning(f"Confidence calculation failed for NOAA alert {alert.get('id')}: {e}")
                        alert['confidence_score'] = 0.95
                        alert['confidence_level'] = 'High'
                        alert['confidence_breakdown'] = {
                            'source': 'noaa',
                            'error_fallback': True,
                            'note': 'Official government source - defaulted to high confidence after error'
                        }

                alerts.append(alert)

            return alerts

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching NOAA weather data: {e}")
            return []
        except Exception as e:
            logger.error(f"Error processing NOAA weather data: {e}")
            return []

    def _extract_coordinates(self, geometry):
        """
        Extract representative coordinates from GeoJSON geometry

        Args:
            geometry (dict): GeoJSON geometry object

        Returns:
            tuple: (longitude, latitude) or None
        """
        if not geometry:
            return None

        try:
            geom_type = geometry.get('type')
            coordinates = geometry.get('coordinates')

            if not coordinates:
                return None

            if geom_type == 'Point':
                return coordinates
            elif geom_type == 'Polygon':
                # Use centroid of first ring
                return self._calculate_centroid(coordinates[0])
            elif geom_type == 'MultiPolygon':
                # Use centroid of first polygon's first ring
                if coordinates and len(coordinates) > 0:
                    return self._calculate_centroid(coordinates[0][0])

            return None

        except Exception:
            return None

    def _calculate_centroid(self, coordinates):
        """
        Calculate centroid of a polygon

        Args:
            coordinates (list): List of [lon, lat] coordinate pairs

        Returns:
            tuple: (longitude, latitude)
        """
        if not coordinates or len(coordinates) < 3:
            return None

        try:
            lon_sum = sum(coord[0] for coord in coordinates)
            lat_sum = sum(coord[1] for coord in coordinates)
            count = len(coordinates)

            return (lon_sum / count, lat_sum / count)

        except Exception:
            return None

    def _is_us_location(self, longitude, latitude):
        """
        Check if coordinates are within US boundaries (50 states only)

        Args:
            longitude (float): Longitude
            latitude (float): Latitude

        Returns:
            bool: True if within US 50 states boundaries
        """
        # US 50 states bounding boxes (excluding territories)
        # Continental US: -125 to -66, 24 to 49
        # Alaska: -180 to -130, 51 to 72
        # Hawaii: -160 to -154, 18 to 23

        if -125 <= longitude <= -66 and 24 <= latitude <= 49:
            return True  # Continental US
        if -180 <= longitude <= -130 and 51 <= latitude <= 72:
            return True  # Alaska
        if -160 <= longitude <= -154 and 18 <= latitude <= 23:
            return True  # Hawaii

        return False
