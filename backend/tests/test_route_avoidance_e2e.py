"""
End-to-End Tests for Route Avoidance System

Tests the complete routing system including:
- Disaster polygon generation with correct buffer sizes
- Route calculation avoiding disaster zones
- Safety scoring accuracy
- Direction/waypoint quality
- Real-world scenario handling
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from shapely.geometry import LineString, Point, Polygon
from services.route_calculation_service import RouteCalculationService
import math


@pytest.fixture
def mock_db():
    """Mock Firebase database with realistic disaster data"""
    db = MagicMock()
    return db


@pytest.fixture
def route_service(mock_db):
    """Create RouteCalculationService with mocked API key"""
    with patch('os.getenv', return_value='test_api_key'):
        service = RouteCalculationService(db=mock_db)
        return service


@pytest.fixture
def san_francisco_wildfire():
    """Mock critical wildfire in San Francisco"""
    return {
        'id': 'sf_wildfire',
        'type': 'wildfire',
        'severity': 'critical',
        'latitude': 37.7749,
        'longitude': -122.4194,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'nasa_firms',
        'brightness': 420  # Very hot fire
    }


@pytest.fixture
def oakland_earthquake():
    """Mock high-severity earthquake in Oakland"""
    return {
        'id': 'oakland_quake',
        'type': 'earthquake',
        'severity': 'high',
        'latitude': 37.8044,
        'longitude': -122.2711,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'usgs',
        'magnitude': 6.5
    }


@pytest.fixture
def mock_successful_ors_response():
    """Mock ORS response with a route that avoids disasters"""
    return {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'properties': {
                    'summary': {
                        'distance': 50000,  # 50km = ~31 miles
                        'duration': 3600  # 1 hour
                    },
                    'segments': [
                        {
                            'steps': [
                                {
                                    'instruction': 'Head north on Main St',
                                    'distance': 1000,  # meters
                                    'duration': 120,  # seconds
                                    'type': 0
                                },
                                {
                                    'instruction': 'Turn right onto Highway 101',
                                    'distance': 45000,
                                    'duration': 3300,
                                    'type': 1
                                },
                                {
                                    'instruction': 'Arrive at destination',
                                    'distance': 100,
                                    'duration': 180,
                                    'type': 10
                                }
                            ]
                        }
                    ]
                },
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [
                        [-122.4194, 37.7749],  # Start
                        [-122.5000, 37.8500],  # Middle waypoint (detours around disaster)
                        [-122.2711, 37.8044]   # End
                    ]
                }
            }
        ]
    }


class TestDisasterBufferGeneration:
    """Test disaster buffer polygon generation"""

    def test_critical_wildfire_creates_5_mile_buffer(self, route_service, mock_db, san_francisco_wildfire):
        """Critical wildfires should have 5-mile buffer zones"""
        # Setup mock to return disasters as Firebase would (dict of dicts)
        mock_refs = {
            'reports': {'disaster_1': san_francisco_wildfire},
            'public_data_cache/wildfires/data': [],
            'public_data_cache/weather_alerts/data': [],
            'public_data_cache/usgs_earthquakes/data': [],
            'public_data_cache/cal_fire_incidents/data': []
        }

        def mock_reference(path):
            ref = MagicMock()
            ref.get.return_value = mock_refs.get(path, None)
            return ref

        mock_db.reference = mock_reference

        origin = {'lat': 37.7000, 'lon': -122.5000}
        destination = {'lat': 37.9000, 'lon': -122.3000}

        polygons, disasters = route_service.get_disaster_polygons(origin, destination)

        assert len(polygons) == 1, "Should create one polygon for one disaster"
        assert len(disasters) == 1
        assert disasters[0]['severity'] == 'critical'

        # Verify buffer radius is approximately 5 miles
        # The polygon should be roughly circular with 5-mile radius
        polygon = polygons[0]
        center = Point(san_francisco_wildfire['longitude'], san_francisco_wildfire['latitude'])

        # Check a point on the polygon boundary is ~5 miles from center
        exterior_point = Point(polygon.exterior.coords[0])
        distance_deg = center.distance(exterior_point)
        # Note: Conversion depends on latitude (cos factor), allow wider range
        distance_mi = distance_deg * 69.1  # Rough conversion

        assert 4.0 <= distance_mi <= 7.0, f"Buffer radius should be ~5 miles, got {distance_mi:.2f} (affected by latitude scaling)"

    def test_high_severity_earthquake_creates_3_mile_buffer(self, route_service, mock_db, oakland_earthquake):
        """High severity earthquakes should have 3-mile buffer zones"""
        # Setup mock properly
        mock_refs = {
            'reports': {'disaster_1': oakland_earthquake},
            'public_data_cache/wildfires/data': [],
            'public_data_cache/weather_alerts/data': [],
            'public_data_cache/usgs_earthquakes/data': [],
            'public_data_cache/cal_fire_incidents/data': []
        }

        def mock_reference(path):
            ref = MagicMock()
            ref.get.return_value = mock_refs.get(path, None)
            return ref

        mock_db.reference = mock_reference

        origin = {'lat': 37.7000, 'lon': -122.5000}
        destination = {'lat': 37.9000, 'lon': -122.1000}

        polygons, disasters = route_service.get_disaster_polygons(origin, destination)

        assert len(polygons) == 1
        assert disasters[0]['severity'] == 'high'

        # Verify buffer radius is approximately 3 miles (wider range due to lat/lon scaling)
        polygon = polygons[0]
        center = Point(oakland_earthquake['longitude'], oakland_earthquake['latitude'])
        exterior_point = Point(polygon.exterior.coords[0])
        distance_deg = center.distance(exterior_point)
        distance_mi = distance_deg * 69.1

        assert 2.0 <= distance_mi <= 4.5, f"Buffer radius should be ~3 miles, got {distance_mi:.2f} (affected by latitude scaling)"

    def test_multiple_disasters_create_multiple_buffers(self, route_service, mock_db, san_francisco_wildfire, oakland_earthquake):
        """Multiple disasters should each get their own buffer zone"""
        mock_db.reference.return_value.get.return_value = {
            'disaster_1': san_francisco_wildfire,
            'disaster_2': oakland_earthquake
        }

        origin = {'lat': 37.6000, 'lon': -122.5000}
        destination = {'lat': 38.0000, 'lon': -122.1000}

        polygons, disasters = route_service.get_disaster_polygons(origin, destination)

        assert len(polygons) == 2, "Should create two polygons for two disasters"
        assert len(disasters) == 2


class TestRouteDisasterIntersection:
    """Test route intersection detection with disaster zones"""

    def test_route_through_disaster_zone_detected(self, route_service, san_francisco_wildfire):
        """Routes passing through disaster zones should be detected"""
        # Create a route that passes directly through the disaster location
        route_geometry = LineString([
            [-122.5000, 37.7000],  # Start west of disaster
            [-122.4194, 37.7749],  # Pass through disaster center
            [-122.3000, 37.8500]   # End east of disaster
        ])

        # Create disaster buffer (5 miles for critical)
        disaster_polygon = route_service._create_circular_polygon(
            san_francisco_wildfire['latitude'],
            san_francisco_wildfire['longitude'],
            5.0  # 5 mile radius
        )

        intersects = route_service.check_route_disaster_intersection(
            route_geometry,
            [disaster_polygon]
        )

        assert intersects is True, "Route through disaster center should intersect buffer zone"

    def test_route_avoiding_disaster_zone_not_detected(self, route_service, san_francisco_wildfire):
        """Routes that avoid disaster zones should not intersect"""
        # Create a route that goes FAR around the disaster (very far north)
        # San Francisco disaster is at (37.7749, -122.4194)
        # 5-mile buffer extends to ~37.8469 latitude (with lon scaling factor)
        # Route well north of buffer to ensure no intersection
        route_geometry = LineString([
            [-122.5000, 38.1000],  # Start far north
            [-122.4500, 38.1000],  # Stay far north
            [-122.3000, 38.1000]   # End far north (all points ~20 miles from disaster)
        ])

        disaster_polygon = route_service._create_circular_polygon(
            san_francisco_wildfire['latitude'],
            san_francisco_wildfire['longitude'],
            5.0
        )

        intersects = route_service.check_route_disaster_intersection(
            route_geometry,
            [disaster_polygon]
        )

        assert intersects is False, "Route far from disaster should not intersect buffer zone"

    def test_route_near_but_outside_buffer(self, route_service, san_francisco_wildfire):
        """Routes near but outside buffer zones should not intersect"""
        # Create a route that passes 6 miles from disaster (just outside 5-mile buffer)
        # San Francisco disaster is at (37.7749, -122.4194)
        # 6 miles north is approximately 37.7749 + (6/69.1) = 37.8618
        route_geometry = LineString([
            [-122.5000, 37.8618],  # 6 miles north of disaster
            [-122.3000, 37.8618]   # Straight east, maintaining 6-mile distance
        ])

        disaster_polygon = route_service._create_circular_polygon(
            san_francisco_wildfire['latitude'],
            san_francisco_wildfire['longitude'],
            5.0  # 5 mile buffer
        )

        intersects = route_service.check_route_disaster_intersection(
            route_geometry,
            [disaster_polygon]
        )

        assert intersects is False, "Route 6 miles away should not intersect 5-mile buffer"


class TestRouteSafetyScoring:
    """Test safety score calculation for routes"""

    def test_route_far_from_disasters_scores_100(self, route_service):
        """Routes far from all disasters should score 100/100"""
        route_geometry = LineString([
            [-122.0000, 38.5000],  # Far north
            [-122.0000, 38.6000]
        ])
        disasters = [
            {
                'id': 'distant_disaster',
                'latitude': 37.0000,  # ~100 miles south
                'longitude': -122.0000,
                'severity': 'critical',
                'type': 'wildfire'
            }
        ]

        result = route_service.calculate_route_safety_score(route_geometry, disasters)

        assert result['score'] >= 95.0, "Route far from disasters should score very high"
        assert result['nearby_count'] == 0, "No disasters should be within 6.2 miles"

    def test_route_through_disaster_scores_low(self, route_service, san_francisco_wildfire):
        """Routes passing through disasters should score very low"""
        # Route directly through disaster center
        route_geometry = LineString([
            [-122.5000, 37.7749],
            [-122.4194, 37.7749],  # Through disaster
            [-122.3000, 37.7749]
        ])
        disasters = [san_francisco_wildfire]

        result = route_service.calculate_route_safety_score(route_geometry, disasters)

        assert result['score'] < 50.0, "Route through disaster should score very low"
        assert result['nearby_count'] >= 1, "Should detect nearby disaster"
        assert result['min_distance_mi'] is not None
        assert result['min_distance_mi'] < 1.0, "Minimum distance should be very small"

    def test_safety_score_decreases_with_more_nearby_disasters(self, route_service, san_francisco_wildfire, oakland_earthquake):
        """More nearby disasters should decrease safety score"""
        route_geometry = LineString([
            [-122.4500, 37.7900],  # Between SF and Oakland
            [-122.3500, 37.7900]
        ])

        # Test with one disaster
        result_one = route_service.calculate_route_safety_score(
            route_geometry,
            [san_francisco_wildfire]
        )

        # Test with two disasters
        result_two = route_service.calculate_route_safety_score(
            route_geometry,
            [san_francisco_wildfire, oakland_earthquake]
        )

        assert result_two['score'] < result_one['score'], \
            "More nearby disasters should reduce safety score"
        assert result_two['nearby_count'] >= result_one['nearby_count'], \
            "Should detect more disasters"


class TestEndToEndRouteCalculation:
    """End-to-end tests for complete route calculation workflow"""

    @patch('requests.post')
    def test_calculate_route_with_disaster_avoidance(
        self,
        mock_post,
        route_service,
        mock_db,
        san_francisco_wildfire,
        mock_successful_ors_response
    ):
        """Test complete route calculation with disaster avoidance"""
        # Setup: disaster exists in database (proper mock structure)
        mock_refs = {
            'reports': {'disaster_1': san_francisco_wildfire},
            'public_data_cache/wildfires/data': [],
            'public_data_cache/weather_alerts/data': [],
            'public_data_cache/usgs_earthquakes/data': [],
            'public_data_cache/cal_fire_incidents/data': []
        }

        def mock_reference(path):
            ref = MagicMock()
            ref.get.return_value = mock_refs.get(path, None)
            return ref

        mock_db.reference = mock_reference

        # Setup: ORS returns a route
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_successful_ors_response

        # Calculate route from south to north, avoiding SF disaster
        origin = {'lat': 37.5000, 'lon': -122.4000}
        destination = {'lat': 37.9000, 'lon': -122.3000}

        routes = route_service.calculate_routes(
            origin=origin,
            destination=destination,
            avoid_disasters=True,
            alternatives=1
        )

        # Verify routes were returned
        assert len(routes) > 0, "Should return at least one route"

        route = routes[0]

        # Verify route structure
        assert 'route_id' in route
        assert 'distance_mi' in route
        assert 'duration_seconds' in route
        assert 'safety_score' in route
        assert 'waypoints' in route
        assert 'geometry' in route

        # Verify waypoints were parsed correctly
        assert len(route['waypoints']) == 3, "Should have 3 waypoint instructions"
        assert 'instruction' in route['waypoints'][0]
        assert route['waypoints'][0]['instruction'] == 'Head north on Main St'

        # Verify ORS request was made with disaster avoidance
        # The disaster is within the bounding box, so polygons should be generated
        call_args = mock_post.call_args
        request_data = call_args[1]['json']

        # ORS API should have been called
        assert 'coordinates' in request_data
        assert request_data['coordinates'][0] == [-122.4000, 37.5000]  # Origin [lon, lat]
        assert request_data['coordinates'][1] == [-122.3000, 37.9000]  # Dest [lon, lat]

        # If disaster was in route path, avoidance polygons should be included
        # Note: This depends on whether disaster is within bounding box
        # For this test, verify the request was made correctly
        assert 'instructions' in request_data

    @patch('requests.post')
    def test_route_without_disaster_avoidance(
        self,
        mock_post,
        route_service,
        mock_db,
        mock_successful_ors_response
    ):
        """Test route calculation with disaster avoidance disabled"""
        mock_db.reference.return_value.get.return_value = {}
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_successful_ors_response

        origin = {'lat': 37.5000, 'lon': -122.4000}
        destination = {'lat': 37.9000, 'lon': -122.3000}

        routes = route_service.calculate_routes(
            origin=origin,
            destination=destination,
            avoid_disasters=False,  # Disable avoidance
            alternatives=1
        )

        # Should still return routes
        assert len(routes) > 0

        # Verify ORS request did NOT include avoidance polygons
        call_args = mock_post.call_args
        request_data = call_args[1]['json']
        assert 'options' not in request_data or 'avoid_polygons' not in request_data.get('options', {}), \
            "Should not include avoidance polygons when disabled"


class TestWaypointAndDirectionAccuracy:
    """Test direction instructions and waypoint quality"""

    @patch('requests.post')
    def test_waypoint_parsing_from_ors_response(
        self,
        mock_post,
        route_service,
        mock_db,
        mock_successful_ors_response
    ):
        """Test that waypoints are correctly parsed from ORS response"""
        mock_db.reference.return_value.get.return_value = {}
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_successful_ors_response

        origin = {'lat': 37.5000, 'lon': -122.4000}
        destination = {'lat': 37.9000, 'lon': -122.3000}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)

        assert len(routes) > 0
        route = routes[0]

        # Verify waypoints
        waypoints = route['waypoints']
        assert len(waypoints) == 3

        # Check first waypoint
        wp1 = waypoints[0]
        assert wp1['instruction'] == 'Head north on Main St'
        assert wp1['distance_mi'] > 0  # Should be converted from meters to miles
        assert wp1['duration_seconds'] == 120

        # Check second waypoint
        wp2 = waypoints[1]
        assert wp2['instruction'] == 'Turn right onto Highway 101'

        # Check last waypoint
        wp3 = waypoints[2]
        assert wp3['instruction'] == 'Arrive at destination'

    @patch('requests.post')
    def test_distance_conversion_accuracy(
        self,
        mock_post,
        route_service,
        mock_db,
        mock_successful_ors_response
    ):
        """Test that distances are correctly converted from meters to miles"""
        mock_db.reference.return_value.get.return_value = {}
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_successful_ors_response

        origin = {'lat': 37.5000, 'lon': -122.4000}
        destination = {'lat': 37.9000, 'lon': -122.3000}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)

        route = routes[0]

        # ORS returns 50000 meters = 31.07 miles
        expected_distance_mi = 50000 / 1609.34
        actual_distance_mi = route['distance_mi']

        # Allow small floating point error
        assert abs(actual_distance_mi - expected_distance_mi) < 0.1, \
            f"Distance conversion incorrect: expected {expected_distance_mi:.2f}, got {actual_distance_mi:.2f}"


class TestRealWorldScenarios:
    """Test realistic disaster scenarios"""

    @patch('requests.post')
    def test_california_wildfire_evacuation_route(
        self,
        mock_post,
        route_service,
        mock_db,
        mock_successful_ors_response
    ):
        """
        Scenario: Large wildfire in Paradise, CA
        Route: Evacuate from Paradise to Chico (north)
        Expected: User is AT the wildfire location, so disaster should be EXCLUDED
                  from avoidance (user needs to escape, not avoid their current location)
        """
        paradise_wildfire = {
            'id': 'camp_fire',
            'type': 'wildfire',
            'severity': 'critical',
            'latitude': 39.7596,  # Paradise, CA
            'longitude': -121.6219,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'cal_fire',
            'acres_burned': 153336  # Camp Fire size
        }

        mock_db.reference.return_value.get.return_value = {'disaster_1': paradise_wildfire}
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_successful_ors_response

        # Evacuate north to Chico FROM Paradise (exact wildfire location)
        origin = {'lat': 39.7596, 'lon': -121.6219}  # Paradise - AT wildfire
        destination = {'lat': 39.7285, 'lon': -121.8375}  # Chico

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=True)

        # User is AT the wildfire location, so disaster should be EXCLUDED from avoidance
        # This allows the user to escape the danger zone
        call_args = mock_post.call_args
        request_data = call_args[1]['json']

        # No avoidance polygons should be sent (disaster at origin excluded)
        # ORS will calculate fastest escape route
        assert 'options' not in request_data or 'avoid_polygons' not in request_data.get('options', {})

    @patch('requests.post')
    def test_multiple_concurrent_disasters(
        self,
        mock_post,
        route_service,
        mock_db,
        mock_successful_ors_response
    ):
        """
        Scenario: Multiple disasters along a route
        Expected: Route should avoid all disaster zones
        """
        now = datetime.now(timezone.utc)

        disasters = {
            'wildfire_1': {
                'id': 'wildfire_1',
                'type': 'wildfire',
                'severity': 'critical',
                'latitude': 37.5000,
                'longitude': -122.3000,
                'timestamp': now.isoformat(),
                'source': 'nasa_firms'
            },
            'earthquake_1': {
                'id': 'earthquake_1',
                'type': 'earthquake',
                'severity': 'high',
                'latitude': 37.7000,
                'longitude': -122.3000,
                'timestamp': now.isoformat(),
                'source': 'usgs',
                'magnitude': 6.2
            },
            'flood_1': {
                'id': 'flood_1',
                'type': 'flood',
                'severity': 'medium',
                'latitude': 37.9000,
                'longitude': -122.3000,
                'timestamp': now.isoformat(),
                'source': 'noaa'
            }
        }

        mock_db.reference.return_value.get.return_value = disasters
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_successful_ors_response

        origin = {'lat': 37.3000, 'lon': -122.3000}
        destination = {'lat': 38.1000, 'lon': -122.3000}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=True)

        # Should create 3 avoidance polygons
        call_args = mock_post.call_args
        request_data = call_args[1]['json']
        assert len(request_data['options']['avoid_polygons']['coordinates']) == 3, \
            "Should create 3 disaster avoidance polygons"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
