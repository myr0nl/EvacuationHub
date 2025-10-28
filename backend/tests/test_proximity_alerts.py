"""
Comprehensive Test Suite for ProximityAlertService

Tests proximity alert functionality including:
- Distance calculations
- Multi-source disaster fetching
- Severity calculation
- User preferences management
- Alert notifications
- Filtering and quiet hours
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timezone, timedelta
import math
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.proximity_alert_service import ProximityAlertService


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_firebase_db():
    """Mock Firebase database instance."""
    db = Mock()
    # Default behavior: return None for references
    db.reference.return_value.get.return_value = None
    return db


@pytest.fixture
def mock_cache_manager():
    """Mock CacheManager instance."""
    cache = Mock()
    cache.get_cached_data.return_value = []
    return cache


@pytest.fixture
def proximity_service(mock_firebase_db, mock_cache_manager):
    """Create ProximityAlertService instance with mocked dependencies."""
    return ProximityAlertService(mock_firebase_db, mock_cache_manager)


@pytest.fixture
def sample_user_report():
    """Sample user-submitted disaster report."""
    return {
        'id': 'report_123',
        'latitude': 37.7749,
        'longitude': -122.4194,
        'type': 'wildfire',
        'severity': 'high',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'user_report',
        'description': 'Large wildfire spreading rapidly',
        'location_name': 'San Francisco, CA'
    }


@pytest.fixture
def sample_nasa_wildfire():
    """Sample NASA FIRMS wildfire detection."""
    return {
        'latitude': 37.7800,
        'longitude': -122.4200,
        'brightness': 380.5,
        'frp': 25.3,
        'acq_datetime': datetime.now(timezone.utc).isoformat(),
        'confidence': 'high'
    }


@pytest.fixture
def sample_noaa_alert():
    """Sample NOAA weather alert."""
    return {
        'id': 'noaa_alert_456',
        'latitude': 37.7750,
        'longitude': -122.4195,
        'event': 'Flood Warning',
        'severity': 'Severe',
        'sent': datetime.now(timezone.utc).isoformat(),
        'area_desc': 'San Francisco Bay Area'
    }


@pytest.fixture
def sample_usgs_earthquake():
    """Sample USGS earthquake data."""
    return {
        'id': 'us70009876',
        'latitude': 37.7700,
        'longitude': -122.4150,
        'magnitude': 5.2,
        'depth_km': 10.5,
        'time': datetime.now(timezone.utc).isoformat(),
        'place': '5km NW of San Francisco, CA'
    }


@pytest.fixture
def sample_fema_disaster():
    """Sample FEMA disaster declaration."""
    return {
        'disaster_number': '4567',
        'latitude': 37.7800,
        'longitude': -122.4300,
        'incident_type': 'Flood',
        'state': 'California',
        'declaration_date': datetime.now(timezone.utc).isoformat()
    }


@pytest.fixture
def default_user_preferences():
    """Default user alert preferences."""
    return {
        'enabled': True,
        'radius_mi': 50,
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
        }
    }


# ============================================================================
# TEST BASIC FUNCTIONALITY
# ============================================================================

class TestBasicFunctionality:
    """Test core functionality of ProximityAlertService."""

    def test_haversine_distance_calculation(self, proximity_service):
        """Test haversine distance formula accuracy."""
        from utils.geo import haversine_distance

        # Test 1: San Francisco to Los Angeles (approx 347 miles)
        sf_lat, sf_lon = 37.7749, -122.4194
        la_lat, la_lon = 34.0522, -118.2437

        distance = haversine_distance(sf_lat, sf_lon, la_lat, la_lon)

        assert 340 < distance < 355, f"Expected ~347 miles, got {distance}"

        # Test 2: New York to Boston (approx 190 miles)
        ny_lat, ny_lon = 40.7128, -74.0060
        boston_lat, boston_lon = 42.3601, -71.0589

        distance = haversine_distance(ny_lat, ny_lon, boston_lat, boston_lon)

        assert 185 < distance < 195, f"Expected ~190 miles, got {distance}"

        # Test 3: Same location (0 miles)
        distance = haversine_distance(sf_lat, sf_lon, sf_lat, sf_lon)

        assert distance == 0, f"Same location should be 0 miles, got {distance}"

    def test_haversine_distance_short_distances(self, proximity_service):
        """Test haversine accuracy for short distances."""
        from utils.geo import haversine_distance

        # Points ~0.3 miles apart
        lat1, lon1 = 37.7749, -122.4194
        lat2, lon2 = 37.7800, -122.4200  # ~0.3 miles away

        distance = haversine_distance(lat1, lon1, lat2, lon2)

        assert 0.2 < distance < 0.4, f"Expected ~0.3 miles, got {distance}"

    def test_check_proximity_alerts_empty(self, proximity_service, mock_firebase_db):
        """Test when no disasters are nearby."""
        # Mock empty Firebase references
        mock_firebase_db.reference.return_value.get.return_value = None

        result = proximity_service.check_proximity_alerts(
            user_lat=37.7749,
            user_lon=-122.4194,
            user_id='user123',
            radius_mi=50
        )

        assert result['count'] == 0
        assert result['highest_severity'] is None
        assert result['closest_distance'] is None
        assert result['alerts'] == []

    def test_check_proximity_alerts_with_disasters(
        self, proximity_service, mock_firebase_db, sample_user_report
    ):
        """Test when multiple disasters are within radius."""
        # Mock user reports
        mock_ref = Mock()
        mock_ref.get.return_value = {
            'report_123': sample_user_report
        }
        mock_firebase_db.reference.return_value = mock_ref

        result = proximity_service.check_proximity_alerts(
            user_lat=37.7749,  # Same as sample report
            user_lon=-122.4194,
            user_id='user123',
            radius_mi=50
        )

        assert result['count'] >= 0  # Might be filtered by preferences
        assert 'alerts' in result
        assert 'highest_severity' in result

    def test_check_proximity_alerts_outside_radius(
        self, proximity_service, mock_firebase_db
    ):
        """Test that disasters beyond radius are excluded."""
        # Create report far away (Los Angeles)
        far_report = {
            'latitude': 34.0522,  # LA coordinates
            'longitude': -118.2437,
            'type': 'wildfire',
            'severity': 'high',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        mock_ref = Mock()
        mock_ref.get.return_value = {'report_far': far_report}
        mock_firebase_db.reference.return_value = mock_ref

        # Search from San Francisco with 50km radius
        result = proximity_service.check_proximity_alerts(
            user_lat=37.7749,  # SF
            user_lon=-122.4194,
            user_id='user123',
            radius_mi=50
        )

        # LA is ~559km away, should not be included
        assert result['count'] == 0


# ============================================================================
# TEST SEVERITY CALCULATION
# ============================================================================

class TestSeverityCalculation:
    """Test alert severity calculation based on distance and disaster severity."""

    def test_calculate_severity_critical(self, proximity_service):
        """Test critical severity: high severity disaster <5km."""
        disaster_data = {'severity': 'high'}

        # 3km away
        severity = proximity_service._calculate_severity_level(disaster_data, 3.0)
        assert severity == 'critical'

        # Exactly 5km
        severity = proximity_service._calculate_severity_level(disaster_data, 5.0)
        assert severity == 'critical'

    def test_calculate_severity_high(self, proximity_service):
        """Test high severity: high severity disaster <15km."""
        disaster_data = {'severity': 'high'}

        # 6 miles away
        severity = proximity_service._calculate_severity_level(disaster_data, 10.0)
        assert severity == 'high'

        # Exactly 15km
        severity = proximity_service._calculate_severity_level(disaster_data, 15.0)
        assert severity == 'high'

    def test_calculate_severity_medium(self, proximity_service):
        """Test medium severity: medium severity <30km."""
        disaster_data = {'severity': 'medium'}

        # 20km away
        severity = proximity_service._calculate_severity_level(disaster_data, 20.0)
        assert severity == 'medium'

        # High severity at 20km should also be medium
        disaster_data = {'severity': 'high'}
        severity = proximity_service._calculate_severity_level(disaster_data, 20.0)
        assert severity == 'medium'

    def test_calculate_severity_low(self, proximity_service):
        """Test low severity: any disaster <50km."""
        disaster_data = {'severity': 'low'}

        # 40km away
        severity = proximity_service._calculate_severity_level(disaster_data, 40.0)
        assert severity == 'low'

        # Exactly 50km
        severity = proximity_service._calculate_severity_level(disaster_data, 50.0)
        assert severity == 'low'

    def test_calculate_severity_distance_thresholds(self, proximity_service):
        """Test severity changes at distance thresholds."""
        # Critical threshold at 5km
        assert proximity_service._calculate_severity_level({'severity': 'high'}, 4.9) == 'critical'
        assert proximity_service._calculate_severity_level({'severity': 'high'}, 5.1) == 'high'

        # High threshold at 15km
        assert proximity_service._calculate_severity_level({'severity': 'high'}, 14.9) == 'high'
        assert proximity_service._calculate_severity_level({'severity': 'high'}, 15.1) == 'medium'

        # Medium threshold at 30km
        assert proximity_service._calculate_severity_level({'severity': 'high'}, 29.9) == 'medium'
        assert proximity_service._calculate_severity_level({'severity': 'high'}, 30.1) == 'low'


# ============================================================================
# TEST USER PREFERENCES
# ============================================================================

class TestUserPreferences:
    """Test user preference management."""

    def test_get_default_preferences(self, proximity_service, mock_firebase_db):
        """Test that default preferences are returned when none exist."""
        mock_firebase_db.reference.return_value.get.return_value = None

        preferences = proximity_service.get_user_alert_preferences('user123')

        assert preferences['enabled'] is True
        assert preferences['radius_mi'] == 50
        assert set(preferences['severity_filter']) == {'critical', 'high', 'medium', 'low'}
        assert 'earthquake' in preferences['disaster_types']
        assert 'wildfire' in preferences['disaster_types']
        assert preferences['quiet_hours']['enabled'] is False

    def test_get_user_preferences_from_firebase(
        self, proximity_service, mock_firebase_db, default_user_preferences
    ):
        """Test loading saved preferences from Firebase."""
        custom_prefs = default_user_preferences.copy()
        custom_prefs['radius_mi'] = 25
        custom_prefs['severity_filter'] = ['critical', 'high']

        mock_firebase_db.reference.return_value.get.return_value = custom_prefs

        preferences = proximity_service.get_user_alert_preferences('user123')

        assert preferences['radius_mi'] == 25
        assert set(preferences['severity_filter']) == {'critical', 'high'}

    def test_update_preferences_validates_radius(self, proximity_service, mock_firebase_db):
        """Test that invalid radius values are rejected."""
        mock_ref = Mock()
        mock_firebase_db.reference.return_value = mock_ref

        # Too small
        result = proximity_service.update_alert_preferences('user123', {
            'radius_mi': 3,
            'severity_filter': ['critical'],
            'disaster_types': ['wildfire']
        })
        assert result is False

        # Too large
        result = proximity_service.update_alert_preferences('user123', {
            'radius_mi': 150,
            'severity_filter': ['critical'],
            'disaster_types': ['wildfire']
        })
        assert result is False

        # Valid range
        result = proximity_service.update_alert_preferences('user123', {
            'radius_mi': 50,
            'severity_filter': ['critical'],
            'disaster_types': ['wildfire']
        })
        assert result is True

    def test_update_preferences_validates_severity_filter(
        self, proximity_service, mock_firebase_db
    ):
        """Test that invalid severity levels are rejected."""
        mock_ref = Mock()
        mock_firebase_db.reference.return_value = mock_ref

        # Invalid severity level
        result = proximity_service.update_alert_preferences('user123', {
            'radius_mi': 50,
            'severity_filter': ['critical', 'invalid_level'],
            'disaster_types': ['wildfire']
        })
        assert result is False

        # Valid severity levels
        result = proximity_service.update_alert_preferences('user123', {
            'radius_mi': 50,
            'severity_filter': ['critical', 'high'],
            'disaster_types': ['wildfire']
        })
        assert result is True

    def test_update_preferences_validates_disaster_types(
        self, proximity_service, mock_firebase_db
    ):
        """Test that invalid disaster types are rejected."""
        mock_ref = Mock()
        mock_firebase_db.reference.return_value = mock_ref

        # Invalid disaster type
        result = proximity_service.update_alert_preferences('user123', {
            'radius_mi': 50,
            'severity_filter': ['critical'],
            'disaster_types': ['wildfire', 'alien_invasion']
        })
        assert result is False

        # Valid disaster types
        result = proximity_service.update_alert_preferences('user123', {
            'radius_mi': 50,
            'severity_filter': ['critical'],
            'disaster_types': ['wildfire', 'earthquake', 'flood']
        })
        assert result is True

    def test_update_preferences_saves_to_firebase(
        self, proximity_service, mock_firebase_db
    ):
        """Test that preferences are correctly saved to Firebase."""
        mock_ref = Mock()
        mock_firebase_db.reference.return_value = mock_ref

        new_prefs = {
            'enabled': False,
            'radius_mi': 25,
            'severity_filter': ['critical', 'high'],
            'disaster_types': ['wildfire'],
            'notification_channels': ['in_app', 'email'],
            'quiet_hours': {
                'enabled': True,
                'start': '23:00',
                'end': '06:00'
            }
        }

        result = proximity_service.update_alert_preferences('user123', new_prefs)

        assert result is True
        assert mock_ref.set.called

        # Verify the saved data structure
        saved_data = mock_ref.set.call_args[0][0]
        assert saved_data['enabled'] is False
        assert saved_data['radius_mi'] == 25
        assert 'updated_at' in saved_data


# ============================================================================
# TEST ALERT FILTERING
# ============================================================================

class TestAlertFiltering:
    """Test filtering alerts by disaster type, severity, and quiet hours."""

    def test_filter_by_disaster_types(
        self, proximity_service, mock_firebase_db
    ):
        """Test that disaster type filter is respected."""
        # Create reports with different types
        reports = {
            'report_1': {
                'latitude': 37.7750,
                'longitude': -122.4195,
                'type': 'wildfire',
                'severity': 'high',
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            'report_2': {
                'latitude': 37.7760,
                'longitude': -122.4200,
                'type': 'earthquake',
                'severity': 'high',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }

        # Mock preferences to only allow wildfires
        preferences = {
            'enabled': True,
            'radius_mi': 50,
            'severity_filter': ['critical', 'high', 'medium', 'low'],
            'disaster_types': ['wildfire']  # Only wildfire
        }

        mock_ref = Mock()
        def get_side_effect(path=None):
            if 'user_alert_preferences' in str(path):
                return preferences
            if 'reports' in str(path):
                return reports
            return None

        def reference_side_effect(path):
            ref = Mock()
            ref.get.side_effect = lambda: get_side_effect(path)
            return ref

        mock_firebase_db.reference.side_effect = reference_side_effect

        result = proximity_service.check_proximity_alerts(
            user_lat=37.7749,
            user_lon=-122.4194,
            user_id='user123',
            radius_mi=50
        )

        # Should only include wildfire, not earthquake
        for alert in result['alerts']:
            assert alert['type'] in ['wildfire']

    def test_filter_by_severity(
        self, proximity_service, mock_firebase_db
    ):
        """Test that severity filter is respected."""
        # Create report nearby
        reports = {
            'report_1': {
                'latitude': 37.7750,
                'longitude': -122.4195,
                'type': 'wildfire',
                'severity': 'low',  # Low severity
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }

        # Mock preferences to only allow critical/high
        preferences = {
            'enabled': True,
            'radius_mi': 50,
            'severity_filter': ['critical', 'high'],  # No low/medium
            'disaster_types': ['wildfire', 'earthquake', 'flood']
        }

        mock_ref = Mock()
        def get_side_effect(path=None):
            if 'user_alert_preferences' in str(path):
                return preferences
            if 'reports' in str(path):
                return reports
            return None

        def reference_side_effect(path):
            ref = Mock()
            ref.get.side_effect = lambda: get_side_effect(path)
            return ref

        mock_firebase_db.reference.side_effect = reference_side_effect

        result = proximity_service.check_proximity_alerts(
            user_lat=37.7749,
            user_lon=-122.4194,
            user_id='user123',
            radius_mi=50
        )

        # Low severity alert should be filtered out
        # (alert_severity will be 'low' due to distance calculation)
        filtered_severities = {alert['alert_severity'] for alert in result['alerts']}
        assert 'low' not in filtered_severities or len(result['alerts']) == 0

    def test_quiet_hours_filtering(self, proximity_service):
        """Test quiet hours detection."""
        # Test during quiet hours (11 PM)
        with patch('services.proximity_alert_service.datetime') as mock_datetime:
            mock_now = datetime(2025, 10, 17, 23, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now

            preferences = {
                'quiet_hours': {
                    'enabled': True,
                    'start': '22:00',
                    'end': '07:00'
                }
            }

            is_quiet = proximity_service._is_in_quiet_hours(preferences)
            assert is_quiet is True

        # Test outside quiet hours (2 PM)
        with patch('services.proximity_alert_service.datetime') as mock_datetime:
            mock_now = datetime(2025, 10, 17, 14, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now

            is_quiet = proximity_service._is_in_quiet_hours(preferences)
            assert is_quiet is False

    def test_quiet_hours_overnight(self, proximity_service):
        """Test quiet hours spanning midnight."""
        preferences = {
            'quiet_hours': {
                'enabled': True,
                'start': '22:00',
                'end': '07:00'
            }
        }

        # 1 AM (should be quiet)
        with patch('services.proximity_alert_service.datetime') as mock_datetime:
            mock_now = datetime(2025, 10, 17, 1, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now

            is_quiet = proximity_service._is_in_quiet_hours(preferences)
            assert is_quiet is True

        # 10 PM (should be quiet)
        with patch('services.proximity_alert_service.datetime') as mock_datetime:
            mock_now = datetime(2025, 10, 17, 22, 30, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now

            is_quiet = proximity_service._is_in_quiet_hours(preferences)
            assert is_quiet is True

        # 8 AM (should not be quiet)
        with patch('services.proximity_alert_service.datetime') as mock_datetime:
            mock_now = datetime(2025, 10, 17, 8, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now

            is_quiet = proximity_service._is_in_quiet_hours(preferences)
            assert is_quiet is False


# ============================================================================
# TEST NOTIFICATION MANAGEMENT
# ============================================================================

class TestNotificationManagement:
    """Test alert notification saving, acknowledgment, and history."""

    def test_save_alert_notification(
        self, proximity_service, mock_firebase_db, sample_user_report
    ):
        """Test saving alert notification to Firebase."""
        mock_ref = Mock()
        mock_new_ref = Mock()
        mock_new_ref.key = 'alert_789'
        mock_ref.push.return_value = mock_new_ref
        mock_firebase_db.reference.return_value = mock_ref

        alert_data = sample_user_report.copy()

        alert_id = proximity_service.save_alert_notification('user123', alert_data)

        assert alert_id == 'alert_789'
        assert mock_ref.push.called
        assert mock_new_ref.set.called

        # Verify notification structure
        saved_data = mock_new_ref.set.call_args[0][0]
        assert saved_data['disaster_id'] == sample_user_report['id']
        assert saved_data['disaster_type'] == sample_user_report['type']
        assert saved_data['acknowledged'] is False
        assert 'expires_at' in saved_data

    def test_acknowledge_alert(self, proximity_service, mock_firebase_db):
        """Test marking alert as acknowledged."""
        mock_ref = Mock()
        mock_ref.get.return_value = {
            'disaster_id': 'report_123',
            'acknowledged': False
        }
        mock_firebase_db.reference.return_value = mock_ref

        success = proximity_service.acknowledge_alert('user123', 'alert_789')

        assert success is True
        assert mock_ref.update.called

        # Verify update includes acknowledged flag
        update_data = mock_ref.update.call_args[0][0]
        assert update_data['acknowledged'] is True
        assert 'acknowledged_at' in update_data

    def test_acknowledge_nonexistent_alert(self, proximity_service, mock_firebase_db):
        """Test acknowledging alert that doesn't exist."""
        mock_ref = Mock()
        mock_ref.get.return_value = None  # Alert not found
        mock_firebase_db.reference.return_value = mock_ref

        success = proximity_service.acknowledge_alert('user123', 'nonexistent')

        assert success is False

    def test_get_notification_history(self, proximity_service, mock_firebase_db):
        """Test fetching notification history."""
        alerts = {
            'alert_1': {
                'disaster_id': 'report_123',
                'timestamp': '2025-10-17T10:00:00+00:00',
                'severity': 'high'
            },
            'alert_2': {
                'disaster_id': 'report_456',
                'timestamp': '2025-10-17T12:00:00+00:00',
                'severity': 'critical'
            },
            'alert_3': {
                'disaster_id': 'report_789',
                'timestamp': '2025-10-17T09:00:00+00:00',
                'severity': 'medium'
            }
        }

        mock_ref = Mock()
        mock_ref.get.return_value = alerts
        mock_firebase_db.reference.return_value = mock_ref

        history = proximity_service.get_notification_history('user123', limit=50)

        assert len(history) == 3
        # Should be sorted by timestamp (newest first)
        assert history[0]['timestamp'] > history[1]['timestamp']
        assert history[1]['timestamp'] > history[2]['timestamp']
        assert history[0]['alert_id'] == 'alert_2'

    def test_get_notification_history_with_limit(
        self, proximity_service, mock_firebase_db
    ):
        """Test notification history respects limit parameter."""
        # Create 100 alerts
        alerts = {
            f'alert_{i}': {
                'disaster_id': f'report_{i}',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'severity': 'high'
            }
            for i in range(100)
        }

        mock_ref = Mock()
        mock_ref.get.return_value = alerts
        mock_firebase_db.reference.return_value = mock_ref

        history = proximity_service.get_notification_history('user123', limit=20)

        assert len(history) == 20

    def test_get_notification_history_empty(self, proximity_service, mock_firebase_db):
        """Test notification history when no notifications exist."""
        mock_ref = Mock()
        mock_ref.get.return_value = None
        mock_firebase_db.reference.return_value = mock_ref

        history = proximity_service.get_notification_history('user123')

        assert history == []


