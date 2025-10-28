"""
Comprehensive edge case testing for route calculation with disaster avoidance.

Tests the critical feature: users inside disaster zones can route OUT.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from services.route_calculation_service import RouteCalculationService
from shapely.geometry import Point
import math


class TestBasicRouteCalculation:
    """Test basic route calculation functionality"""

    @patch('requests.post')
    def test_route_without_any_disasters(self, mock_post):
        """Test route calculation when no disasters exist"""
        # Mock database with no disasters
        db = MagicMock()
        db.reference.return_value.get.return_value = {}

        service = RouteCalculationService(api_key='test_key', db=db)

        # Mock ORS API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'features': [{
                'properties': {
                    'summary': {'distance': 100000, 'duration': 3600},
                    'segments': [{'steps': []}]
                },
                'geometry': {'coordinates': [[0, 0], [1, 1]]}
            }]
        }

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 37.8044, 'lon': -122.2711}

        routes = service.calculate_routes(origin, destination, avoid_disasters=True)

        # Should get routes even with no disasters
        assert len(routes) >= 1
        # No avoidance polygons should be sent to ORS
        call_args = mock_post.call_args[1]['json']
        assert 'options' not in call_args or 'avoid_polygons' not in call_args.get('options', {})


class TestUserAtDisasterCenter:
    """Test when user is exactly at the center of a disaster"""

    def test_user_at_exact_disaster_coordinates(self):
        """User at exact same coordinates as disaster epicenter"""
        db = MagicMock()
        now = datetime.now(timezone.utc)

        # Disaster at exact coordinates
        disaster = {
            'id': 'wildfire_center',
            'type': 'wildfire',
            'severity': 'critical',
            'latitude': 34.0522,
            'longitude': -118.2437,
            'timestamp': now.isoformat(),
            'brightness': 400
        }

        def mock_reference(path):
            ref = MagicMock()
            if path == 'reports':
                ref.get.return_value = {'wildfire_center': disaster}
            else:
                ref.get.return_value = [] if 'data' in path else None
            return ref

        db.reference.side_effect = mock_reference

        service = RouteCalculationService(api_key='test_key', db=db)

        # User at EXACT disaster center
        origin = {'lat': 34.0522, 'lon': -118.2437}
        destination = {'lat': 34.1522, 'lon': -118.3437}

        polygons, disasters = service.get_disaster_polygons(origin, destination)

        # Disaster should be fetched
        assert len(disasters) == 1
        # But polygon should be EXCLUDED (user is inside)
        assert len(polygons) == 0


class TestUserAtBufferEdge:
    """Test when user is at the edge of disaster buffer zone"""

    def test_user_at_5_mile_buffer_edge(self):
        """User exactly at edge of 5-mile critical disaster buffer"""
        db = MagicMock()
        now = datetime.now(timezone.utc)

        # Critical disaster (5-mile buffer)
        disaster = {
            'id': 'wildfire_1',
            'type': 'wildfire',
            'severity': 'critical',
            'latitude': 34.0,
            'longitude': -118.0,
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

        # Calculate point ~4.9 miles away (just INSIDE buffer)
        # Approximately 0.07 degrees latitude ~= 4.9 miles
        origin_inside = {'lat': 34.0 + 0.07, 'lon': -118.0}
        destination = {'lat': 34.2, 'lon': -118.2}

        polygons_inside, _ = service.get_disaster_polygons(origin_inside, destination)

        # User is INSIDE buffer, so polygon excluded
        assert len(polygons_inside) == 0

    def test_user_just_outside_buffer(self):
        """User just outside the disaster buffer zone"""
        db = MagicMock()
        now = datetime.now(timezone.utc)

        # Critical disaster (5-mile buffer)
        disaster = {
            'id': 'wildfire_1',
            'type': 'wildfire',
            'severity': 'critical',
            'latitude': 34.0,
            'longitude': -118.0,
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

        # Calculate point ~5.2 miles away (just OUTSIDE buffer)
        # Approximately 0.075 degrees latitude ~= 5.2 miles
        origin_outside = {'lat': 34.0 + 0.075, 'lon': -118.0}
        destination = {'lat': 34.2, 'lon': -118.2}

        polygons_outside, _ = service.get_disaster_polygons(origin_outside, destination)

        # User is OUTSIDE buffer, so polygon included
        assert len(polygons_outside) == 1


class TestMultipleDisasters:
    """Test scenarios with multiple disasters"""

    def test_user_inside_one_outside_another(self):
        """User inside one disaster zone but outside another"""
        db = MagicMock()
        now = datetime.now(timezone.utc)

        disasters = {
            'wildfire_at_origin': {
                'id': 'wildfire_at_origin',
                'type': 'wildfire',
                'severity': 'critical',
                'latitude': 34.0,
                'longitude': -118.0,
                'timestamp': now.isoformat(),
                'brightness': 400
            },
            'earthquake_far': {
                'id': 'earthquake_far',
                'type': 'earthquake',
                'severity': 'high',
                'latitude': 34.3,
                'longitude': -118.5,
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

        # User at wildfire location, far from earthquake
        origin = {'lat': 34.0, 'lon': -118.0}
        destination = {'lat': 34.5, 'lon': -118.7}

        polygons, disasters_list = service.get_disaster_polygons(origin, destination)

        # 2 disasters fetched
        assert len(disasters_list) == 2
        # Only 1 polygon (earthquake, wildfire excluded)
        assert len(polygons) == 1

    def test_user_between_two_disasters(self):
        """User positioned between two disasters, outside both buffers"""
        db = MagicMock()
        now = datetime.now(timezone.utc)

        # Place disasters along the route path, but far enough from origin
        # Critical wildfire has 5-mile buffer, high earthquake has 3-mile buffer
        disasters = {
            'wildfire_north': {
                'id': 'wildfire_north',
                'type': 'wildfire',
                'severity': 'critical',
                'latitude': 34.15,  # ~10 miles north of origin
                'longitude': -118.20,
                'timestamp': now.isoformat(),
                'brightness': 400
            },
            'earthquake_south': {
                'id': 'earthquake_south',
                'type': 'earthquake',
                'severity': 'high',
                'latitude': 34.25,  # ~17 miles north of origin
                'longitude': -118.18,
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

        # User starts south of both disasters
        origin = {'lat': 34.05, 'lon': -118.19}  # Well south of both
        destination = {'lat': 34.30, 'lon': -118.19}  # North of both

        polygons, disasters_list = service.get_disaster_polygons(origin, destination)

        # 2 disasters fetched (both within bounding box)
        assert len(disasters_list) == 2
        # 2 polygons (both included, user outside both disaster buffers)
        assert len(polygons) == 2


class TestSeverityLevels:
    """Test different disaster severity levels and buffer sizes"""

    def test_buffer_sizes_vary_by_severity(self):
        """Verify different severity levels create different buffer sizes"""
        service = RouteCalculationService(api_key='test_key', db=MagicMock())

        # Test severity to buffer radius mapping
        assert service._get_buffer_radius({'severity': 'critical'}) == 5
        assert service._get_buffer_radius({'severity': 'high'}) == 3
        assert service._get_buffer_radius({'severity': 'medium'}) == 2
        assert service._get_buffer_radius({'severity': 'low'}) == 1
        assert service._get_buffer_radius({'severity': 'unknown'}) == 1  # Default

    def test_user_inside_low_severity_outside_high_severity(self):
        """User inside low-severity (1mi) buffer, outside high-severity (3mi) buffer"""
        db = MagicMock()
        now = datetime.now(timezone.utc)

        # Low severity disaster very close to origin
        disaster_low = {
            'id': 'flood_low',
            'type': 'flood',
            'severity': 'low',
            'latitude': 34.01,  # ~0.7 miles from origin
            'longitude': -118.01,
            'timestamp': now.isoformat()
        }

        def mock_reference(path):
            ref = MagicMock()
            if path == 'reports':
                ref.get.return_value = {'flood_low': disaster_low}
            else:
                ref.get.return_value = [] if 'data' in path else None
            return ref

        db.reference.side_effect = mock_reference

        service = RouteCalculationService(api_key='test_key', db=db)

        # Origin close enough to be in 1-mile low-severity buffer
        origin = {'lat': 34.0, 'lon': -118.0}
        destination = {'lat': 34.2, 'lon': -118.2}

        polygons, _ = service.get_disaster_polygons(origin, destination)

        # Should be excluded (user within 1-mile buffer)
        assert len(polygons) == 0


class TestPolygonGeometry:
    """Test polygon creation and geometry validation"""

    def test_circular_polygon_created_correctly(self):
        """Verify disaster buffers create circular polygons"""
        service = RouteCalculationService(api_key='test_key', db=MagicMock())

        lat, lon = 34.0, -118.0
        radius_mi = 5.0

        polygon = service._create_circular_polygon(lat, lon, radius_mi)

        # Polygon should be valid
        assert polygon.is_valid

        # Center point should be inside polygon
        center = Point(lon, lat)
        assert polygon.contains(center)

        # Polygon should have ~32 points (approximation of circle)
        # Exterior includes closing point, so 33 total
        assert len(polygon.exterior.coords) == 33

    def test_polygon_containment_logic(self):
        """Test Point.contains() logic for origin exclusion"""
        service = RouteCalculationService(api_key='test_key', db=MagicMock())

        disaster_lat, disaster_lon = 34.0, -118.0
        buffer_radius = 5.0

        polygon = service._create_circular_polygon(disaster_lat, disaster_lon, buffer_radius)

        # Point at center - INSIDE
        center_point = Point(disaster_lon, disaster_lat)
        assert polygon.contains(center_point)

        # Point 2 miles away - INSIDE (within 5-mile buffer)
        nearby_point = Point(disaster_lon + 0.03, disaster_lat + 0.03)
        assert polygon.contains(nearby_point)

        # Point 10 miles away - OUTSIDE
        far_point = Point(disaster_lon + 0.15, disaster_lat + 0.15)
        assert not polygon.contains(far_point)


class TestCoordinateValidation:
    """Test coordinate validation edge cases"""

    def test_invalid_coordinates_rejected(self):
        """Routes with invalid coordinates should be rejected"""
        service = RouteCalculationService(api_key='test_key', db=MagicMock())

        # Invalid latitude (> 90)
        invalid_origin = {'lat': 95.0, 'lon': -118.0}
        valid_dest = {'lat': 34.0, 'lon': -118.0}

        routes = service.calculate_routes(invalid_origin, valid_dest)
        assert len(routes) == 0

        # Invalid longitude (> 180)
        valid_origin = {'lat': 34.0, 'lon': -118.0}
        invalid_dest = {'lat': 34.0, 'lon': 200.0}

        routes = service.calculate_routes(valid_origin, invalid_dest)
        assert len(routes) == 0


class TestBoundingBox:
    """Test bounding box calculation for disaster filtering"""

    def test_disasters_outside_bounding_box_excluded(self):
        """Disasters far from route should not be fetched"""
        db = MagicMock()
        now = datetime.now(timezone.utc)

        # Disaster very far from route
        disaster_far = {
            'id': 'wildfire_alaska',
            'type': 'wildfire',
            'severity': 'critical',
            'latitude': 61.0,  # Alaska
            'longitude': -149.0,
            'timestamp': now.isoformat(),
            'brightness': 400
        }

        def mock_reference(path):
            ref = MagicMock()
            if path == 'reports':
                ref.get.return_value = {'wildfire_alaska': disaster_far}
            else:
                ref.get.return_value = [] if 'data' in path else None
            return ref

        db.reference.side_effect = mock_reference

        service = RouteCalculationService(api_key='test_key', db=db)

        # Route in Los Angeles
        origin = {'lat': 34.0, 'lon': -118.0}
        destination = {'lat': 34.1, 'lon': -118.1}

        polygons, disasters = service.get_disaster_polygons(origin, destination)

        # Alaska disaster should be filtered out (outside bounding box)
        assert len(disasters) == 0
        assert len(polygons) == 0


class TestRealWorldScenarios:
    """Test real-world disaster evacuation scenarios"""

    def test_wildfire_evacuation_scenario(self):
        """User needs to evacuate from wildfire zone"""
        db = MagicMock()
        now = datetime.now(timezone.utc)

        # Large wildfire (critical severity, 5-mile buffer)
        wildfire = {
            'id': 'woolsey_fire',
            'type': 'wildfire',
            'severity': 'critical',
            'latitude': 34.1000,
            'longitude': -118.8000,
            'timestamp': now.isoformat(),
            'brightness': 420,
            'source': 'cal_fire'
        }

        def mock_reference(path):
            ref = MagicMock()
            if path == 'reports':
                ref.get.return_value = {}
            elif path == 'public_data_cache/cal_fire_incidents/data':
                ref.get.return_value = [wildfire]
            else:
                ref.get.return_value = [] if 'data' in path else None
            return ref

        db.reference.side_effect = mock_reference

        service = RouteCalculationService(api_key='test_key', db=db)

        # User inside wildfire zone
        origin = {'lat': 34.1000, 'lon': -118.8000}
        # Evacuating to Santa Monica (safe zone)
        destination = {'lat': 34.0195, 'lon': -118.4912}

        polygons, disasters = service.get_disaster_polygons(origin, destination)

        # Wildfire fetched
        assert len(disasters) == 1
        # But excluded from avoidance (user needs to escape)
        assert len(polygons) == 0

    def test_earthquake_aftermath_navigation(self):
        """User navigating through earthquake-damaged area"""
        db = MagicMock()
        now = datetime.now(timezone.utc)

        # Major earthquake with 3-mile danger zone
        earthquake = {
            'id': 'northridge_quake',
            'type': 'earthquake',
            'severity': 'high',
            'latitude': 34.2130,
            'longitude': -118.5366,
            'timestamp': now.isoformat(),
            'magnitude': 6.7,
            'source': 'usgs'
        }

        def mock_reference(path):
            ref = MagicMock()
            if path == 'public_data_cache/usgs_earthquakes/data':
                ref.get.return_value = [earthquake]
            else:
                ref.get.return_value = {} if path == 'reports' else ([] if 'data' in path else None)
            return ref

        db.reference.side_effect = mock_reference

        service = RouteCalculationService(api_key='test_key', db=db)

        # User at epicenter
        origin_at_epicenter = {'lat': 34.2130, 'lon': -118.5366}
        destination = {'lat': 34.0522, 'lon': -118.2437}  # Downtown LA

        polygons_at_epicenter, disasters = service.get_disaster_polygons(
            origin_at_epicenter, destination
        )

        # Earthquake excluded (user at epicenter)
        assert len(disasters) == 1
        assert len(polygons_at_epicenter) == 0

        # User 5 miles away (outside 3-mile buffer)
        origin_outside = {'lat': 34.2630, 'lon': -118.5366}

        polygons_outside, _ = service.get_disaster_polygons(origin_outside, destination)

        # Earthquake included (user outside buffer)
        assert len(polygons_outside) == 1
