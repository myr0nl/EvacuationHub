"""
ProximityAlertService - Manages user proximity alerts for nearby disasters.

This service checks for disasters near a user's location and manages their
notification preferences, alert history, and acknowledgments.

Integrates with all 8 data sources:
- User reports
- NASA FIRMS wildfires
- NOAA weather alerts
- FEMA disaster declarations
- USGS earthquakes
- GDACS global events
- Cal Fire incidents
- Cal OES alerts
"""

import math
from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, List, Optional, Any
from utils.distance import haversine_distance

logger = logging.getLogger(__name__)


def validate_timestamp(timestamp_value: Any) -> Optional[str]:
    """
    Validate and normalize timestamp values from various data sources.

    Handles multiple timestamp formats:
    - ISO 8601 strings (e.g., "2025-10-19T09:02:00+00:00")
    - Unix timestamps in milliseconds (e.g., 1698566520000)
    - Unix timestamps in seconds (e.g., 1698566520)
    - datetime objects
    - None/null values

    Args:
        timestamp_value: Timestamp in various formats

    Returns:
        ISO 8601 formatted timestamp string if valid, None otherwise

    Examples:
        >>> validate_timestamp("2025-10-19T09:02:00+00:00")
        "2025-10-19T09:02:00+00:00"
        >>> validate_timestamp(1698566520000)  # milliseconds
        "2023-10-29T07:42:00+00:00"
        >>> validate_timestamp(1698566520)  # seconds
        "2023-10-29T07:42:00+00:00"
        >>> validate_timestamp(None)
        None
        >>> validate_timestamp("invalid")
        None
    """
    if timestamp_value is None:
        return None

    try:
        # Case 1: Already an ISO 8601 string
        if isinstance(timestamp_value, str):
            # Try parsing as ISO format
            dt = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
            return dt.isoformat()

        # Case 2: Unix timestamp (milliseconds or seconds)
        if isinstance(timestamp_value, (int, float)):
            # If > 1e10, it's in milliseconds (after year 2286 in seconds)
            if timestamp_value > 1e10:
                dt = datetime.fromtimestamp(timestamp_value / 1000, tz=timezone.utc)
            else:
                dt = datetime.fromtimestamp(timestamp_value, tz=timezone.utc)
            return dt.isoformat()

        # Case 3: datetime object
        if isinstance(timestamp_value, datetime):
            if timestamp_value.tzinfo is None:
                # Assume UTC if no timezone
                timestamp_value = timestamp_value.replace(tzinfo=timezone.utc)
            return timestamp_value.isoformat()

        # Unknown type
        logger.warning(f"Unknown timestamp type: {type(timestamp_value)}")
        return None

    except (ValueError, OSError, OverflowError) as e:
        logger.warning(f"Invalid timestamp value {timestamp_value}: {e}")
        return None


