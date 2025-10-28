"""
Unit tests for Cal OES Service
Tests RSS feed parsing, caching, and alert classification
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import feedparser
from services.cal_oes_service import CalOESService


class TestCalOESService:
    """Test suite for CalOESService"""

    @pytest.fixture
    def mock_confidence_scorer(self):
        """Create mock confidence scorer"""
        scorer = Mock()
        scorer.calculate_confidence.return_value = {
            'confidence_score': 0.95,
            'confidence_level': 'High',
            'breakdown': {
                'source': 'cal_oes',
                'official_source': True
            }
        }
        return scorer

    @pytest.fixture
    def cal_oes_service(self, mock_confidence_scorer):
        """Create CalOESService instance with mock scorer"""
        return CalOESService(confidence_scorer=mock_confidence_scorer)

    @pytest.fixture
    def mock_rss_feed(self):
        """Create mock RSS feed data"""
        mock_feed = {
            'bozo': False,
            'entries': [
                {
                    'title': 'Wildfire Emergency in Northern California',
                    'summary': 'Critical wildfire threatening communities in Shasta County. Evacuation orders issued.',
                    'link': 'https://news.caloes.ca.gov/wildfire-alert-123',
                    'published_parsed': (2024, 1, 15, 10, 30, 0, 0, 0, 0),
                },
                {
                    'title': 'Earthquake Advisory for Bay Area',
                    'summary': 'Moderate earthquake detected near San Francisco. Monitor for aftershocks.',
                    'link': 'https://news.caloes.ca.gov/earthquake-alert-124',
                    'published_parsed': (2024, 1, 15, 11, 0, 0, 0, 0),
                },
                {
                    'title': 'Flood Watch Issued for Sacramento Valley',
                    'summary': 'Minor flood watch due to heavy rainfall expected.',
                    'link': 'https://news.caloes.ca.gov/flood-alert-125',
                    'published_parsed': (2024, 1, 15, 12, 0, 0, 0, 0),
                }
            ]
        }
        return mock_feed

    def test_service_initialization(self):
        """Test CalOESService initializes correctly"""
        service = CalOESService()
        assert service.RSS_FEED_URL == "https://news.caloes.ca.gov/feed"
        assert service.CACHE_TYPE == "cal_oes_alerts"
        assert service.confidence_scorer is not None

    def test_service_initialization_with_scorer(self, mock_confidence_scorer):
        """Test CalOESService initialization with custom scorer"""
        service = CalOESService(confidence_scorer=mock_confidence_scorer)
        assert service.confidence_scorer == mock_confidence_scorer

    @patch('services.cal_oes_service.feedparser.parse')
    def test_fetch_recent_alerts_success(self, mock_parse, cal_oes_service, mock_rss_feed):
        """Test successful RSS feed fetch and parsing"""
        mock_parse.return_value = mock_rss_feed

        alerts = cal_oes_service.fetch_recent_alerts()

        assert len(alerts) == 3
        assert all('id' in alert for alert in alerts)
        assert all('source' in alert for alert in alerts)
        assert all(alert['source'] == 'cal_oes' for alert in alerts)
        assert all('confidence_score' in alert for alert in alerts)

    @patch('services.cal_oes_service.feedparser.parse')
    def test_fetch_recent_alerts_network_error(self, mock_parse, cal_oes_service):
        """Test handling of network errors during fetch"""
        mock_parse.side_effect = Exception("Network error")

        alerts = cal_oes_service.fetch_recent_alerts()

        assert alerts == []

    def test_parse_rss_feed_with_entries(self, cal_oes_service, mock_rss_feed):
        """Test RSS feed parsing with valid entries"""
        alerts = cal_oes_service._parse_rss_feed(mock_rss_feed)

        assert len(alerts) == 3
        assert alerts[0]['title'] == 'Wildfire Emergency in Northern California'
        assert alerts[1]['title'] == 'Earthquake Advisory for Bay Area'
        assert alerts[2]['title'] == 'Flood Watch Issued for Sacramento Valley'

    def test_parse_rss_feed_empty(self, cal_oes_service):
        """Test RSS feed parsing with empty feed"""
        empty_feed = {'entries': []}
        alerts = cal_oes_service._parse_rss_feed(empty_feed)

        assert alerts == []

    def test_classify_alert_wildfire(self, cal_oes_service):
        """Test alert classification for wildfire"""
        title = "Critical Wildfire Emergency"
        description = "Severe wildfire spreading rapidly"

        alert_type, severity = cal_oes_service._classify_alert(title, description)

        assert alert_type == 'wildfire'
        assert severity == 'critical'

    def test_classify_alert_earthquake(self, cal_oes_service):
        """Test alert classification for earthquake"""
        title = "Earthquake Advisory"
        description = "Moderate seismic activity detected"

        alert_type, severity = cal_oes_service._classify_alert(title, description)

        assert alert_type == 'earthquake'
        assert severity == 'medium'

    def test_classify_alert_flood(self, cal_oes_service):
        """Test alert classification for flood"""
        title = "Flood Warning"
        description = "Severe flooding expected in low-lying areas"

        alert_type, severity = cal_oes_service._classify_alert(title, description)

        assert alert_type == 'flood'
        assert severity == 'high'

    def test_classify_alert_storm(self, cal_oes_service):
        """Test alert classification for storm"""
        title = "Hurricane Warning"
        description = "Extreme storm conditions approaching coast"

        alert_type, severity = cal_oes_service._classify_alert(title, description)

        assert alert_type == 'storm'
        assert severity == 'critical'

    def test_classify_alert_default(self, cal_oes_service):
        """Test alert classification with no specific keywords"""
        title = "General Alert"
        description = "Public safety announcement"

        alert_type, severity = cal_oes_service._classify_alert(title, description)

        assert alert_type == 'emergency'
        assert severity == 'medium'

    def test_generate_id_hash(self, cal_oes_service):
        """Test ID hash generation"""
        text = "https://news.caloes.ca.gov/alert-123"
        hash_id = cal_oes_service._generate_id_hash(text)

        assert isinstance(hash_id, str)
        assert len(hash_id) == 12
        # Same input should produce same hash
        assert hash_id == cal_oes_service._generate_id_hash(text)

    def test_generate_id_hash_empty(self, cal_oes_service):
        """Test ID hash generation with empty string"""
        hash_id = cal_oes_service._generate_id_hash("")

        assert isinstance(hash_id, str)
        assert len(hash_id) == 12

    def test_parse_pub_date_published(self, cal_oes_service):
        """Test publication date parsing from published_parsed"""
        entry = Mock()
        entry.published_parsed = (2024, 1, 15, 10, 30, 0, 0, 0, 0)

        pub_date = cal_oes_service._parse_pub_date(entry)

        assert isinstance(pub_date, str)
        assert '2024-01-15' in pub_date
        assert '10:30:00' in pub_date

    def test_parse_pub_date_fallback(self, cal_oes_service):
        """Test publication date parsing fallback to current time"""
        entry = Mock()
        del entry.published_parsed
        del entry.updated_parsed

        pub_date = cal_oes_service._parse_pub_date(entry)

        assert isinstance(pub_date, str)
        # Should be recent timestamp
        parsed_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
        assert (datetime.now(timezone.utc) - parsed_date).total_seconds() < 5

    def test_extract_coordinates_default(self, cal_oes_service):
        """Test coordinate extraction defaults to California center"""
        entry = Mock()
        del entry.geo_lat
        del entry.geo_long
        del entry.georss_point

        lat, lon = cal_oes_service._extract_coordinates(entry, "Test", "Test description")

        # Should default to California geographic center
        assert lat == 37.0
        assert lon == -119.5

    def test_extract_coordinates_geo_tags(self, cal_oes_service):
        """Test coordinate extraction from geo tags"""
        entry = Mock()
        entry.geo_lat = "34.0522"
        entry.geo_long = "-118.2437"

        lat, lon = cal_oes_service._extract_coordinates(entry, "Test", "Test")

        assert lat == 34.0522
        assert lon == -118.2437

    def test_is_california_location_valid(self, cal_oes_service):
        """Test California location validation for valid coordinates"""
        # Los Angeles
        assert cal_oes_service._is_california_location(34.0522, -118.2437)
        # San Francisco
        assert cal_oes_service._is_california_location(37.7749, -122.4194)
        # Sacramento
        assert cal_oes_service._is_california_location(38.5816, -121.4944)

    def test_is_california_location_invalid(self, cal_oes_service):
        """Test California location validation for invalid coordinates"""
        # Nevada
        assert not cal_oes_service._is_california_location(36.1699, -115.1398)
        # Oregon
        assert not cal_oes_service._is_california_location(45.5152, -122.6784)
        # Mexico
        assert not cal_oes_service._is_california_location(32.5027, -117.0039)

    def test_confidence_scoring_applied(self, cal_oes_service, mock_rss_feed, mock_confidence_scorer):
        """Test that confidence scoring is applied to all alerts"""
        alerts = cal_oes_service._parse_rss_feed(mock_rss_feed)

        assert all('confidence_score' in alert for alert in alerts)
        assert all(alert['confidence_score'] == 0.95 for alert in alerts)
        assert all(alert['confidence_level'] == 'High' for alert in alerts)
        # Verify scorer was called for each alert
        assert mock_confidence_scorer.calculate_confidence.call_count == 3

    def test_confidence_scoring_fallback_on_error(self, mock_confidence_scorer):
        """Test confidence scoring fallback when scorer fails"""
        mock_confidence_scorer.calculate_confidence.side_effect = Exception("Scoring error")
        service = CalOESService(confidence_scorer=mock_confidence_scorer)

        mock_feed = {
            'entries': [
                {
                    'title': 'Test Alert',
                    'summary': 'Test description',
                    'link': 'https://test.com',
                    'published_parsed': (2024, 1, 15, 10, 0, 0, 0, 0, 0)
                }
            ]
        }

        alerts = service._parse_rss_feed(mock_feed)

        # Should still have confidence score (fallback to 0.95)
        assert len(alerts) == 1
        assert alerts[0]['confidence_score'] == 0.95
        assert alerts[0]['confidence_level'] == 'High'
        assert 'error_fallback' in alerts[0]['confidence_breakdown']

    @patch('services.cal_oes_service.CacheManager')
    @patch('services.cal_oes_service.feedparser.parse')
    def test_get_cached_alerts_cache_hit(self, mock_parse, mock_cache_manager, cal_oes_service):
        """Test get_cached_alerts returns cached data when cache is fresh"""
        mock_cache_manager.should_update.return_value = False
        cached_data = [{'id': 'test1', 'title': 'Cached Alert'}]
        mock_cache_manager.get_cached_data.return_value = cached_data

        result = cal_oes_service.get_cached_alerts()

        assert result == cached_data
        mock_cache_manager.should_update.assert_called_once_with('cal_oes_alerts')
        mock_parse.assert_not_called()  # Should not fetch fresh data

    @patch('services.cal_oes_service.CacheManager')
    @patch('services.cal_oes_service.feedparser.parse')
    def test_get_cached_alerts_cache_miss(self, mock_parse, mock_cache_manager, cal_oes_service, mock_rss_feed):
        """Test get_cached_alerts fetches fresh data when cache is stale"""
        mock_cache_manager.should_update.return_value = True
        mock_parse.return_value = mock_rss_feed

        result = cal_oes_service.get_cached_alerts()

        assert len(result) == 3
        mock_cache_manager.should_update.assert_called_once_with('cal_oes_alerts')
        mock_cache_manager.update_cache.assert_called_once()
        mock_parse.assert_called_once()

    def test_alert_structure(self, cal_oes_service, mock_rss_feed):
        """Test that parsed alerts have correct structure"""
        alerts = cal_oes_service._parse_rss_feed(mock_rss_feed)

        required_fields = [
            'id', 'source', 'type', 'title', 'description',
            'pub_date', 'link', 'timestamp', 'latitude',
            'longitude', 'severity', 'confidence_score',
            'confidence_level', 'confidence_breakdown'
        ]

        for alert in alerts:
            for field in required_fields:
                assert field in alert, f"Alert missing required field: {field}"
            assert alert['source'] == 'cal_oes'
            assert alert['id'].startswith('caloes_')
