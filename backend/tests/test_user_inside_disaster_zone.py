"""
Tests for route calculation when user starts inside a disaster zone.

Critical edge case: Users already in disaster zones need to route OUT,
so those disasters must be excluded from avoidance polygons.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from services.route_calculation_service import RouteCalculationService


@pytest.fixture
def mock_db_with_disasters():
    """Mock Firebase database with disasters at specific locations"""
    db = MagicMock()
    now = datetime.now(timezone.utc)

    # Disaster 1: Wildfire at (34.05, -118.25) with 5-mile radius (critical)
    # User will be INSIDE this zone at (34.05, -118.25)
    disaster_1 = {
        'id': 'wildfire_at_origin',
        'type': 'wildfire',
        'severity': 'critical',
        'latitude': 34.05,
        'longitude': -118.25,
        'timestamp': now.isoformat(),
        'brightness': 400  # High brightness = critical
    }

    # Disaster 2: Earthquake at (34.10, -118.30) with 3-mile radius (high)
    # User will be OUTSIDE this zone
    disaster_2 = {
        'id': 'earthquake_nearby',
        'type': 'earthquake',
        'severity': 'high',
        'latitude': 34.10,
        'longitude': -118.30,
        'timestamp': now.isoformat(),
        'magnitude': 6.5  # High magnitude = high severity
    }

    # Mock database responses
    def mock_reference(path):
        ref = MagicMock()
        if path == 'reports':
            ref.get.return_value = {
                'wildfire_at_origin': disaster_1
            }
        elif path == 'public_data_cache/wildfires/data':
            ref.get.return_value = []
        elif path == 'public_data_cache/weather_alerts/data':
            ref.get.return_value = []
        elif path == 'public_data_cache/usgs_earthquakes/data':
            ref.get.return_value = [disaster_2]
        elif path == 'public_data_cache/cal_fire_incidents/data':
            ref.get.return_value = []
        else:
            ref.get.return_value = None
        return ref

    db.reference.side_effect = mock_reference
    return db


def test_user_inside_disaster_zone_excludes_that_disaster(mock_db_with_disasters):
    """
    Test that disasters containing the origin point are excluded from avoidance.

    User at (34.05, -118.25) is INSIDE wildfire zone (same coordinates, 5-mile buffer).
    The wildfire should be excluded from avoidance polygons so user can route OUT.
    The nearby earthquake should still be included in avoidance.
    """
    service = RouteCalculationService(
        api_key='test_key',
        db=mock_db_with_disasters
    )

    # User is at the EXACT center of wildfire disaster zone
    origin = {'lat': 34.05, 'lon': -118.25}

    # Destination is 10 miles away, outside all disaster zones
    destination = {'lat': 34.20, 'lon': -118.40}

    # Get disaster polygons
    polygons, disasters = service.get_disaster_polygons(origin, destination)

    # Should have 2 disasters total (wildfire + earthquake)
    assert len(disasters) == 2

    # Should only have 1 polygon (earthquake)
    # Wildfire polygon should be excluded because user is inside it
    assert len(polygons) == 1


def test_user_slightly_inside_disaster_zone():
    """
    Test that disasters containing the origin point are excluded even if user
    is near the edge of the disaster zone (within buffer radius).
    """
    db = MagicMock()
    now = datetime.now(timezone.utc)

    # Disaster at (34.05, -118.25) with 5-mile critical buffer
    disaster = {
        'id': 'wildfire_1',
        'type': 'wildfire',
        'severity': 'critical',
        'latitude': 34.05,
        'longitude': -118.25,
        'timestamp': now.isoformat(),
        'brightness': 400
    }

    def mock_reference(path):
        ref = MagicMock()
        if path == 'reports':
            ref.get.return_value = {'wildfire_1': disaster}
        else:
            ref.get.return_value = [] if 'data' in path else None
        return ref

    db.reference.side_effect = mock_reference

    service = RouteCalculationService(api_key='test_key', db=db)

    # User is 2 miles away from disaster center (well within 5-mile buffer)
    # Approximate: 0.03 degrees ~= 2 miles
    origin = {'lat': 34.05 + 0.03, 'lon': -118.25}
    destination = {'lat': 34.20, 'lon': -118.40}

    polygons, disasters = service.get_disaster_polygons(origin, destination)

    # Should have 1 disaster
    assert len(disasters) == 1

    # Should have 0 polygons (user is inside the only disaster)
    assert len(polygons) == 0


def test_user_outside_all_disasters():
    """
    Test that all disasters are included when user is outside all zones.
    This is the normal case - no disasters should be excluded.
    """
    db = MagicMock()
    now = datetime.now(timezone.utc)

    # Disasters along the route but user is outside their buffer zones
    disasters = {
        'wildfire_1': {
            'id': 'wildfire_1',
            'type': 'wildfire',
            'severity': 'critical',
            'latitude': 34.15,  # Along the route
            'longitude': -118.35,
            'timestamp': now.isoformat(),
            'brightness': 400
        },
        'earthquake_1': {
            'id': 'earthquake_1',
            'type': 'earthquake',
            'severity': 'high',
            'latitude': 34.18,  # Also along the route
            'longitude': -118.38,
            'timestamp': now.isoformat(),
            'magnitude': 6.5
        }
    }

    def mock_reference(path):
        ref = MagicMock()
        if path == 'reports':
            ref.get.return_value = disasters
        elif path == 'public_data_cache/usgs_earthquakes/data':
            ref.get.return_value = []
        else:
            ref.get.return_value = [] if 'data' in path else None
        return ref

    db.reference.side_effect = mock_reference

    service = RouteCalculationService(api_key='test_key', db=db)

    # User is traveling through area with disasters but starting outside all zones
    origin = {'lat': 34.05, 'lon': -118.25}  # Outside disaster zones
    destination = {'lat': 34.25, 'lon': -118.45}  # Destination also outside

    polygons, disasters_list = service.get_disaster_polygons(origin, destination)

    # Should have 2 disasters
    assert len(disasters_list) == 2

    # Should have 2 polygons (both disasters included since user is outside them)
    assert len(polygons) == 2


def test_multiple_disasters_at_origin():
    """
    Test that multiple overlapping disasters at origin are all excluded.
    """
    db = MagicMock()
    now = datetime.now(timezone.utc)

    # Two disasters at the SAME location (origin)
    disasters = {
        'wildfire_1': {
            'id': 'wildfire_1',
            'type': 'wildfire',
            'severity': 'critical',
            'latitude': 34.05,
            'longitude': -118.25,
            'timestamp': now.isoformat(),
            'brightness': 400
        },
        'earthquake_1': {
            'id': 'earthquake_1',
            'type': 'earthquake',
            'severity': 'high',
            'latitude': 34.05,
            'longitude': -118.25,
            'timestamp': now.isoformat(),
            'magnitude': 6.5
        }
    }

    def mock_reference(path):
        ref = MagicMock()
        if path == 'reports':
            ref.get.return_value = disasters
        else:
            ref.get.return_value = [] if 'data' in path else None
        return ref

    db.reference.side_effect = mock_reference

    service = RouteCalculationService(api_key='test_key', db=db)

    # User is at the exact center of both disasters
    origin = {'lat': 34.05, 'lon': -118.25}
    destination = {'lat': 34.20, 'lon': -118.40}

    polygons, disasters_list = service.get_disaster_polygons(origin, destination)

    # Should have 2 disasters
    assert len(disasters_list) == 2

    # Should have 0 polygons (both disasters excluded)
    assert len(polygons) == 0
