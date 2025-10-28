"""
Tests for RouteCalculationService

Tests disaster polygon generation, safety scoring, and route calculation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from services.route_calculation_service import RouteCalculationService


@pytest.fixture
def mock_db():
    """Mock Firebase database"""
    db = MagicMock()
    # Mock empty database by default
    db.reference.return_value.get.return_value = None
    return db


@pytest.fixture
def mock_disasters():
    """Mock disaster data with various types and severities"""
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=50)

    return {
        'disaster_1': {
            'id': 'disaster_1',
            'type': 'wildfire',
            'severity': 'critical',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'timestamp': now.isoformat(),
            'source': 'nasa_firms'
        },
        'disaster_2': {
            'id': 'disaster_2',
            'type': 'earthquake',
            'severity': 'high',
            'latitude': 37.8044,
            'longitude': -122.2711,
            'timestamp': now.isoformat(),
            'source': 'usgs_earthquake'
        },
        'disaster_3': {
            'id': 'disaster_3',
            'type': 'drought',  # Should be excluded
            'severity': 'medium',
            'latitude': 37.7500,
            'longitude': -122.4500,
            'timestamp': now.isoformat(),
            'source': 'user_report'
        },
        'disaster_4': {
            'id': 'disaster_4',
            'type': 'flood',
            'severity': 'low',
            'latitude': 37.7000,
            'longitude': -122.4000,
            'timestamp': old_time.isoformat(),  # Too old, should be excluded
            'source': 'user_report'
        }
    }


@pytest.fixture
def mock_ors_response():
    """Mock successful ORS API response (GeoJSON FeatureCollection)"""
    return {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'properties': {
                    'summary': {
                        'distance': 25300,  # meters
                        'duration': 1800  # seconds
                    },
                    'segments': [
                        {
                            'steps': [
                                {
                                    'instruction': 'Turn left onto Main St',
                                    'distance': 500,
                                    'duration': 60
                                }
                            ]
                        }
                    ]
                },
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [
                        [-122.4194, 37.7749],
                        [-122.4000, 37.7600],
                        [-122.2711, 37.8044]
                    ]
                }
            }
        ]
    }


@pytest.fixture
def route_service(mock_db):
    """Create RouteCalculationService with mocked dependencies"""
    with patch('os.getenv', return_value='test_api_key'):
        service = RouteCalculationService(db=mock_db)
        return service


class TestDisasterPolygonGeneration:
    """Tests for disaster polygon generation and filtering"""

    def test_disaster_type_filtering(self, route_service, mock_db, mock_disasters):
        """Test that drought and old disasters are excluded"""
        # Setup mock to return disasters
        mock_db.reference.return_value.get.return_value = mock_disasters

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 37.8044, 'lon': -122.2711}

        polygons, disasters = route_service.get_disaster_polygons(origin, destination)

        # Should include wildfire and earthquake, exclude drought and old flood
        disaster_ids = [d['id'] for d in disasters]
        assert 'disaster_1' in disaster_ids  # wildfire - included
        assert 'disaster_2' in disaster_ids  # earthquake - included
        assert 'disaster_3' not in disaster_ids  # drought - excluded
        assert 'disaster_4' not in disaster_ids  # flood too old - excluded

    def test_buffer_sizes_by_severity(self, route_service, mock_db):
        """Test that buffer sizes match severity levels"""
        disasters = {
            'd1': {
                'id': 'd1',
                'type': 'wildfire',
                'severity': 'critical',
                'latitude': 37.8500,  # Away from origin to avoid exclusion
                'longitude': -122.3500,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'source': 'nasa_firms'
            }
        }
        mock_db.reference.return_value.get.return_value = disasters

        origin = {'lat': 37.7749, 'lon': -122.4194}  # Different from disaster location
        destination = {'lat': 38.0, 'lon': -122.0}

        polygons, active_disasters = route_service.get_disaster_polygons(origin, destination)

        # Critical severity should use 5 miles buffer radius from BUFFER_RADII_MI
        assert len(polygons) == 1  # One disaster, one polygon (not excluded because user is outside)
        assert route_service.BUFFER_RADII_MI['critical'] == 5


class TestSafetyScoring:
    """Tests for route safety score calculation"""

    def test_safety_score_with_no_disasters(self, route_service):
        """Test safety score is 100 when no disasters present"""
        from shapely.geometry import LineString
        route_geometry = LineString([[-122.4194, 37.7749], [-122.2711, 37.8044]])
        disasters = []

        result = route_service.calculate_route_safety_score(route_geometry, disasters)

        assert result['score'] == 100.0
        assert result['nearby_count'] == 0
        assert result['min_distance_mi'] is None

    def test_safety_score_decreases_with_nearby_disasters(self, route_service):
        """Test safety score decreases when disasters are nearby"""
        from shapely.geometry import LineString
        route_geometry = LineString([[-122.4194, 37.7749], [-122.2711, 37.8044]])
        disasters = [
            {
                'id': 'd1',
                'type': 'wildfire',
                'severity': 'critical',
                'latitude': 37.7749,
                'longitude': -122.4000,  # Very close to route
                'source': 'nasa_firms'
            }
        ]

        result = route_service.calculate_route_safety_score(route_geometry, disasters)

        # Score should be significantly reduced
        assert result['score'] < 80.0
        assert result['nearby_count'] > 0
        assert result['score'] >= 0.0


class TestRouteCalculation:
    """Tests for full route calculation workflow"""

    @patch('requests.post')
    def test_calculate_routes_with_disasters(self, mock_post, route_service, mock_db, mock_disasters, mock_ors_response):
        """Test route calculation with disaster avoidance"""
        # Setup mocks
        mock_db.reference.return_value.get.return_value = mock_disasters
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 37.8044, 'lon': -122.2711}

        routes = route_service.calculate_routes(
            origin=origin,
            destination=destination,
            avoid_disasters=True,
            alternatives=3
        )

        # Should return routes
        assert len(routes) > 0

        # Check route structure
        route = routes[0]
        assert 'route_id' in route
        assert 'distance_mi' in route
        assert 'duration_seconds' in route
        assert 'safety_score' in route
        assert 'geometry' in route
        assert 'waypoints' in route

        # Check conversions (use approximate equality for floating point)
        assert abs(route['distance_mi'] - 15.7) < 0.1  # 25300m → ~15.7 miles
        assert route['duration_seconds'] == 1800

    @patch('requests.post')
    def test_calculate_routes_api_failure(self, mock_post, route_service, mock_db):
        """Test graceful handling of ORS API failure"""
        import requests
        # Setup mock to fail with requests exception
        mock_post.side_effect = requests.exceptions.RequestException("API Error")

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 37.8044, 'lon': -122.2711}

        routes = route_service.calculate_routes(origin, destination)

        # Should return empty list on failure
        assert routes == []

    def test_invalid_coordinates(self, route_service):
        """Test handling of invalid coordinates"""
        invalid_origin = {'lat': 999, 'lon': -122.4194}  # Invalid lat
        destination = {'lat': 37.8044, 'lon': -122.2711}

        routes = route_service.calculate_routes(invalid_origin, destination)

        # Should return empty list for invalid coords
        assert routes == []


class TestCoordinateConversion:
    """Tests for coordinate format conversion"""

    @patch('requests.post')
    def test_coordinate_format_in_request(self, mock_post, route_service, mock_db, mock_ors_response):
        """Test that coordinates are converted to [lon, lat] for ORS"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_ors_response

        origin = {'lat': 37.7749, 'lon': -122.4194}
        destination = {'lat': 37.8044, 'lon': -122.2711}

        route_service.calculate_routes(origin, destination)

        # Check that the request was made with correct coordinate format
        call_args = mock_post.call_args
        request_data = call_args[1]['json']

        # ORS expects [lon, lat] format
        assert request_data['coordinates'][0] == [-122.4194, 37.7749]
        assert request_data['coordinates'][1] == [-122.2711, 37.8044]