class ProximityAlertService:
    """
    Service for managing proximity-based disaster alerts for users.

    Monitors nearby disasters and sends alerts based on user preferences
    for distance thresholds, severity levels, and disaster types.
    """

    def __init__(self, firebase_db, cache_manager):
        """
        Initialize the ProximityAlertService.

        Args:
            firebase_db: Firebase database reference
            cache_manager: CacheManager instance for accessing cached data
        """
        self.db = firebase_db
        self.cache = cache_manager

        # Distance thresholds for alert severity levels (in miles)
        self.alert_thresholds = {
            'critical': 5,   # miles
            'high': 15,      # miles
            'medium': 30,    # miles
            'low': 50        # miles
        }

        # Default disaster severity ranking for comparison
        self.severity_ranking = {
            'critical': 4,
            'high': 3,
            'medium': 2,
            'low': 1
        }

    def check_proximity_alerts(
        self,
        user_lat: float,
        user_lon: float,
        user_id: str,
        radius_mi: Optional[float] = 50
    ) -> Dict[str, Any]:
        """
        Check for disasters within the specified radius of user's location.

        Queries all 8 data sources (user reports + 7 official sources) and
        returns disasters within the radius, sorted by distance.

        Args:
            user_lat: User's latitude
            user_lon: User's longitude
            user_id: User identifier for filtering preferences
            radius_mi: Search radius in miles (default: 50 miles)

        Returns:
            Dict containing:
                - alerts: List of nearby disasters with details
                - highest_severity: Most severe alert level found
                - count: Total number of alerts
                - closest_distance: Distance to nearest disaster in miles
        """
        try:
            alerts = []

            # Fetch user preferences to filter results
            preferences = self.get_user_alert_preferences(user_id)
            if not preferences.get('enabled', True):
                return {
                    'alerts': [],
                    'highest_severity': None,
                    'count': 0,
                    'closest_distance': None
                }

            # Use explicitly passed radius parameter (takes priority over preferences)
            # This allows real-time radius adjustments without saving preferences
            search_radius = radius_mi
            severity_filter = set(preferences.get('severity_filter', ['critical', 'high', 'medium', 'low']))
            disaster_types_filter = set(preferences.get('disaster_types', []))

            # 1. Fetch user reports
            alerts.extend(self._fetch_nearby_user_reports(
                user_lat, user_lon, search_radius, disaster_types_filter
            ))

            # 2. Fetch NASA FIRMS wildfires
            alerts.extend(self._fetch_nearby_wildfires(
                user_lat, user_lon, search_radius, disaster_types_filter
            ))

            # 3. Fetch NOAA weather alerts
            alerts.extend(self._fetch_nearby_weather_alerts(
                user_lat, user_lon, search_radius, disaster_types_filter
            ))

            # 4. Fetch FEMA disaster declarations
            alerts.extend(self._fetch_nearby_fema_disasters(
                user_lat, user_lon, search_radius, disaster_types_filter
            ))

            # 5. Fetch USGS earthquakes
            alerts.extend(self._fetch_nearby_earthquakes(
                user_lat, user_lon, search_radius, disaster_types_filter
            ))

            # 6. Fetch GDACS events
            alerts.extend(self._fetch_nearby_gdacs_events(
                user_lat, user_lon, search_radius, disaster_types_filter
            ))

            # 7. Fetch Cal Fire incidents
            alerts.extend(self._fetch_nearby_cal_fire(
                user_lat, user_lon, search_radius, disaster_types_filter
            ))

            # 8. Fetch Cal OES alerts
            alerts.extend(self._fetch_nearby_cal_oes(
                user_lat, user_lon, search_radius, disaster_types_filter
            ))

            # Filter by severity preferences
            filtered_alerts = [
                alert for alert in alerts
                if alert.get('alert_severity', 'low') in severity_filter
            ]

            # Sort by distance (closest first)
            filtered_alerts.sort(key=lambda x: x['distance_mi'])

            # Calculate summary statistics
            highest_severity = self._determine_highest_severity(filtered_alerts)
            closest_distance = filtered_alerts[0]['distance_mi'] if filtered_alerts else None

            return {
                'alerts': filtered_alerts,
                'highest_severity': highest_severity,
                'count': len(filtered_alerts),
                'closest_distance': closest_distance
            }

        except Exception as e:
            logger.error(f"Error checking proximity alerts: {e}")
            return {
                'alerts': [],
                'highest_severity': None,
                'count': 0,
                'closest_distance': None,
                'error': str(e)
            }

    def get_user_alert_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch user's alert preferences from Firebase.

        Args:
            user_id: User identifier

        Returns:
            Dict containing user preferences or defaults if not found
        """
        try:
            ref = self.db.reference(f'user_alert_preferences/{user_id}')
            preferences = ref.get()

            if preferences:
                # Ensure show_radius_circle field exists (for backwards compatibility)
                if 'show_radius_circle' not in preferences:
                    preferences['show_radius_circle'] = True
                return preferences

            # Return default preferences if none exist
            return {
                'enabled': True,
                'radius_mi': 50,  # DEPRECATED: Use map_settings.display_radius_mi instead
                'show_radius_circle': True,
                'severity_filter': ['critical', 'high', 'medium', 'low'],
                'disaster_types': [
                    'earthquake', 'flood', 'wildfire', 'hurricane',
                    'tornado', 'volcano', 'drought'
                ],
                'notification_channels': ['in_app'],
                'quiet_hours': {
                    'enabled': False,
                    'start': '22:00',
                    'end': '07:00'
                },
                'map_settings': {
                    'zoom_radius_mi': 20,
                    'display_radius_mi': 20,
                    'auto_zoom': True,
                    'show_all_disasters': False
                }
            }

        except Exception as e:
            logger.error(f"Error fetching user preferences: {e}")
            # Return defaults on error
            return {
                'enabled': True,
                'radius_mi': 50,  # DEPRECATED: Use map_settings.display_radius_mi instead
                'show_radius_circle': True,
                'severity_filter': ['critical', 'high', 'medium', 'low'],
                'disaster_types': [
                    'earthquake', 'flood', 'wildfire', 'hurricane',
                    'tornado', 'volcano', 'drought'
                ],
                'notification_channels': ['in_app'],
                'quiet_hours': {
                    'enabled': False,
                    'start': '22:00',
                    'end': '07:00'
                },
                'map_settings': {
                    'zoom_radius_mi': 20,
                    'display_radius_mi': 20,
                    'auto_zoom': True,
                    'show_all_disasters': False
                }
            }

    def save_alert_notification(self, user_id: str, alert_data: Dict[str, Any]) -> Optional[str]:
        """
        Save an alert notification to Firebase.

        Args:
            user_id: User identifier
            alert_data: Alert information including disaster details

        Returns:
            Alert ID if successful, None otherwise
        """
        try:
            # Generate unique alert ID
            alerts_ref = self.db.reference(f'user_notifications/{user_id}/alerts')
            new_alert_ref = alerts_ref.push()
            alert_id = new_alert_ref.key

            # Prepare notification data
            notification = {
                'disaster_id': alert_data.get('id'),
                'disaster_type': alert_data.get('type'),
                'severity': alert_data.get('severity'),
                'alert_severity': alert_data.get('alert_severity', 'low'),
                'distance_mi': alert_data.get('distance_mi'),
                'latitude': alert_data.get('latitude'),
                'longitude': alert_data.get('longitude'),
                'source': alert_data.get('source'),
                'timestamp': validate_timestamp(alert_data.get('timestamp')) or datetime.now(timezone.utc).isoformat(),  # Use original event timestamp
                'acknowledged': False,
                'expires_at': (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            }

            # Add optional fields if present
            if 'description' in alert_data:
                notification['description'] = alert_data['description']
            if 'location_name' in alert_data:
                notification['location_name'] = alert_data['location_name']

            new_alert_ref.set(notification)
            return alert_id

        except Exception as e:
            logger.error(f"Error saving alert notification: {e}")
            return None

    def update_alert_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """
        Update user's alert preferences with validation.

        Args:
            user_id: User identifier
            preferences: New preferences to save

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate preferences
            valid_severity_levels = {'critical', 'high', 'medium', 'low'}
            valid_disaster_types = {
                'earthquake', 'flood', 'wildfire', 'hurricane',
                'tornado', 'volcano', 'drought'
            }

            # Validate radius (accept both radius_mi and radius_km for backwards compatibility)
            radius = preferences.get('radius_mi') or preferences.get('radius_km', 50)
            if not (5 <= radius <= 50):
                logger.warning(f"Invalid radius: {radius}. Must be between 5 and 50 miles.")
                return False

            # Validate severity filter
            severity_filter = preferences.get('severity_filter', [])
            if not set(severity_filter).issubset(valid_severity_levels):
                logger.warning(f"Invalid severity levels in filter: {severity_filter}")
                return False

            # Validate disaster types
            disaster_types = preferences.get('disaster_types', [])
            if not set(disaster_types).issubset(valid_disaster_types):
                logger.warning(f"Invalid disaster types: {disaster_types}")
                return False

            # Save validated preferences
            ref = self.db.reference(f'user_alert_preferences/{user_id}')
            ref.set({
                'enabled': preferences.get('enabled', True),
                'radius_mi': radius,
                'show_radius_circle': preferences.get('show_radius_circle', True),
                'severity_filter': severity_filter,
                'disaster_types': disaster_types,
                'notification_channels': preferences.get('notification_channels', ['in_app']),
                'quiet_hours': preferences.get('quiet_hours', {
                    'enabled': False,
                    'start': '22:00',
                    'end': '07:00'
                }),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })

            return True

        except Exception as e:
            logger.error(f"Error updating alert preferences: {e}")
            return False

    def acknowledge_alert(self, user_id: str, alert_id: str) -> bool:
        """
        Mark an alert as acknowledged by the user.

        Args:
            user_id: User identifier
            alert_id: Alert identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            ref = self.db.reference(f'user_notifications/{user_id}/alerts/{alert_id}')
            alert = ref.get()

            if not alert:
                logger.info(f"Alert {alert_id} not found for user {user_id}")
                return False

            ref.update({
                'acknowledged': True,
                'acknowledged_at': datetime.now(timezone.utc).isoformat()
            })

            return True

        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            return False

    def get_notification_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch user's notification history from Firebase.

        Args:
            user_id: User identifier
            limit: Maximum number of notifications to return (default: 50)

        Returns:
            List of notifications sorted by timestamp (newest first)
        """
        try:
            ref = self.db.reference(f'user_notifications/{user_id}/alerts')
            alerts = ref.get()

            if not alerts:
                return []

            # Convert to list of dicts with IDs
            alert_list = [
                {'alert_id': alert_id, **alert_data}
                for alert_id, alert_data in alerts.items()
            ]

            # Sort by timestamp (newest first)
            alert_list.sort(
                key=lambda x: x.get('timestamp', ''),
                reverse=True
            )

            # Apply limit
            return alert_list[:limit]

        except Exception as e:
            logger.error(f"Error fetching notification history: {e}")
            return []

    def get_map_settings(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch user's map settings from Firebase.

        Args:
            user_id: User identifier

        Returns:
            Dict containing map settings or defaults if not found
        """
        try:
            ref = self.db.reference(f'user_map_settings/{user_id}')
            settings = ref.get()

            if settings:
                return settings

            # Return default settings if none exist
            return {
                'zoom_radius_mi': 20,
                'display_radius_mi': 20,
                'auto_zoom': True,
                'show_all_disasters': False
            }

        except Exception as e:
            logger.error(f"Error fetching map settings: {e}")
            # Return defaults on error
            return {
                'zoom_radius_mi': 20,
                'display_radius_mi': 20,
                'auto_zoom': True,
                'show_all_disasters': False
            }

    def update_map_settings(self, user_id: str, settings: Dict[str, Any]) -> bool:
        """
        Update user's map settings with validation.

        Args:
            user_id: User identifier
            settings: New map settings to save

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate display_radius_mi (1-100 miles)
            display_radius = settings.get('display_radius_mi', 20)
            if not (1 <= display_radius <= 100):
                logger.warning(f"Invalid display_radius_mi: {display_radius}. Must be between 1 and 100 miles.")
                return False

            # Validate zoom_radius_mi (1-100 miles)
            zoom_radius = settings.get('zoom_radius_mi', 20)
            if not (1 <= zoom_radius <= 100):
                logger.warning(f"Invalid zoom_radius_mi: {zoom_radius}. Must be between 1 and 100 miles.")
                return False

            # Validate boolean fields
            auto_zoom = settings.get('auto_zoom', True)
            if not isinstance(auto_zoom, bool):
                logger.warning(f"Invalid auto_zoom: {auto_zoom}. Must be a boolean.")
                return False

            show_all_disasters = settings.get('show_all_disasters', False)
            if not isinstance(show_all_disasters, bool):
                logger.warning(f"Invalid show_all_disasters: {show_all_disasters}. Must be a boolean.")
                return False

            # Save validated settings
            ref = self.db.reference(f'user_map_settings/{user_id}')
            ref.set({
                'zoom_radius_mi': zoom_radius,
                'display_radius_mi': display_radius,
                'auto_zoom': auto_zoom,
                'show_all_disasters': show_all_disasters,
                'updated_at': datetime.now(timezone.utc).isoformat()
            })

            return True

        except Exception as e:
            logger.error(f"Error updating map settings: {e}")
            return False

    def _is_in_quiet_hours(self, preferences: Dict[str, Any]) -> bool:
        """
        Check if current time is within user's quiet hours.

        Args:
            preferences: User's alert preferences

        Returns:
            True if in quiet hours, False otherwise
        """
        try:
            quiet_hours = preferences.get('quiet_hours', {})
            if not quiet_hours.get('enabled', False):
                return False

            now = datetime.now(timezone.utc)
            current_time = now.strftime('%H:%M')

            start_time = quiet_hours.get('start', '22:00')
            end_time = quiet_hours.get('end', '07:00')

            # Handle overnight quiet hours (e.g., 22:00 to 07:00)
            if start_time > end_time:
                return current_time >= start_time or current_time <= end_time
            else:
                return start_time <= current_time <= end_time

        except Exception as e:
            logger.error(f"Error checking quiet hours: {e}")
            return False

    def _calculate_severity_level(self, disaster_data: Dict[str, Any], distance_mi: float) -> str:
        """
        Calculate alert severity level based on disaster severity and distance.

        Args:
            disaster_data: Disaster information including severity
            distance_mi: Distance from user in miles

        Returns:
            Alert severity level: 'critical', 'high', 'medium', or 'low'
        """
        disaster_severity = disaster_data.get('severity', 'low').lower()

        # Critical: high severity disaster within 5km
        if disaster_severity in ['critical', 'high'] and distance_mi <= self.alert_thresholds['critical']:
            return 'critical'

        # High: high severity within 15km OR critical severity within 15km
        if disaster_severity in ['critical', 'high'] and distance_mi <= self.alert_thresholds['high']:
            return 'high'

        # Medium: medium severity within 30km OR high severity within 30km
        if disaster_severity in ['medium', 'high', 'critical'] and distance_mi <= self.alert_thresholds['medium']:
            return 'medium'

        # Low: any disaster within 50km
        if distance_mi <= self.alert_thresholds['low']:
            return 'low'

        return 'low'

    def _is_within_bounding_box(self, user_lat: float, user_lon: float,
                                  point_lat: float, point_lon: float,
                                  radius_mi: float) -> bool:
        """
        Quick bounding box check before expensive haversine calculation.
        Approximately 1 degree = 69.1 miles at equator.

        Args:
            user_lat: User's latitude
            user_lon: User's longitude
            point_lat: Point's latitude
            point_lon: Point's longitude
            radius_mi: Radius in miles

        Returns:
            True if point is within bounding box, False otherwise
        """
        # Approximate degrees per mile (varies by latitude)
        lat_degrees_per_mi = 1.0 / 69.1
        lon_degrees_per_mi = 1.0 / (69.1 * math.cos(math.radians(user_lat)))

        lat_diff = abs(point_lat - user_lat)
        lon_diff = abs(point_lon - user_lon)

        return (lat_diff <= radius_mi * lat_degrees_per_mi and
                lon_diff <= radius_mi * lon_degrees_per_mi)


    def _determine_highest_severity(self, alerts: List[Dict[str, Any]]) -> Optional[str]:
        """
        Determine the highest severity level among alerts.

        Args:
            alerts: List of alert dictionaries

        Returns:
            Highest severity level or None if no alerts
        """
        if not alerts:
            return None

        highest_rank = 0
        highest_severity = 'low'

        for alert in alerts:
            severity = alert.get('alert_severity', 'low')
            rank = self.severity_ranking.get(severity, 1)
            if rank > highest_rank:
                highest_rank = rank
                highest_severity = severity

        return highest_severity

    # Data source fetching methods

    def _fetch_nearby_user_reports(
        self,
        lat: float,
        lon: float,
        radius_mi: float,
        disaster_types_filter: set
    ) -> List[Dict[str, Any]]:
        """Fetch nearby user reports from Firebase."""
        try:
            reports_ref = self.db.reference('reports')
            reports = reports_ref.get()

            if not reports:
                return []

            nearby = []
            for report_id, report_data in reports.items():
                # Skip if disaster type not in filter (if filter is set)
                if disaster_types_filter and report_data.get('type') not in disaster_types_filter:
                    continue

                report_lat = report_data.get('latitude', 0)
                report_lon = report_data.get('longitude', 0)

                # Quick bounding box check before expensive haversine
                if not self._is_within_bounding_box(lat, lon, report_lat, report_lon, radius_mi):
                    continue

                distance = haversine_distance(lat, lon, report_lat, report_lon)

                if distance <= radius_mi:
                    alert_severity = self._calculate_severity_level(report_data, distance)
                    nearby.append({
                        'id': report_id,
                        'type': report_data.get('type'),
                        'disaster_type': report_data.get('type'),  # Add for frontend display
                        'severity': report_data.get('severity', 'low'),
                        'alert_severity': alert_severity,
                        'distance_mi': round(distance, 2),
                        'latitude': report_data.get('latitude'),
                        'longitude': report_data.get('longitude'),
                        'source': 'user_report',
                        'timestamp': validate_timestamp(report_data.get('timestamp')),
                        'description': report_data.get('description', ''),
                        'location_name': report_data.get('location_name', '')
                    })

            return nearby

        except Exception as e:
            logger.error(f"Error fetching nearby user reports: {e}")
            return []

    def _fetch_nearby_wildfires(
        self,
        lat: float,
        lon: float,
        radius_mi: float,
        disaster_types_filter: set
    ) -> List[Dict[str, Any]]:
        """Fetch nearby NASA FIRMS wildfires from cache."""
        try:
            # Skip if wildfire not in filter
            if disaster_types_filter and 'wildfire' not in disaster_types_filter:
                return []

            cache_ref = self.db.reference('public_data_cache/wildfires/data')
            wildfires = cache_ref.get()

            if not wildfires:
                return []

            nearby = []
            for fire in wildfires:
                distance = haversine_distance(
                    lat, lon,
                    fire.get('latitude', 0),
                    fire.get('longitude', 0)
                )

                if distance <= radius_mi:
                    # Determine severity based on brightness/FRP
                    brightness = fire.get('brightness', 0)
                    severity = 'high' if brightness > 350 else 'medium'

                    fire_data = {'severity': severity}
                    alert_severity = self._calculate_severity_level(fire_data, distance)

                    nearby.append({
                        'id': f"firms_{fire.get('latitude')}_{fire.get('longitude')}",
                        'type': 'wildfire',
                        'disaster_type': 'wildfire',  # Add for frontend display
                        'severity': severity,
                        'alert_severity': alert_severity,
                        'distance_mi': round(distance, 2),
                        'latitude': fire.get('latitude'),
                        'longitude': fire.get('longitude'),
                        'source': 'nasa_firms',
                        'timestamp': validate_timestamp(fire.get('timestamp')),
                        'description': f"Satellite-detected fire (brightness: {brightness}K)"
                    })

            return nearby

        except Exception as e:
            logger.error(f"Error fetching nearby wildfires: {e}")
            return []

    def _fetch_nearby_weather_alerts(
        self,
        lat: float,
        lon: float,
        radius_mi: float,
        disaster_types_filter: set
    ) -> List[Dict[str, Any]]:
        """Fetch nearby NOAA weather alerts from cache."""
        try:
            cache_ref = self.db.reference('public_data_cache/weather_alerts/data')
            alerts = cache_ref.get()

            if not alerts:
                return []

            nearby = []
            for alert in alerts:
                # Map NOAA event types to our disaster types
                event = alert.get('event', '').lower()
                disaster_type = self._map_noaa_event_to_disaster_type(event)

                # Skip if disaster type not in filter
                if disaster_types_filter and disaster_type not in disaster_types_filter:
                    continue

                distance = haversine_distance(
                    lat, lon,
                    alert.get('latitude', 0),
                    alert.get('longitude', 0)
                )

                if distance <= radius_mi:
                    # Map NOAA severity to our severity levels
                    noaa_severity = alert.get('severity', 'Minor').lower()
                    severity = self._map_noaa_severity(noaa_severity)

                    alert_data = {'severity': severity}
                    alert_severity = self._calculate_severity_level(alert_data, distance)

                    nearby.append({
                        'id': alert.get('id'),
                        'type': disaster_type,
                        'disaster_type': disaster_type,  # Add for frontend display
                        'severity': severity,
                        'alert_severity': alert_severity,
                        'distance_mi': round(distance, 2),
                        'latitude': alert.get('latitude'),
                        'longitude': alert.get('longitude'),
                        'source': 'noaa_weather',
                        'timestamp': validate_timestamp(alert.get('sent')),
                        'description': alert.get('event', ''),
                        'location_name': alert.get('area_desc', '')
                    })

            return nearby

        except Exception as e:
            logger.error(f"Error fetching nearby weather alerts: {e}")
            return []

    def _fetch_nearby_fema_disasters(
        self,
        lat: float,
        lon: float,
        radius_mi: float,
        disaster_types_filter: set
    ) -> List[Dict[str, Any]]:
        """Fetch nearby FEMA disaster declarations from cache."""
        try:
            cache_ref = self.db.reference('public_data_cache/fema_disasters/data')
            disasters = cache_ref.get()

            if not disasters:
                return []

            nearby = []
            for disaster in disasters:
                # Map FEMA incident type to our disaster types
                incident_type = disaster.get('incident_type', '').lower()
                disaster_type = self._map_fema_incident_to_disaster_type(incident_type)

                # Skip if disaster type not in filter
                if disaster_types_filter and disaster_type not in disaster_types_filter:
                    continue

                distance = haversine_distance(
                    lat, lon,
                    disaster.get('latitude', 0),
                    disaster.get('longitude', 0)
                )

                if distance <= radius_mi:
                    # FEMA disasters are typically high severity (federally declared)
                    disaster_data = {'severity': 'high'}
                    alert_severity = self._calculate_severity_level(disaster_data, distance)

                    nearby.append({
                        'id': disaster.get('disaster_number'),
                        'type': disaster_type,
                        'disaster_type': disaster_type,  # Add for frontend display
                        'severity': 'high',
                        'alert_severity': alert_severity,
                        'distance_mi': round(distance, 2),
                        'latitude': disaster.get('latitude'),
                        'longitude': disaster.get('longitude'),
                        'source': 'fema',
                        'timestamp': validate_timestamp(disaster.get('declaration_date')),
                        'description': disaster.get('incident_type', ''),
                        'location_name': disaster.get('state', '')
                    })

            return nearby

        except Exception as e:
            logger.error(f"Error fetching nearby FEMA disasters: {e}")
            return []

    def _fetch_nearby_earthquakes(
        self,
        lat: float,
        lon: float,
        radius_mi: float,
        disaster_types_filter: set
    ) -> List[Dict[str, Any]]:
        """Fetch nearby USGS earthquakes from cache."""
        try:
            # Skip if earthquake not in filter
            if disaster_types_filter and 'earthquake' not in disaster_types_filter:
                return []

            cache_ref = self.db.reference('public_data_cache/usgs_earthquakes/data')
            earthquakes = cache_ref.get()

            if not earthquakes:
                return []

            nearby = []
            for quake in earthquakes:
                distance = haversine_distance(
                    lat, lon,
                    quake.get('latitude', 0),
                    quake.get('longitude', 0)
                )

                if distance <= radius_mi:
                    # Determine severity based on magnitude
                    magnitude = quake.get('magnitude', 0)
                    if magnitude >= 6.0:
                        severity = 'critical'
                    elif magnitude >= 5.0:
                        severity = 'high'
                    elif magnitude >= 4.0:
                        severity = 'medium'
                    else:
                        severity = 'low'

                    quake_data = {'severity': severity}
                    alert_severity = self._calculate_severity_level(quake_data, distance)

                    nearby.append({
                        'id': quake.get('id'),
                        'type': 'earthquake',
                        'disaster_type': 'earthquake',  # Add for frontend display
                        'severity': severity,
                        'alert_severity': alert_severity,
                        'distance_mi': round(distance, 2),
                        'latitude': quake.get('latitude'),
                        'longitude': quake.get('longitude'),
                        'source': 'usgs',
                        'timestamp': validate_timestamp(quake.get('timestamp')),  # FIX: Changed from 'time' to 'timestamp'
                        'description': f"Magnitude {magnitude} earthquake",
                        'location_name': quake.get('place', '')
                    })

            return nearby

        except Exception as e:
            logger.error(f"Error fetching nearby earthquakes: {e}")
            return []

    def _fetch_nearby_gdacs_events(
        self,
        lat: float,
        lon: float,
        radius_mi: float,
        disaster_types_filter: set
    ) -> List[Dict[str, Any]]:
        """Fetch nearby GDACS events from cache."""
        try:
            cache_ref = self.db.reference('public_data_cache/gdacs_events/data')
            events = cache_ref.get()

            if not events:
                return []

            nearby = []
            for event in events:
                # Map GDACS event type to our disaster types
                event_type = event.get('event_type', '').lower()
                disaster_type = self._map_gdacs_event_to_disaster_type(event_type)

                # Skip if disaster type not in filter
                if disaster_types_filter and disaster_type not in disaster_types_filter:
                    continue

                distance = haversine_distance(
                    lat, lon,
                    event.get('latitude', 0),
                    event.get('longitude', 0)
                )

                if distance <= radius_mi:
                    # Map GDACS alert level to severity
                    alert_level = event.get('alert_level', 'Green').lower()
                    severity = self._map_gdacs_alert_level(alert_level)

                    event_data = {'severity': severity}
                    alert_severity = self._calculate_severity_level(event_data, distance)

                    nearby.append({
                        'id': event.get('id'),
                        'type': disaster_type,
                        'disaster_type': disaster_type,  # Add for frontend display
                        'severity': severity,
                        'alert_severity': alert_severity,
                        'distance_mi': round(distance, 2),
                        'latitude': event.get('latitude'),
                        'longitude': event.get('longitude'),
                        'source': 'gdacs',
                        'timestamp': validate_timestamp(event.get('from_date')),
                        'description': event.get('event_name', ''),
                        'location_name': event.get('country', '')
                    })

            return nearby

        except Exception as e:
            logger.error(f"Error fetching nearby GDACS events: {e}")
            return []

    def _fetch_nearby_cal_fire(
        self,
        lat: float,
        lon: float,
        radius_mi: float,
        disaster_types_filter: set
    ) -> List[Dict[str, Any]]:
        """Fetch nearby Cal Fire incidents from cache."""
        try:
            # Skip if wildfire not in filter
            if disaster_types_filter and 'wildfire' not in disaster_types_filter:
                return []

            cache_ref = self.db.reference('public_data_cache/cal_fire_incidents/data')
            incidents = cache_ref.get()

            if not incidents:
                return []

            nearby = []
            for incident in incidents:
                distance = haversine_distance(
                    lat, lon,
                    incident.get('latitude', 0),
                    incident.get('longitude', 0)
                )

                if distance <= radius_mi:
                    # Determine severity based on acres burned
                    acres = incident.get('acres_burned', 0)
                    if acres > 10000:
                        severity = 'critical'
                    elif acres > 1000:
                        severity = 'high'
                    elif acres > 100:
                        severity = 'medium'
                    else:
                        severity = 'low'

                    incident_data = {'severity': severity}
                    alert_severity = self._calculate_severity_level(incident_data, distance)

                    nearby.append({
                        'id': incident.get('id'),
                        'type': 'wildfire',
                        'disaster_type': 'wildfire',  # Add for frontend display
                        'severity': severity,
                        'alert_severity': alert_severity,
                        'distance_mi': round(distance, 2),
                        'latitude': incident.get('latitude'),
                        'longitude': incident.get('longitude'),
                        'source': 'cal_fire',
                        'timestamp': validate_timestamp(incident.get('updated')),
                        'description': f"{incident.get('name', 'Wildfire')} - {acres} acres",
                        'location_name': incident.get('county', '')
                    })

            return nearby

        except Exception as e:
            logger.error(f"Error fetching nearby Cal Fire incidents: {e}")
            return []

    def _fetch_nearby_cal_oes(
        self,
        lat: float,
        lon: float,
        radius_mi: float,
        disaster_types_filter: set
    ) -> List[Dict[str, Any]]:
        """Fetch nearby Cal OES alerts from cache."""
        try:
            cache_ref = self.db.reference('public_data_cache/cal_oes_alerts/data')
            alerts = cache_ref.get()

            if not alerts:
                return []

            nearby = []
            for alert in alerts:
                # Cal OES alerts may not have precise coordinates
                # Skip if no valid coordinates
                if not alert.get('latitude') or not alert.get('longitude'):
                    continue

                # Map Cal OES alert to disaster type (generic emergency)
                disaster_type = self._map_cal_oes_to_disaster_type(alert.get('title', ''))

                # Skip if disaster type not in filter
                if disaster_types_filter and disaster_type not in disaster_types_filter:
                    continue

                distance = haversine_distance(
                    lat, lon,
                    alert.get('latitude', 0),
                    alert.get('longitude', 0)
                )

                if distance <= radius_mi:
                    # Cal OES alerts are state-level, typically high severity
                    alert_data = {'severity': 'high'}
                    alert_severity = self._calculate_severity_level(alert_data, distance)

                    nearby.append({
                        'id': alert.get('id'),
                        'type': disaster_type,
                        'disaster_type': disaster_type,  # Add for frontend display
                        'severity': 'high',
                        'alert_severity': alert_severity,
                        'distance_mi': round(distance, 2),
                        'latitude': alert.get('latitude'),
                        'longitude': alert.get('longitude'),
                        'source': 'cal_oes',
                        'timestamp': validate_timestamp(alert.get('pub_date')),
                        'description': alert.get('title', ''),
                        'location_name': 'California'
                    })

            return nearby

        except Exception as e:
            logger.error(f"Error fetching nearby Cal OES alerts: {e}")
            return []

    # Helper methods for mapping external data to our disaster types

    def _map_noaa_event_to_disaster_type(self, event: str) -> str:
        """Map NOAA event type to our disaster types."""
        event_lower = event.lower()
        if 'flood' in event_lower:
            return 'flood'
        elif 'hurricane' in event_lower or 'tropical storm' in event_lower:
            return 'hurricane'
        elif 'tornado' in event_lower:
            return 'tornado'
        elif 'fire' in event_lower:
            return 'wildfire'
        elif 'drought' in event_lower:
            return 'drought'
        else:
            return 'flood'  # Default for weather events

    def _map_noaa_severity(self, severity: str) -> str:
        """Map NOAA severity levels to our severity levels."""
        severity_map = {
            'extreme': 'critical',
            'severe': 'high',
            'moderate': 'medium',
            'minor': 'low',
            'unknown': 'low'
        }
        return severity_map.get(severity, 'low')

    def _map_fema_incident_to_disaster_type(self, incident_type: str) -> str:
        """Map FEMA incident type to our disaster types."""
        incident_lower = incident_type.lower()
        if 'flood' in incident_lower:
            return 'flood'
        elif 'hurricane' in incident_lower:
            return 'hurricane'
        elif 'tornado' in incident_lower:
            return 'tornado'
        elif 'fire' in incident_lower:
            return 'wildfire'
        elif 'earthquake' in incident_lower:
            return 'earthquake'
        elif 'drought' in incident_lower:
            return 'drought'
        else:
            return 'flood'  # Default

    def _map_gdacs_event_to_disaster_type(self, event_type: str) -> str:
        """Map GDACS event type to our disaster types."""
        event_lower = event_type.lower()
        if 'eq' in event_lower or 'earthquake' in event_lower:
            return 'earthquake'
        elif 'fl' in event_lower or 'flood' in event_lower:
            return 'flood'
        elif 'tc' in event_lower or 'cyclone' in event_lower or 'hurricane' in event_lower:
            return 'hurricane'
        elif 'dr' in event_lower or 'drought' in event_lower:
            return 'drought'
        elif 'vo' in event_lower or 'volcano' in event_lower:
            return 'volcano'
        else:
            return 'flood'  # Default

    def _map_gdacs_alert_level(self, alert_level: str) -> str:
        """Map GDACS alert level to our severity levels."""
        alert_map = {
            'red': 'critical',
            'orange': 'high',
            'green': 'medium'
        }
        return alert_map.get(alert_level, 'low')

    def _map_cal_oes_to_disaster_type(self, title: str) -> str:
        """Map Cal OES alert title to our disaster types."""
        title_lower = title.lower()
        if 'fire' in title_lower:
            return 'wildfire'
        elif 'flood' in title_lower:
            return 'flood'
        elif 'earthquake' in title_lower:
            return 'earthquake'
        elif 'drought' in title_lower:
            return 'drought'
        else:
            return 'wildfire'  # Default for California
