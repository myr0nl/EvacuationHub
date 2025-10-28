"""
API Integration Tests for Time Decay Functionality

Tests the GET /api/reports endpoint with time decay metadata and filtering.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from app import app


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_reports_data():
    """Mock reports data with various ages"""
    now = datetime.now(timezone.utc)

    return {
        'report1_fresh': {
            'latitude': 37.7749,
            'longitude': -122.4194,
            'type': 'earthquake',
            'severity': 'high',
            'timestamp': (now - timedelta(minutes=30)).isoformat(),
            'source': 'user_report',
            'confidence_score': 0.85
        },
        'report2_recent': {
            'latitude': 34.0522,
            'longitude': -118.2437,
            'type': 'wildfire',
            'severity': 'critical',
            'timestamp': (now - timedelta(hours=3)).isoformat(),
            'source': 'user_report',
            'confidence_score': 0.92
        },
        'report3_old': {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'type': 'flood',
            'severity': 'medium',
            'timestamp': (now - timedelta(hours=12)).isoformat(),
            'source': 'user_report',
            'confidence_score': 0.78
        },
        'report4_stale': {
            'latitude': 41.8781,
            'longitude': -87.6298,
            'type': 'tornado',
            'severity': 'high',
            'timestamp': (now - timedelta(hours=36)).isoformat(),
            'source': 'user_report',
            'confidence_score': 0.88
        },
        'report5_very_stale': {
            'latitude': 33.4484,
            'longitude': -112.0740,
            'type': 'drought',
            'severity': 'low',
            'timestamp': (now - timedelta(hours=72)).isoformat(),
            'source': 'user_report',
            'confidence_score': 0.65
        },
        'report6_no_timestamp': {
            'latitude': 39.7392,
            'longitude': -104.9903,
            'type': 'wildfire',
            'severity': 'medium',
            # No timestamp field
            'source': 'user_report',
            'confidence_score': 0.75
        }
    }


class TestGetReportsWithTimeDecay:
    """Test GET /api/reports endpoint with time decay metadata"""

    @patch('app.db')
    def test_get_reports_includes_time_decay(self, mock_db, client, mock_reports_data):
        """Test that all reports include time_decay metadata"""
        # Mock Firebase response
        mock_ref = Mock()
        mock_ref.get.return_value = mock_reports_data
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports')

        assert response.status_code == 200
        reports = response.get_json()

        assert isinstance(reports, list)
        assert len(reports) == 6

        # Check that all reports have time_decay field
        for report in reports:
            assert 'time_decay' in report
            assert 'age_hours' in report['time_decay']
            assert 'age_category' in report['time_decay']
            assert 'decay_score' in report['time_decay']

    @patch('app.db')
    def test_get_reports_fresh_category(self, mock_db, client, mock_reports_data):
        """Test that fresh reports (<1h) are categorized correctly"""
        mock_ref = Mock()
        mock_ref.get.return_value = mock_reports_data
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports')
        reports = response.get_json()

        # Find the fresh report (report1_fresh - 30 minutes old)
        fresh_report = next(r for r in reports if r['id'] == 'report1_fresh')

        assert fresh_report['time_decay']['age_category'] == 'fresh'
        assert fresh_report['time_decay']['decay_score'] == 1.0
        assert 0.4 <= fresh_report['time_decay']['age_hours'] <= 0.6

    @patch('app.db')
    def test_get_reports_recent_category(self, mock_db, client, mock_reports_data):
        """Test that recent reports (1-6h) are categorized correctly"""
        mock_ref = Mock()
        mock_ref.get.return_value = mock_reports_data
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports')
        reports = response.get_json()

        # Find the recent report (report2_recent - 3 hours old)
        recent_report = next(r for r in reports if r['id'] == 'report2_recent')

        assert recent_report['time_decay']['age_category'] == 'recent'
        assert recent_report['time_decay']['decay_score'] == 0.8
        assert 2.9 <= recent_report['time_decay']['age_hours'] <= 3.1

    @patch('app.db')
    def test_get_reports_old_category(self, mock_db, client, mock_reports_data):
        """Test that old reports (6-24h) are categorized correctly"""
        mock_ref = Mock()
        mock_ref.get.return_value = mock_reports_data
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports')
        reports = response.get_json()

        # Find the old report (report3_old - 12 hours old)
        old_report = next(r for r in reports if r['id'] == 'report3_old')

        assert old_report['time_decay']['age_category'] == 'old'
        assert old_report['time_decay']['decay_score'] == 0.6
        assert 11.9 <= old_report['time_decay']['age_hours'] <= 12.1

    @patch('app.db')
    def test_get_reports_stale_category(self, mock_db, client, mock_reports_data):
        """Test that stale reports (24-48h) are categorized correctly"""
        mock_ref = Mock()
        mock_ref.get.return_value = mock_reports_data
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports')
        reports = response.get_json()

        # Find the stale report (report4_stale - 36 hours old)
        stale_report = next(r for r in reports if r['id'] == 'report4_stale')

        assert stale_report['time_decay']['age_category'] == 'stale'
        assert stale_report['time_decay']['decay_score'] == 0.4
        assert 35.9 <= stale_report['time_decay']['age_hours'] <= 36.1

    @patch('app.db')
    def test_get_reports_very_stale_category(self, mock_db, client, mock_reports_data):
        """Test that very stale reports (>48h) are categorized correctly"""
        mock_ref = Mock()
        mock_ref.get.return_value = mock_reports_data
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports')
        reports = response.get_json()

        # Find the very stale report (report5_very_stale - 72 hours old)
        very_stale_report = next(r for r in reports if r['id'] == 'report5_very_stale')

        assert very_stale_report['time_decay']['age_category'] == 'very_stale'
        assert very_stale_report['time_decay']['decay_score'] == 0.2
        assert 71.9 <= very_stale_report['time_decay']['age_hours'] <= 72.1

    @patch('app.db')
    def test_get_reports_missing_timestamp(self, mock_db, client, mock_reports_data):
        """Test graceful handling of reports without timestamps"""
        mock_ref = Mock()
        mock_ref.get.return_value = mock_reports_data
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports')
        reports = response.get_json()

        # Find report without timestamp
        no_timestamp_report = next(r for r in reports if r['id'] == 'report6_no_timestamp')

        assert no_timestamp_report['time_decay']['age_hours'] is None
        assert no_timestamp_report['time_decay']['age_category'] == 'unknown'
        assert no_timestamp_report['time_decay']['decay_score'] == 0.5


class TestAgeFiltering:
    """Test age-based filtering with max_age_hours parameter"""

    @patch('app.db')
    def test_filter_by_24_hours(self, mock_db, client, mock_reports_data):
        """Test filtering to only show reports from last 24 hours"""
        mock_ref = Mock()
        mock_ref.get.return_value = mock_reports_data
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports?max_age_hours=24')

        assert response.status_code == 200
        reports = response.get_json()

        # Should include: fresh (0.5h), recent (3h), old (12h)
        # Should exclude: stale (36h), very_stale (72h)
        # Unknown timestamp: included (not filtered)
        assert len(reports) == 4

        report_ids = {r['id'] for r in reports}
        assert 'report1_fresh' in report_ids
        assert 'report2_recent' in report_ids
        assert 'report3_old' in report_ids
        assert 'report6_no_timestamp' in report_ids
        assert 'report4_stale' not in report_ids
        assert 'report5_very_stale' not in report_ids

    @patch('app.db')
    def test_filter_by_48_hours(self, mock_db, client, mock_reports_data):
        """Test filtering to only show reports from last 48 hours"""
        mock_ref = Mock()
        mock_ref.get.return_value = mock_reports_data
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports?max_age_hours=48')

        assert response.status_code == 200
        reports = response.get_json()

        # Should include: fresh, recent, old, stale (36h is within 48h)
        # Should exclude: very_stale (72h)
        # Unknown timestamp: included
        assert len(reports) == 5

        report_ids = {r['id'] for r in reports}
        assert 'report1_fresh' in report_ids
        assert 'report2_recent' in report_ids
        assert 'report3_old' in report_ids
        assert 'report4_stale' in report_ids
        assert 'report6_no_timestamp' in report_ids
        assert 'report5_very_stale' not in report_ids

    @patch('app.db')
    def test_filter_by_1_hour(self, mock_db, client, mock_reports_data):
        """Test filtering to only show reports from last 1 hour"""
        mock_ref = Mock()
        mock_ref.get.return_value = mock_reports_data
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports?max_age_hours=1')

        assert response.status_code == 200
        reports = response.get_json()

        # Should include: fresh (0.5h)
        # Unknown timestamp: included
        assert len(reports) == 2

        report_ids = {r['id'] for r in reports}
        assert 'report1_fresh' in report_ids
        assert 'report6_no_timestamp' in report_ids

    @patch('app.db')
    def test_no_filter_when_parameter_missing(self, mock_db, client, mock_reports_data):
        """Test that all reports are returned when max_age_hours is not provided"""
        mock_ref = Mock()
        mock_ref.get.return_value = mock_reports_data
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports')

        assert response.status_code == 200
        reports = response.get_json()

        # Should include all reports
        assert len(reports) == 6

    @patch('app.db')
    def test_filter_with_very_large_age(self, mock_db, client, mock_reports_data):
        """Test filtering with very large max_age_hours (all reports included)"""
        mock_ref = Mock()
        mock_ref.get.return_value = mock_reports_data
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports?max_age_hours=1000')

        assert response.status_code == 200
        reports = response.get_json()

        # All reports should be included
        assert len(reports) == 6


class TestParameterValidation:
    """Test validation of max_age_hours parameter"""

    @patch('app.db')
    def test_negative_max_age_hours(self, mock_db, client):
        """Test that negative max_age_hours is rejected"""
        mock_ref = Mock()
        mock_ref.get.return_value = {}
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports?max_age_hours=-10')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'non-negative' in data['error'].lower()

    @patch('app.db')
    def test_excessive_max_age_hours(self, mock_db, client):
        """Test that excessively large max_age_hours is rejected"""
        mock_ref = Mock()
        mock_ref.get.return_value = {}
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports?max_age_hours=10000')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert '8760' in data['error']  # 1 year limit

    @patch('app.db')
    def test_valid_max_age_hours_accepted(self, mock_db, client):
        """Test that valid max_age_hours values are accepted"""
        mock_ref = Mock()
        mock_ref.get.return_value = {}
        mock_db.reference.return_value = mock_ref

        # Test various valid values
        for hours in [0, 1, 24, 48, 72, 168, 720, 8760]:
            response = client.get(f'/api/reports?max_age_hours={hours}')
            assert response.status_code == 200

    @patch('app.db')
    def test_invalid_max_age_hours_type(self, mock_db, client):
        """Test that non-numeric max_age_hours is handled gracefully"""
        mock_ref = Mock()
        mock_ref.get.return_value = {}
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports?max_age_hours=invalid')

        # Flask's type converter returns None for invalid floats
        # This is treated as "no filter" (returns 200)
        assert response.status_code == 200


class TestBackwardsCompatibility:
    """Test backwards compatibility with existing reports"""

    @patch('app.db')
    def test_legacy_disaster_type_field(self, mock_db, client):
        """Test handling of legacy disaster_type field"""
        mock_ref = Mock()
        mock_ref.get.return_value = {
            'legacy_report': {
                'latitude': 37.7749,
                'longitude': -122.4194,
                'disaster_type': 'earthquake',  # Old field name
                'severity': 'high',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'source': 'user_report'
            }
        }
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports')

        assert response.status_code == 200
        reports = response.get_json()

        assert len(reports) == 1
        assert reports[0]['type'] == 'earthquake'
        assert 'time_decay' in reports[0]

    @patch('app.db')
    def test_empty_reports_database(self, mock_db, client):
        """Test handling of empty reports database"""
        mock_ref = Mock()
        mock_ref.get.return_value = None
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports')

        assert response.status_code == 200
        reports = response.get_json()
        assert reports == []

    @patch('app.db')
    def test_reports_with_all_fields(self, mock_db, client):
        """Test that all existing fields are preserved when adding time_decay"""
        now = datetime.now(timezone.utc)
        mock_ref = Mock()
        mock_ref.get.return_value = {
            'full_report': {
                'latitude': 37.7749,
                'longitude': -122.4194,
                'type': 'earthquake',
                'severity': 'high',
                'timestamp': now.isoformat(),
                'source': 'user_report',
                'confidence_score': 0.85,
                'confidence_level': 'High',
                'confidence_breakdown': {},
                'description': 'Test description',
                'image_url': 'https://example.com/image.jpg',
                'location_name': 'San Francisco, CA'
            }
        }
        mock_db.reference.return_value = mock_ref

        response = client.get('/api/reports')

        assert response.status_code == 200
        reports = response.get_json()

        assert len(reports) == 1
        report = reports[0]

        # Check all original fields are preserved
        assert report['latitude'] == 37.7749
        assert report['longitude'] == -122.4194
        assert report['type'] == 'earthquake'
        assert report['severity'] == 'high'
        assert report['confidence_score'] == 0.85
        assert report['description'] == 'Test description'
        assert report['location_name'] == 'San Francisco, CA'

        # Check time_decay is added
        assert 'time_decay' in report
        assert report['time_decay']['age_category'] == 'fresh'