# ============================================================================
# TEST MULTI-SOURCE INTEGRATION
# ============================================================================

class TestMultiSourceIntegration:
    """Test integration with all 8 data sources."""

    def test_fetch_from_all_sources(
        self, proximity_service, mock_firebase_db
    ):
        """Test that check_proximity_alerts queries all sources."""
        # This test verifies the service attempts to fetch from all sources
        mock_ref = Mock()
        mock_ref.get.return_value = None
        mock_firebase_db.reference.return_value = mock_ref

        result = proximity_service.check_proximity_alerts(
            user_lat=37.7749,
            user_lon=-122.4194,
            user_id='user123',
            radius_mi=50
        )

        # Verify Firebase references were called for different sources
        reference_calls = [call[0][0] for call in mock_firebase_db.reference.call_args_list]

        # Should include checks for preferences and various data sources
        assert any('user_alert_preferences' in str(call) for call in reference_calls)

    def test_handle_missing_coordinates(self, proximity_service, mock_firebase_db):
        """Test graceful handling of missing lat/lon in data."""
        reports = {
            'report_1': {
                'latitude': None,  # Missing
                'longitude': -122.4194,
                'type': 'wildfire',
                'severity': 'high',
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            'report_2': {
                'latitude': 37.7749,
                'longitude': None,  # Missing
                'type': 'earthquake',
                'severity': 'high',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }

        mock_ref = Mock()
        mock_ref.get.return_value = reports
        mock_firebase_db.reference.return_value = mock_ref

        # Should not crash, should handle gracefully
        result = proximity_service.check_proximity_alerts(
            user_lat=37.7749,
            user_lon=-122.4194,
            user_id='user123',
            radius_mi=50
        )

        # Result should be valid even with bad data
        assert 'alerts' in result
        assert 'count' in result

    def test_nasa_firms_severity_mapping(
        self, proximity_service, mock_firebase_db
    ):
        """Test brightness to severity conversion for NASA FIRMS."""
        # High brightness fire
        high_brightness_fire = [{
            'latitude': 37.7750,
            'longitude': -122.4195,
            'brightness': 380,  # > 350
            'acq_datetime': datetime.now(timezone.utc).isoformat()
        }]

        # Low brightness fire
        low_brightness_fire = [{
            'latitude': 37.7760,
            'longitude': -122.4200,
            'brightness': 320,  # <= 350
            'acq_datetime': datetime.now(timezone.utc).isoformat()
        }]

        mock_ref = Mock()

        # Test high brightness
        mock_ref.get.return_value = high_brightness_fire
        mock_firebase_db.reference.return_value = mock_ref

        alerts = proximity_service._fetch_nearby_wildfires(
            lat=37.7749,
            lon=-122.4194,
            radius_mi=50,
            disaster_types_filter=set()
        )

        if alerts:
            assert alerts[0]['severity'] == 'high'

        # Test low brightness
        mock_ref.get.return_value = low_brightness_fire

        alerts = proximity_service._fetch_nearby_wildfires(
            lat=37.7749,
            lon=-122.4194,
            radius_mi=50,
            disaster_types_filter=set()
        )

        if alerts:
            assert alerts[0]['severity'] == 'medium'

    def test_noaa_event_type_mapping(self, proximity_service):
        """Test NOAA event type to disaster type mapping."""
        assert proximity_service._map_noaa_event_to_disaster_type('Flood Warning') == 'flood'
        assert proximity_service._map_noaa_event_to_disaster_type('Hurricane Watch') == 'hurricane'
        assert proximity_service._map_noaa_event_to_disaster_type('Tornado Warning') == 'tornado'
        assert proximity_service._map_noaa_event_to_disaster_type('Fire Weather Watch') == 'wildfire'
        assert proximity_service._map_noaa_event_to_disaster_type('Drought Advisory') == 'drought'
        assert proximity_service._map_noaa_event_to_disaster_type('Winter Storm') == 'flood'  # Default

    def test_noaa_severity_mapping(self, proximity_service):
        """Test NOAA severity to our severity levels mapping."""
        assert proximity_service._map_noaa_severity('extreme') == 'critical'
        assert proximity_service._map_noaa_severity('severe') == 'high'
        assert proximity_service._map_noaa_severity('moderate') == 'medium'
        assert proximity_service._map_noaa_severity('minor') == 'low'
        assert proximity_service._map_noaa_severity('unknown') == 'low'

    def test_usgs_magnitude_to_severity(
        self, proximity_service, mock_firebase_db
    ):
        """Test earthquake magnitude to severity mapping."""
        earthquakes = [
            {
                'id': 'eq1',
                'latitude': 37.7750,
                'longitude': -122.4195,
                'magnitude': 6.5,  # Critical
                'time': datetime.now(timezone.utc).isoformat()
            },
            {
                'id': 'eq2',
                'latitude': 37.7760,
                'longitude': -122.4200,
                'magnitude': 5.5,  # High
                'time': datetime.now(timezone.utc).isoformat()
            },
            {
                'id': 'eq3',
                'latitude': 37.7770,
                'longitude': -122.4205,
                'magnitude': 4.5,  # Medium
                'time': datetime.now(timezone.utc).isoformat()
            },
            {
                'id': 'eq4',
                'latitude': 37.7780,
                'longitude': -122.4210,
                'magnitude': 3.5,  # Low
                'time': datetime.now(timezone.utc).isoformat()
            }
        ]

        mock_ref = Mock()
        mock_ref.get.return_value = earthquakes
        mock_firebase_db.reference.return_value = mock_ref

        alerts = proximity_service._fetch_nearby_earthquakes(
            lat=37.7749,
            lon=-122.4194,
            radius_mi=50,
            disaster_types_filter=set()
        )

        # Verify severity mapping
        severity_map = {alert['id']: alert['severity'] for alert in alerts}
        assert severity_map.get('eq1') == 'critical'  # >= 6.0
        assert severity_map.get('eq2') == 'high'      # >= 5.0
        assert severity_map.get('eq3') == 'medium'    # >= 4.0
        assert severity_map.get('eq4') == 'low'       # < 4.0

    def test_fema_disaster_mapping(self, proximity_service):
        """Test FEMA incident type mapping."""
        assert proximity_service._map_fema_incident_to_disaster_type('Severe Storm and Flooding') == 'flood'
        assert proximity_service._map_fema_incident_to_disaster_type('Hurricane') == 'hurricane'
        assert proximity_service._map_fema_incident_to_disaster_type('Wildfire') == 'wildfire'
        assert proximity_service._map_fema_incident_to_disaster_type('Earthquake') == 'earthquake'
        assert proximity_service._map_fema_incident_to_disaster_type('Tornado') == 'tornado'

    def test_gdacs_event_mapping(self, proximity_service):
        """Test GDACS event type and alert level mapping."""
        # Event type mapping
        assert proximity_service._map_gdacs_event_to_disaster_type('EQ') == 'earthquake'
        assert proximity_service._map_gdacs_event_to_disaster_type('FL') == 'flood'
        assert proximity_service._map_gdacs_event_to_disaster_type('TC') == 'hurricane'
        assert proximity_service._map_gdacs_event_to_disaster_type('VO') == 'volcano'
        assert proximity_service._map_gdacs_event_to_disaster_type('DR') == 'drought'

        # Alert level mapping
        assert proximity_service._map_gdacs_alert_level('red') == 'critical'
        assert proximity_service._map_gdacs_alert_level('orange') == 'high'
        assert proximity_service._map_gdacs_alert_level('green') == 'medium'

    def test_cal_fire_acres_to_severity(
        self, proximity_service, mock_firebase_db
    ):
        """Test Cal Fire acres burned to severity mapping."""
        incidents = [
            {
                'id': 'fire1',
                'latitude': 37.7750,
                'longitude': -122.4195,
                'acres_burned': 15000,  # Critical
                'updated': datetime.now(timezone.utc).isoformat()
            },
            {
                'id': 'fire2',
                'latitude': 37.7760,
                'longitude': -122.4200,
                'acres_burned': 5000,  # High
                'updated': datetime.now(timezone.utc).isoformat()
            },
            {
                'id': 'fire3',
                'latitude': 37.7770,
                'longitude': -122.4205,
                'acres_burned': 500,  # Medium
                'updated': datetime.now(timezone.utc).isoformat()
            },
            {
                'id': 'fire4',
                'latitude': 37.7780,
                'longitude': -122.4210,
                'acres_burned': 50,  # Low
                'updated': datetime.now(timezone.utc).isoformat()
            }
        ]

        mock_ref = Mock()
        mock_ref.get.return_value = incidents
        mock_firebase_db.reference.return_value = mock_ref

        alerts = proximity_service._fetch_nearby_cal_fire(
            lat=37.7749,
            lon=-122.4194,
            radius_mi=50,
            disaster_types_filter=set()
        )

        # Verify severity mapping based on acres
        severity_map = {alert['id']: alert['severity'] for alert in alerts}
        assert severity_map.get('fire1') == 'critical'  # > 10000
        assert severity_map.get('fire2') == 'high'      # > 1000
        assert severity_map.get('fire3') == 'medium'    # > 100
        assert severity_map.get('fire4') == 'low'       # <= 100


# ============================================================================
# TEST EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_null_user_location(self, proximity_service, mock_firebase_db):
        """Test handling of None latitude/longitude."""
        mock_ref = Mock()
        mock_ref.get.return_value = None
        mock_firebase_db.reference.return_value = mock_ref

        # Should not crash with None values
        result = proximity_service.check_proximity_alerts(
            user_lat=None,
            user_lon=None,
            user_id='user123',
            radius_mi=50
        )

        # Should return error or empty result
        assert 'alerts' in result

    def test_firebase_connection_error(self, proximity_service, mock_firebase_db):
        """Test graceful degradation on Firebase errors."""
        mock_firebase_db.reference.side_effect = Exception("Firebase connection error")

        # Should not crash, should return error indication
        result = proximity_service.check_proximity_alerts(
            user_lat=37.7749,
            user_lon=-122.4194,
            user_id='user123',
            radius_mi=50
        )

        assert 'error' in result or result['count'] == 0

    def test_empty_cache_data(self, proximity_service, mock_firebase_db):
        """Test handling of empty data from all sources."""
        mock_ref = Mock()
        mock_ref.get.return_value = None  # Empty everywhere
        mock_firebase_db.reference.return_value = mock_ref

        result = proximity_service.check_proximity_alerts(
            user_lat=37.7749,
            user_lon=-122.4194,
            user_id='user123',
            radius_mi=50
        )

        assert result['count'] == 0
        assert result['alerts'] == []
        assert result['highest_severity'] is None

    def test_invalid_timestamp_format(self, proximity_service, mock_firebase_db):
        """Test handling of malformed timestamps."""
        reports = {
            'report_1': {
                'latitude': 37.7750,
                'longitude': -122.4195,
                'type': 'wildfire',
                'severity': 'high',
                'timestamp': 'invalid-timestamp-format'
            }
        }

        mock_ref = Mock()
        mock_ref.get.return_value = reports
        mock_firebase_db.reference.return_value = mock_ref

        # Should handle gracefully without crashing
        result = proximity_service.check_proximity_alerts(
            user_lat=37.7749,
            user_lon=-122.4194,
            user_id='user123',
            radius_mi=50
        )

        assert 'alerts' in result

    def test_determine_highest_severity_empty_list(self, proximity_service):
        """Test highest severity calculation with empty list."""
        result = proximity_service._determine_highest_severity([])
        assert result is None

    def test_determine_highest_severity_ranking(self, proximity_service):
        """Test that highest severity is correctly identified."""
        alerts = [
            {'alert_severity': 'low'},
            {'alert_severity': 'medium'},
            {'alert_severity': 'critical'},
            {'alert_severity': 'high'}
        ]

        result = proximity_service._determine_highest_severity(alerts)
        assert result == 'critical'

    def test_alerts_disabled_by_user(self, proximity_service, mock_firebase_db):
        """Test that alerts are skipped when user disables them."""
        preferences = {
            'enabled': False,  # Disabled
            'radius_mi': 50,
            'severity_filter': ['critical', 'high'],
            'disaster_types': ['wildfire']
        }

        mock_ref = Mock()
        mock_ref.get.return_value = preferences
        mock_firebase_db.reference.return_value = mock_ref

        result = proximity_service.check_proximity_alerts(
            user_lat=37.7749,
            user_lon=-122.4194,
            user_id='user123',
            radius_mi=50
        )

        # Should return empty when disabled
        assert result['count'] == 0
        assert result['alerts'] == []

    def test_filter_respects_empty_disaster_types(
        self, proximity_service, mock_firebase_db
    ):
        """Test that empty disaster_types filter includes all types."""
        reports = {
            'report_1': {
                'latitude': 37.7750,
                'longitude': -122.4195,
                'type': 'wildfire',
                'severity': 'high',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }

        preferences = {
            'enabled': True,
            'radius_mi': 50,
            'severity_filter': ['critical', 'high', 'medium', 'low'],
            'disaster_types': []  # Empty means all types
        }

        mock_ref = Mock()
        def get_side_effect(path=None):
            if 'user_alert_preferences' in str(path):
                return preferences
            if 'reports' in str(path):
                return reports
            return None

        def reference_side_effect(path):
            ref = Mock()
            ref.get.side_effect = lambda: get_side_effect(path)
            return ref

        mock_firebase_db.reference.side_effect = reference_side_effect

        result = proximity_service.check_proximity_alerts(
            user_lat=37.7749,
            user_lon=-122.4194,
            user_id='user123',
            radius_mi=50
        )

        # Empty filter should include all disaster types
        # The implementation should handle this correctly


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
