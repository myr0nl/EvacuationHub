"""
Unit tests for USGS Earthquake Service
Tests earthquake data fetching, parsing, and confidence scoring
"""
import pytest
from datetime import datetime, timezone, timedelta
import sys
import os
from unittest.mock import Mock, patch

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.usgs_earthquake_service import USGSEarthquakeService
from services.confidence_scorer import ConfidenceScorer


class TestUSGSEarthquakeService:
    """Test suite for USGS Earthquake Service"""

    def setup_method(self):
        """Setup test fixtures"""
        self.service = USGSEarthquakeService()
        self.scorer = ConfidenceScorer()

    def test_initialization(self):
        """Test service initializes correctly"""
        assert self.service is not None
        assert self.service.confidence_scorer is not None

    def test_initialization_with_scorer(self):
        """Test service accepts custom confidence scorer"""
        custom_scorer = ConfidenceScorer()
        service = USGSEarthquakeService(confidence_scorer=custom_scorer)
        assert service.confidence_scorer == custom_scorer

    def test_severity_determination(self):
        """Test earthquake severity mapping from magnitude"""
        # Test critical severity (7.0+)
        assert self.service._determine_severity(7.5) == 'critical'
        assert self.service._determine_severity(8.0) == 'critical'

        # Test high severity (6.0-6.9)
        assert self.service._determine_severity(6.0) == 'high'
        assert self.service._determine_severity(6.5) == 'high'

        # Test medium severity (5.0-5.9)
        assert self.service._determine_severity(5.0) == 'medium'
        assert self.service._determine_severity(5.5) == 'medium'

        # Test low severity (2.5-4.9)
        assert self.service._determine_severity(2.5) == 'low'
        assert self.service._determine_severity(4.9) == 'low'

    def test_is_in_us_continental(self):
        """Test continental US boundary detection"""
        # San Francisco, CA
        assert self.service._is_in_us(37.7749, -122.4194) == True

        # New York, NY
        assert self.service._is_in_us(40.7128, -74.0060) == True

        # Mexico City (should be False)
        assert self.service._is_in_us(19.4326, -99.1332) == False

        # Toronto, Canada (should be False)
        assert self.service._is_in_us(43.6532, -79.3832) == False

    def test_is_in_us_alaska(self):
        """Test Alaska boundary detection"""
        # Anchorage, AK
        assert self.service._is_in_us(61.2181, -149.9003) == True

        # Fairbanks, AK
        assert self.service._is_in_us(64.8378, -147.7164) == True

        # Outside Alaska
        assert self.service._is_in_us(80.0, -150.0) == False

    def test_is_in_us_hawaii(self):
        """Test Hawaii boundary detection"""
        # Honolulu, HI
        assert self.service._is_in_us(21.3099, -157.8581) == True

        # Hilo, HI
        assert self.service._is_in_us(19.7216, -155.0844) == True

        # Outside Hawaii
        assert self.service._is_in_us(15.0, -157.0) == False

    def test_parse_timestamp(self):
        """Test timestamp parsing from milliseconds"""
        # Test valid timestamp (2024-01-01 00:00:00 UTC)
        test_ms = 1704067200000  # 2024-01-01 00:00:00 UTC in milliseconds

        result = self.service._parse_timestamp(test_ms)

        # Should return ISO format with timezone
        assert result.endswith('+00:00') or result.endswith('Z')
        assert '2024' in result

    def test_parse_timestamp_invalid(self):
        """Test timestamp parsing with invalid data"""
        # Should not crash, should return current time
        result = self.service._parse_timestamp(None)
        assert result is not None
        assert isinstance(result, str)

    def test_parse_usgs_geojson_valid_earthquake(self):
        """Test parsing valid earthquake from GeoJSON format"""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        features = [{
            'type': 'Feature',
            'properties': {
                'mag': 5.5,
                'place': '6 miles SW of San Francisco, CA',
                'time': now_ms,
                'id': 'nc73654321',
                'type': 'earthquake',
                'status': 'reviewed',
                'tsunami': 0,
                'felt': 150,
                'sig': 500
            },
            'geometry': {
                'type': 'Point',
                'coordinates': [-122.4194, 37.7749, 10.5]  # lon, lat, depth
            }
        }]

        result = self.service._parse_usgs_geojson(features, days_filter=7)

        assert len(result) == 1
        earthquake = result[0]

        # Verify required fields
        assert earthquake['id'] == 'usgs_nc73654321'
        assert earthquake['source'] == 'usgs'
        assert earthquake['type'] == 'earthquake'
        assert earthquake['latitude'] == 37.7749
        assert earthquake['longitude'] == -122.4194
        assert earthquake['magnitude'] == 5.5
        assert earthquake['depth_km'] == 10.5
        assert earthquake['place'] == '6 miles SW of San Francisco, CA'
        assert earthquake['severity'] == 'medium'

        # Verify confidence scoring was applied
        assert 'confidence_score' in earthquake
        assert 'confidence_level' in earthquake
        assert 'confidence_breakdown' in earthquake

    def test_parse_usgs_geojson_filters_non_us(self):
        """Test that non-US earthquakes are filtered out"""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        features = [
            {
                'type': 'Feature',
                'properties': {
                    'mag': 5.5,
                    'place': 'Mexico',
                    'time': now_ms,
                    'id': 'mx12345'
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [-99.1332, 19.4326, 10.0]  # Mexico City
                }
            },
            {
                'type': 'Feature',
                'properties': {
                    'mag': 4.5,
                    'place': 'San Francisco, CA',
                    'time': now_ms,
                    'id': 'nc12345'
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [-122.4194, 37.7749, 8.0]  # San Francisco
                }
            }
        ]

        result = self.service._parse_usgs_geojson(features, days_filter=7)

        # Should only include the US earthquake
        assert len(result) == 1
        assert result[0]['place'] == 'San Francisco, CA'

    def test_parse_usgs_geojson_filters_old_data(self):
        """Test that earthquakes older than days_filter are excluded"""
        now = datetime.now(timezone.utc)
        old_time_ms = int((now - timedelta(days=10)).timestamp() * 1000)
        recent_time_ms = int((now - timedelta(hours=1)).timestamp() * 1000)

        features = [
            {
                'type': 'Feature',
                'properties': {
                    'mag': 5.0,
                    'place': 'Old earthquake',
                    'time': old_time_ms,
                    'id': 'old123'
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [-122.4194, 37.7749, 10.0]
                }
            },
            {
                'type': 'Feature',
                'properties': {
                    'mag': 4.5,
                    'place': 'Recent earthquake',
                    'time': recent_time_ms,
                    'id': 'recent123'
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [-122.4194, 37.7749, 8.0]
                }
            }
        ]

        result = self.service._parse_usgs_geojson(features, days_filter=7)

        # Should only include the recent earthquake
        assert len(result) == 1
        assert result[0]['place'] == 'Recent earthquake'

    def test_parse_usgs_geojson_filters_low_magnitude(self):
        """Test that earthquakes below 2.5 magnitude are filtered out"""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        features = [
            {
                'type': 'Feature',
                'properties': {
                    'mag': 2.0,  # Below threshold
                    'place': 'Weak earthquake',
                    'time': now_ms,
                    'id': 'weak123'
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [-122.4194, 37.7749, 10.0]
                }
            },
            {
                'type': 'Feature',
                'properties': {
                    'mag': 3.5,  # Above threshold
                    'place': 'Strong enough earthquake',
                    'time': now_ms,
                    'id': 'strong123'
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [-122.4194, 37.7749, 8.0]
                }
            }
        ]

        result = self.service._parse_usgs_geojson(features, days_filter=7)

        # Should only include magnitude 2.5+
        assert len(result) == 1
        assert result[0]['magnitude'] == 3.5

    def test_parse_usgs_geojson_handles_missing_fields(self):
        """Test that parser handles missing optional fields gracefully"""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        features = [{
            'type': 'Feature',
            'properties': {
                'mag': 4.0,
                'place': 'Minimal data earthquake',
                'time': now_ms,
                'id': 'minimal123'
                # Missing: type, status, tsunami, felt, sig
            },
            'geometry': {
                'type': 'Point',
                'coordinates': [-122.4194, 37.7749, 10.0]
            }
        }]

        result = self.service._parse_usgs_geojson(features, days_filter=7)

        assert len(result) == 1
        earthquake = result[0]

        # Should have defaults for missing fields
        assert earthquake['event_type'] == 'earthquake'
        assert earthquake['status'] == 'automatic'
        assert earthquake['tsunami'] == 0
        assert earthquake['felt_reports'] is None
        assert earthquake['significance'] is None

    def test_parse_usgs_geojson_handles_invalid_coordinates(self):
        """Test that parser skips earthquakes with invalid coordinates"""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        features = [
            {
                'type': 'Feature',
                'properties': {
                    'mag': 5.0,
                    'place': 'Invalid coordinates',
                    'time': now_ms,
                    'id': 'invalid123'
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': []  # Missing coordinates
                }
            },
            {
                'type': 'Feature',
                'properties': {
                    'mag': 4.5,
                    'place': 'Valid earthquake',
                    'time': now_ms,
                    'id': 'valid123'
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [-122.4194, 37.7749, 10.0]
                }
            }
        ]

        result = self.service._parse_usgs_geojson(features, days_filter=7)

        # Should only include the valid one
        assert len(result) == 1
        assert result[0]['place'] == 'Valid earthquake'

    def test_earthquake_confidence_scoring(self):
        """Test that earthquakes receive high confidence scores"""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        features = [{
            'type': 'Feature',
            'properties': {
                'mag': 5.5,
                'place': 'San Francisco, CA',
                'time': now_ms,
                'id': 'nc12345',
                'type': 'earthquake',
                'status': 'reviewed'
            },
            'geometry': {
                'type': 'Point',
                'coordinates': [-122.4194, 37.7749, 10.0]
            }
        }]

        result = self.service._parse_usgs_geojson(features, days_filter=7)
        earthquake = result[0]

        # USGS earthquakes should have high confidence (seismometer-verified)
        assert earthquake['confidence_score'] >= 0.95
        assert earthquake['confidence_level'] == 'High'
        assert 'source_credibility' in earthquake['confidence_breakdown']

    @patch('requests.get')
    def test_get_us_earthquakes_success(self, mock_get):
        """Test successful earthquake fetch from USGS API"""
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'type': 'FeatureCollection',
            'features': [{
                'type': 'Feature',
                'properties': {
                    'mag': 5.5,
                    'place': '6 miles SW of San Francisco, CA',
                    'time': now_ms,
                    'id': 'nc73654321',
                    'type': 'earthquake'
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [-122.4194, 37.7749, 10.5]
                }
            }]
        }
        mock_get.return_value = mock_response

        result = self.service.get_us_earthquakes(days=7)

        assert len(result) == 1
        assert result[0]['magnitude'] == 5.5
        assert result[0]['place'] == '6 miles SW of San Francisco, CA'

    @patch('requests.get')
    def test_get_us_earthquakes_api_error(self, mock_get):
        """Test graceful handling of API errors"""
        mock_get.side_effect = Exception("API unavailable")

        result = self.service.get_us_earthquakes(days=7)

        # Should return empty list on error, not crash
        assert result == []

    def test_get_us_earthquakes_feed_selection(self):
        """Test that correct USGS feed is selected based on days parameter"""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'type': 'FeatureCollection', 'features': []}
            mock_get.return_value = mock_response

            # Test 1 day -> day feed
            self.service.get_us_earthquakes(days=1)
            assert '2.5_day.geojson' in mock_get.call_args[0][0]

            # Test 7 days -> week feed
            self.service.get_us_earthquakes(days=7)
            assert '2.5_week.geojson' in mock_get.call_args[0][0]

            # Test 30 days -> month feed
            self.service.get_us_earthquakes(days=30)
            assert '2.5_month.geojson' in mock_get.call_args[0][0]


class TestUSGSIntegrationWithConfidenceScorer:
    """Integration tests for USGS service with confidence scorer"""

    def setup_method(self):
        """Setup test fixtures"""
        self.scorer = ConfidenceScorer()
        self.service = USGSEarthquakeService(confidence_scorer=self.scorer)

    def test_usgs_earthquake_base_confidence(self):
        """Test that USGS earthquakes get expected confidence score"""
        earthquake = {
            'source': 'usgs',
            'type': 'earthquake',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'magnitude': 5.5,
            'depth_km': 10.0,
            'place': 'San Francisco, CA',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        result = self.scorer.calculate_confidence(earthquake)

        # USGS is official source, should get high confidence
        assert result['confidence_level'] == 'High'
        assert result['confidence_score'] >= 0.90
        assert 'source_credibility' in result['breakdown']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
