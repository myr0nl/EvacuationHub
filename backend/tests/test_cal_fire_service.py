"""
Tests for Cal Fire ArcGIS Integration Service
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from services.cal_fire_service import CalFireService
from datetime import datetime, timezone


class TestCalFireService:
    """Test suite for CalFireService class"""

    @pytest.fixture
    def cal_fire_service(self):
        """Create CalFireService instance for testing"""
        return CalFireService()

    @pytest.fixture
    def mock_geojson_response(self):
        """Mock GeoJSON response from Cal Fire ArcGIS API"""
        return {
            'type': 'FeatureCollection',
            'features': [
                {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [-120.5, 38.5]  # [lon, lat]
                    },
                    'properties': {
                        'FIRE_NAME': 'Creek Fire',
                        'COUNTY': 'Fresno',
                        'GIS_ACRES': 379895.0,
                        'PERCENT_CONTAINED': 100.0,
                        'ALARM_DATE': '2020-09-04'
                    }
                },
                {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Polygon',
                        'coordinates': [[
                            [-121.0, 39.0],
                            [-121.0, 39.5],
                            [-120.5, 39.5],
                            [-120.5, 39.0],
                            [-121.0, 39.0]
                        ]]
                    },
                    'properties': {
                        'INCIDENT_NAME': 'Dixie Fire',
                        'LOCATION': 'Butte',
                        'ACRES': 963309.0,
                        'CONTAINMENT': 75.0,
                        'START_DATE': 1626134400000  # Unix timestamp in ms
                    }
                }
            ]
        }

    def test_initialization(self, cal_fire_service):
        """Test service initialization"""
        assert cal_fire_service is not None
        assert cal_fire_service.BASE_URL is not None
        assert 'arcgis.com' in cal_fire_service.BASE_URL

    def test_parse_arcgis_response_with_point_geometry(self, cal_fire_service, mock_geojson_response):
        """Test parsing GeoJSON with Point geometry"""
        incidents = cal_fire_service._parse_arcgis_response(mock_geojson_response)

        assert len(incidents) == 2

        # Check first incident (Point geometry)
        incident = incidents[0]
        assert incident['name'] == 'Creek Fire'
        assert incident['county'] == 'Fresno'
        assert incident['latitude'] == 38.5
        assert incident['longitude'] == -120.5
        assert incident['acres_burned'] == 379895.0
        assert incident['percent_contained'] == 100.0
        assert incident['source'] == 'cal_fire'
        assert incident['type'] == 'wildfire'
        assert 'id' in incident
        assert incident['confidence_score'] >= 0.7  # Official data should have reasonably high confidence

    def test_parse_arcgis_response_with_polygon_geometry(self, cal_fire_service, mock_geojson_response):
        """Test parsing GeoJSON with Polygon geometry (calculates centroid)"""
        incidents = cal_fire_service._parse_arcgis_response(mock_geojson_response)

        # Check second incident (Polygon geometry)
        incident = incidents[1]
        assert incident['name'] == 'Dixie Fire'
        assert incident['county'] == 'Butte'
        assert incident['latitude'] is not None  # Centroid calculated
        assert incident['longitude'] is not None
        assert incident['acres_burned'] == 963309.0
        assert incident['percent_contained'] == 75.0

    def test_extract_centroid_point(self, cal_fire_service):
        """Test centroid extraction from Point geometry"""
        geometry = {
            'type': 'Point',
            'coordinates': [-122.4194, 37.7749]  # San Francisco
        }

        lat, lon = cal_fire_service._extract_centroid(geometry)

        assert lat == 37.7749
        assert lon == -122.4194

    def test_extract_centroid_polygon(self, cal_fire_service):
        """Test centroid extraction from Polygon geometry"""
        geometry = {
            'type': 'Polygon',
            'coordinates': [[
                [-121.0, 39.0],
                [-121.0, 40.0],
                [-120.0, 40.0],
                [-120.0, 39.0],
                [-121.0, 39.0]
            ]]
        }

        lat, lon = cal_fire_service._extract_centroid(geometry)

        # Centroid should be at center of square
        assert lat == pytest.approx(39.5, rel=0.1)
        assert lon == pytest.approx(-120.5, rel=0.1)

    def test_extract_centroid_multipolygon(self, cal_fire_service):
        """Test centroid extraction from MultiPolygon geometry"""
        geometry = {
            'type': 'MultiPolygon',
            'coordinates': [
                [[
                    [-121.0, 39.0],
                    [-121.0, 40.0],
                    [-120.0, 40.0],
                    [-120.0, 39.0],
                    [-121.0, 39.0]
                ]]
            ]
        }

        lat, lon = cal_fire_service._extract_centroid(geometry)

        # Should use first polygon's centroid
        assert lat is not None
        assert lon is not None

    def test_extract_centroid_invalid_geometry(self, cal_fire_service):
        """Test centroid extraction with invalid geometry"""
        geometry = {
            'type': 'Unknown',
            'coordinates': []
        }

        lat, lon = cal_fire_service._extract_centroid(geometry)

        assert lat is None
        assert lon is None

    def test_determine_severity_critical_large_uncontained(self, cal_fire_service):
        """Test severity determination for large uncontained fire"""
        severity = cal_fire_service._determine_severity(acres_burned=15000, percent_contained=30)
        assert severity == 'critical'

    def test_determine_severity_critical_medium_low_containment(self, cal_fire_service):
        """Test severity determination for medium fire with low containment"""
        severity = cal_fire_service._determine_severity(acres_burned=6000, percent_contained=50)
        assert severity == 'critical'

    def test_determine_severity_high(self, cal_fire_service):
        """Test severity determination for high severity fire"""
        severity = cal_fire_service._determine_severity(acres_burned=2000, percent_contained=70)
        assert severity == 'high'

    def test_determine_severity_medium(self, cal_fire_service):
        """Test severity determination for medium severity fire"""
        severity = cal_fire_service._determine_severity(acres_burned=600, percent_contained=85)
        assert severity == 'medium'

    def test_determine_severity_low(self, cal_fire_service):
        """Test severity determination for low severity fire"""
        severity = cal_fire_service._determine_severity(acres_burned=100, percent_contained=95)
        assert severity == 'low'

    def test_safe_float_valid_number(self, cal_fire_service):
        """Test safe float conversion with valid number"""
        result = cal_fire_service._safe_float(123.45)
        assert result == 123.45

    def test_safe_float_string_number(self, cal_fire_service):
        """Test safe float conversion with string number"""
        result = cal_fire_service._safe_float('678.90')
        assert result == 678.90

    def test_safe_float_none(self, cal_fire_service):
        """Test safe float conversion with None"""
        result = cal_fire_service._safe_float(None, default=0.0)
        assert result == 0.0

    def test_safe_float_invalid(self, cal_fire_service):
        """Test safe float conversion with invalid value"""
        result = cal_fire_service._safe_float('invalid', default=0.0)
        assert result == 0.0

    def test_parse_date_field_iso_format(self, cal_fire_service):
        """Test date parsing with ISO format"""
        result = cal_fire_service._parse_date_field('2023-09-15')
        assert '2023-09-15' in result

    def test_parse_date_field_unix_timestamp(self, cal_fire_service):
        """Test date parsing with Unix timestamp (milliseconds)"""
        # 1626134400000 = 2021-07-12 20:00:00 UTC (but may vary by timezone)
        result = cal_fire_service._parse_date_field(1626134400000)
        # Check that result contains 2021-07 (month/year correct regardless of timezone)
        assert '2021-07' in result

    def test_parse_date_field_various_formats(self, cal_fire_service):
        """Test date parsing with various date formats"""
        dates = [
            '2023-09-15',
            '2023/09/15',
            '09/15/2023'
        ]

        for date_str in dates:
            result = cal_fire_service._parse_date_field(date_str)
            assert result is not None
            assert isinstance(result, str)

    def test_parse_date_field_invalid(self, cal_fire_service):
        """Test date parsing with invalid date"""
        result = cal_fire_service._parse_date_field('invalid-date')
        # Should return current time on failure
        assert result is not None
        assert isinstance(result, str)

    def test_parse_date_field_empty(self, cal_fire_service):
        """Test date parsing with empty value"""
        result = cal_fire_service._parse_date_field('')
        # Should return current time
        assert result is not None

    def test_generate_incident_id(self, cal_fire_service):
        """Test incident ID generation"""
        incident_id = cal_fire_service._generate_incident_id(
            name='Creek Fire',
            county='Fresno County',
            lat=37.1234,
            lon=-119.5678
        )

        assert incident_id.startswith('calfire_')
        assert 'Creek_Fire' in incident_id
        assert 'Fresno_County' in incident_id
        assert '37.1234' in incident_id
        assert '-119.5678' in incident_id

    def test_generate_incident_id_with_special_chars(self, cal_fire_service):
        """Test incident ID generation with special characters"""
        incident_id = cal_fire_service._generate_incident_id(
            name='Fire / Complex',
            county='Los Angeles',
            lat=34.0522,
            lon=-118.2437
        )

        # Special characters should be replaced with underscores
        assert '/' not in incident_id
        assert '_' in incident_id

    @patch('services.cal_fire_service.requests.get')
    def test_fetch_active_incidents_success(self, mock_get, cal_fire_service, mock_geojson_response):
        """Test successful fetch of active incidents"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_geojson_response
        mock_get.return_value = mock_response

        incidents = cal_fire_service.fetch_active_incidents()

        assert len(incidents) > 0
        assert mock_get.called

        # Verify request parameters
        call_args = mock_get.call_args
        assert 'params' in call_args.kwargs
        params = call_args.kwargs['params']
        assert params['where'] == '1=1'
        assert params['outFields'] == '*'
        assert params['f'] == 'geojson'

    @patch('services.cal_fire_service.requests.get')
    def test_fetch_active_incidents_api_error(self, mock_get, cal_fire_service):
        """Test handling of API errors"""
        mock_get.side_effect = Exception('API Error')

        incidents = cal_fire_service.fetch_active_incidents()

        # Should return empty list on error
        assert incidents == []

    @patch('services.cal_fire_service.requests.get')
    def test_fetch_active_incidents_http_error(self, mock_get, cal_fire_service):
        """Test handling of HTTP errors"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception('HTTP 500')
        mock_get.return_value = mock_response

        incidents = cal_fire_service.fetch_active_incidents()

        # Should return empty list on HTTP error
        assert incidents == []

    @patch('services.cal_fire_service.requests.get')
    def test_fetch_active_incidents_no_features(self, mock_get, cal_fire_service):
        """Test handling of response with no features"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'type': 'FeatureCollection', 'features': []}
        mock_get.return_value = mock_response

        incidents = cal_fire_service.fetch_active_incidents()

        assert incidents == []

    def test_get_cached_incidents_cache_expired(self, cal_fire_service):
        """Test getting incidents when cache is expired"""
        mock_cache_manager = Mock()
        mock_cache_manager.should_update.return_value = True
        mock_cache_manager.get_cached_data.return_value = []

        with patch.object(cal_fire_service, 'fetch_active_incidents', return_value=[{'id': 'test'}]):
            incidents = cal_fire_service.get_cached_incidents(mock_cache_manager)

        # Should fetch fresh data
        assert mock_cache_manager.should_update.called
        assert mock_cache_manager.update_cache.called

    def test_get_cached_incidents_cache_valid(self, cal_fire_service):
        """Test getting incidents when cache is valid"""
        mock_cache_manager = Mock()
        mock_cache_manager.should_update.return_value = False
        mock_cache_manager.get_cached_data.return_value = [{'id': 'cached'}]

        incidents = cal_fire_service.get_cached_incidents(mock_cache_manager)

        # Should use cached data
        assert mock_cache_manager.should_update.called
        assert not mock_cache_manager.update_cache.called
        assert incidents == [{'id': 'cached'}]

    def test_get_cached_incidents_error_fallback(self, cal_fire_service):
        """Test fallback to cached data on error"""
        mock_cache_manager = Mock()
        mock_cache_manager.should_update.side_effect = Exception('Cache error')
        mock_cache_manager.get_cached_data.return_value = [{'id': 'fallback'}]

        incidents = cal_fire_service.get_cached_incidents(mock_cache_manager)

        # Should fall back to cached data
        assert incidents == [{'id': 'fallback'}]

    def test_calculate_polygon_centroid(self, cal_fire_service):
        """Test polygon centroid calculation"""
        # Square polygon
        coords = [
            [-121.0, 39.0],
            [-121.0, 40.0],
            [-120.0, 40.0],
            [-120.0, 39.0],
            [-121.0, 39.0]
        ]

        lat, lon = cal_fire_service._calculate_polygon_centroid(coords)

        # Center of square
        assert lat == pytest.approx(39.5, rel=0.01)
        assert lon == pytest.approx(-120.5, rel=0.01)

    def test_calculate_polygon_centroid_empty(self, cal_fire_service):
        """Test polygon centroid calculation with empty coordinates"""
        lat, lon = cal_fire_service._calculate_polygon_centroid([])
        assert lat is None
        assert lon is None

    def test_confidence_scoring_integration(self, cal_fire_service, mock_geojson_response):
        """Test that confidence scoring is applied to incidents"""
        incidents = cal_fire_service._parse_arcgis_response(mock_geojson_response)

        for incident in incidents:
            assert 'confidence_score' in incident
            assert 'confidence_level' in incident
            assert 0 <= incident['confidence_score'] <= 1
            assert incident['confidence_level'] in ['Low', 'Medium', 'High']
            # Cal Fire official data should have reasonably high confidence (>70%)
            assert incident['confidence_score'] >= 0.7

    def test_incident_structure(self, cal_fire_service, mock_geojson_response):
        """Test that parsed incidents have all required fields"""
        incidents = cal_fire_service._parse_arcgis_response(mock_geojson_response)

        required_fields = [
            'id', 'source', 'type', 'name', 'county', 'latitude', 'longitude',
            'acres_burned', 'percent_contained', 'started', 'timestamp',
            'severity', 'confidence_score', 'confidence_level'
        ]

        for incident in incidents:
            for field in required_fields:
                assert field in incident, f"Missing field: {field}"

    def test_incident_data_types(self, cal_fire_service, mock_geojson_response):
        """Test that incident fields have correct data types"""
        incidents = cal_fire_service._parse_arcgis_response(mock_geojson_response)

        for incident in incidents:
            assert isinstance(incident['id'], str)
            assert isinstance(incident['name'], str)
            assert isinstance(incident['county'], str)
            assert isinstance(incident['latitude'], float)
            assert isinstance(incident['longitude'], float)
            assert isinstance(incident['acres_burned'], float)
            assert isinstance(incident['percent_contained'], float)
            assert isinstance(incident['severity'], str)
            assert incident['severity'] in ['low', 'medium', 'high', 'critical']
