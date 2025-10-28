"""
Tests for Direction Quality and User Navigation Experience

Tests the quality and accuracy of turn-by-turn directions shown to users,
including waypoint parsing, instruction formatting, and Google Maps integration.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from services.route_calculation_service import RouteCalculationService


@pytest.fixture
def mock_db():
    """Mock Firebase database"""
    db = MagicMock()
    # Setup empty database by default
    mock_refs = {
        'reports': {},
        'public_data_cache/wildfires/data': [],
        'public_data_cache/weather_alerts/data': [],
        'public_data_cache/usgs_earthquakes/data': [],
        'public_data_cache/cal_fire_incidents/data': []
    }

    def mock_reference(path):
        ref = MagicMock()
        ref.get.return_value = mock_refs.get(path, None)
        return ref

    db.reference = mock_reference
    return db


@pytest.fixture
def route_service(mock_db):
    """Create RouteCalculationService"""
    with patch('os.getenv', return_value='test_api_key'):
        service = RouteCalculationService(db=mock_db)
        return service


@pytest.fixture
def detailed_ors_response():
    """Mock ORS response with realistic navigation instructions"""
    return {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'properties': {
                    'summary': {
                        'distance': 45000,  # 45km = 27.96 miles
                        'duration': 2700  # 45 minutes
                    },
                    'segments': [
                        {
                            'steps': [
                                {
                                    'instruction': 'Head north on Main Street',
                                    'distance': 500,  # 500m = 0.31 miles
                                    'duration': 60,  # 1 minute
                                    'type': 0  # Depart
                                },
                                {
                                    'instruction': 'Turn right onto Highway 101',
                                    'distance': 35000,  # 35km = 21.75 miles
                                    'duration': 1800,  # 30 minutes
                                    'type': 1  # Turn right
                                },
                                {
                                    'instruction': 'Take exit 42A toward Downtown',
                                    'distance': 2000,  # 2km = 1.24 miles
                                    'duration': 180,  # 3 minutes
                                    'type': 6  # Exit/ramp
                                },
                                {
                                    'instruction': 'Continue straight on Oak Avenue',
                                    'distance': 5000,  # 5km = 3.11 miles
                                    'duration': 420,  # 7 minutes
                                    'type': 0  # Continue
                                },
                                {
                                    'instruction': 'Turn left onto Elm Street',
                                    'distance': 1500,  # 1.5km = 0.93 miles
                                    'duration': 180,  # 3 minutes
                                    'type': 2  # Turn left
                                },
                                {
                                    'instruction': 'Arrive at Safe Zone - Community Center',
                                    'distance': 100,  # 100m = 0.06 miles
                                    'duration': 60,  # 1 minute
                                    'type': 10  # Arrive
                                }
                            ]
                        }
                    ]
                },
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [
                        [-122.4194, 37.7749],  # Start
                        [-122.4200, 37.7850],  # After 500m
                        [-122.3500, 38.0000],  # After 35km on highway
                        [-122.3400, 38.0100],  # After exit
                        [-122.3200, 38.0500],  # After 5km
                        [-122.3100, 38.0600],  # After 1.5km
                        [-122.3090, 38.0610]   # Final destination
                    ]
                }
            }
        ]
    }


class TestWaypointInstructionParsing:
    """Test parsing of turn-by-turn navigation instructions"""

    @patch('requests.post')
    def test_waypoint_instruction_extraction(self, mock_post, route_service, mock_db, detailed_ors_response):
        """Test that all waypoint instructions are correctly extracted"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)

        assert len(routes) > 0
        route = routes[0]
        waypoints = route['waypoints']

        # Verify all 6 instructions were parsed
        assert len(waypoints) == 6, "Should extract all 6 navigation steps"

        # Check specific instructions
        assert waypoints[0]['instruction'] == 'Head north on Main Street'
        assert waypoints[1]['instruction'] == 'Turn right onto Highway 101'
        assert waypoints[2]['instruction'] == 'Take exit 42A toward Downtown'
        assert waypoints[3]['instruction'] == 'Continue straight on Oak Avenue'
        assert waypoints[4]['instruction'] == 'Turn left onto Elm Street'
        assert waypoints[5]['instruction'] == 'Arrive at Safe Zone - Community Center'

    @patch('requests.post')
    def test_waypoint_distance_conversion(self, mock_post, route_service, mock_db, detailed_ors_response):
        """Test that waypoint distances are correctly converted to miles"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)
        waypoints = routes[0]['waypoints']

        # Check distance conversions (meters to miles: distance_m / 1609.34)
        expected_distances = [
            500 / 1609.34,    # 0.31 miles
            35000 / 1609.34,  # 21.75 miles
            2000 / 1609.34,   # 1.24 miles
            5000 / 1609.34,   # 3.11 miles
            1500 / 1609.34,   # 0.93 miles
            100 / 1609.34     # 0.06 miles
        ]

        for i, expected in enumerate(expected_distances):
            actual = waypoints[i]['distance_mi']
            assert abs(actual - expected) < 0.01, \
                f"Waypoint {i} distance mismatch: expected {expected:.2f}, got {actual:.2f}"

    @patch('requests.post')
    def test_waypoint_duration_parsing(self, mock_post, route_service, mock_db, detailed_ors_response):
        """Test that waypoint durations are correctly parsed"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)
        waypoints = routes[0]['waypoints']

        # Check durations (in seconds)
        expected_durations = [60, 1800, 180, 420, 180, 60]

        for i, expected in enumerate(expected_durations):
            actual = waypoints[i]['duration_seconds']
            assert actual == expected, \
                f"Waypoint {i} duration mismatch: expected {expected}s, got {actual}s"

    @patch('requests.post')
    def test_waypoint_type_handling(self, mock_post, route_service, mock_db, detailed_ors_response):
        """Test that instruction type codes are correctly handled"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)
        waypoints = routes[0]['waypoints']

        # Verify type codes are converted to strings
        # ORS returns integer type codes, we should convert them
        for waypoint in waypoints:
            assert 'type' in waypoint
            assert isinstance(waypoint['type'], str), \
                f"Type should be string, got {type(waypoint['type'])}"


class TestDirectionQuality:
    """Test the quality and usefulness of navigation directions"""

    @patch('requests.post')
    def test_first_instruction_is_departure(self, mock_post, route_service, mock_db, detailed_ors_response):
        """First instruction should be a clear departure instruction"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)
        first_instruction = routes[0]['waypoints'][0]['instruction']

        # First instruction should start with "Head" or "Depart" or "Start"
        assert any(word in first_instruction for word in ['Head', 'Depart', 'Start']), \
            f"First instruction should be a departure: {first_instruction}"

    @patch('requests.post')
    def test_last_instruction_is_arrival(self, mock_post, route_service, mock_db, detailed_ors_response):
        """Last instruction should be a clear arrival instruction"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)
        last_instruction = routes[0]['waypoints'][-1]['instruction']

        # Last instruction should contain "Arrive"
        assert 'Arrive' in last_instruction, \
            f"Last instruction should be an arrival: {last_instruction}"

    @patch('requests.post')
    def test_turn_instructions_specify_direction(self, mock_post, route_service, mock_db, detailed_ors_response):
        """Turn instructions should specify left or right"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)
        waypoints = routes[0]['waypoints']

        # Find turn instructions
        turn_instructions = [
            wp for wp in waypoints
            if 'turn' in wp['instruction'].lower()
        ]

        assert len(turn_instructions) >= 2, "Should have multiple turn instructions"

        # Each turn should specify direction
        for turn in turn_instructions:
            instruction = turn['instruction'].lower()
            assert 'left' in instruction or 'right' in instruction, \
                f"Turn instruction should specify direction: {turn['instruction']}"

    @patch('requests.post')
    def test_street_names_included(self, mock_post, route_service, mock_db, detailed_ors_response):
        """Instructions should include street names for clarity"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)
        waypoints = routes[0]['waypoints']

        # Most instructions (except first/last) should mention street names
        middle_instructions = waypoints[1:-1]

        streets_mentioned = sum(
            1 for wp in middle_instructions
            if any(word in wp['instruction'] for word in ['Street', 'Avenue', 'Highway', 'Road', 'Boulevard'])
        )

        assert streets_mentioned >= len(middle_instructions) * 0.5, \
            "Most instructions should include street names"


class TestTotalRouteMetrics:
    """Test overall route distance and duration calculations"""

    @patch('requests.post')
    def test_total_distance_matches_waypoint_sum(self, mock_post, route_service, mock_db, detailed_ors_response):
        """Total route distance should approximately match sum of waypoint distances"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)
        route = routes[0]

        # Calculate sum of waypoint distances
        waypoint_total = sum(wp['distance_mi'] for wp in route['waypoints'])
        route_total = route['distance_mi']

        # Should match within 5% (accounting for rounding)
        difference_percent = abs(waypoint_total - route_total) / route_total * 100
        assert difference_percent < 5, \
            f"Waypoint sum ({waypoint_total:.2f}) should match route total ({route_total:.2f})"

    @patch('requests.post')
    def test_total_duration_matches_waypoint_sum(self, mock_post, route_service, mock_db, detailed_ors_response):
        """Total route duration should match sum of waypoint durations"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)
        route = routes[0]

        # Calculate sum of waypoint durations
        waypoint_total = sum(wp['duration_seconds'] for wp in route['waypoints'])
        route_total = route['duration_seconds']

        # Should match exactly (or very close)
        assert abs(waypoint_total - route_total) < 5, \
            f"Waypoint duration sum ({waypoint_total}s) should match route total ({route_total}s)"


class TestInstructionCompleteness:
    """Test that instructions provide complete navigation guidance"""

    @patch('requests.post')
    def test_no_missing_instructions(self, mock_post, route_service, mock_db, detailed_ors_response):
        """All waypoints should have non-empty instructions"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)
        waypoints = routes[0]['waypoints']

        for i, waypoint in enumerate(waypoints):
            assert 'instruction' in waypoint, f"Waypoint {i} missing instruction field"
            assert waypoint['instruction'], f"Waypoint {i} has empty instruction"
            assert len(waypoint['instruction']) > 5, \
                f"Waypoint {i} instruction too short: '{waypoint['instruction']}'"

    @patch('requests.post')
    def test_all_waypoints_have_distances(self, mock_post, route_service, mock_db, detailed_ors_response):
        """All waypoints should have distance information"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)
        waypoints = routes[0]['waypoints']

        for i, waypoint in enumerate(waypoints):
            assert 'distance_mi' in waypoint, f"Waypoint {i} missing distance"
            assert waypoint['distance_mi'] >= 0, f"Waypoint {i} has negative distance"

    @patch('requests.post')
    def test_all_waypoints_have_durations(self, mock_post, route_service, mock_db, detailed_ors_response):
        """All waypoints should have duration information"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)
        waypoints = routes[0]['waypoints']

        for i, waypoint in enumerate(waypoints):
            assert 'duration_seconds' in waypoint, f"Waypoint {i} missing duration"
            assert waypoint['duration_seconds'] >= 0, f"Waypoint {i} has negative duration"


class TestGoogleMapsCompatibility:
    """Test that route data is compatible with Google Maps navigation"""

    @patch('requests.post')
    def test_geometry_format_for_google_maps(self, mock_post, route_service, mock_db, detailed_ors_response):
        """Route geometry should be in [lon, lat] format for easy conversion"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)
        geometry = routes[0]['geometry']

        # Verify all coordinates are [lon, lat] pairs
        for coord in geometry:
            assert len(coord) == 2, "Coordinate should be [lon, lat] pair"
            lon, lat = coord
            # Validate longitude range
            assert -180 <= lon <= 180, f"Invalid longitude: {lon}"
            # Validate latitude range
            assert -90 <= lat <= 90, f"Invalid latitude: {lat}"

    @patch('requests.post')
    def test_sufficient_geometry_points(self, mock_post, route_service, mock_db, detailed_ors_response):
        """Route should have sufficient geometry points for accurate display"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = detailed_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 38.0610, 'lon': -122.3090}

        routes = route_service.calculate_routes(origin, destination, avoid_disasters=False)
        geometry = routes[0]['geometry']

        # For a 28-mile route, should have at least 5 points
        assert len(geometry) >= 5, \
            f"Route should have sufficient geometry points, got {len(geometry)}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
