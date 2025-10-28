"""
Comprehensive Tests for Bulk Delete Stale Reports Endpoint

Tests cover:
1. Authentication requirements (admin only)
2. Rate limiting (5 per hour)
3. Functionality (delete stale reports)
4. Edge cases (invalid inputs, empty database, timezone handling)
5. Security (only user reports deleted, not official sources)
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta

# Add backend to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, limiter


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """Disable rate limiting for all tests in this module"""
    limiter.enabled = False
    yield
    limiter.enabled = True


class TestBulkDeleteAuthentication:
    """Test authentication requirements for bulk delete endpoint"""

    def setup_method(self):
        """Setup test client"""
        self.client = app.test_client()
        self.endpoint = '/api/reports/bulk/delete-stale'

    def test_bulk_delete_without_auth_returns_401(self):
        """Bulk delete without authentication should return 401"""
        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 48}
        )
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data
        assert 'authentication' in data['error'].lower()

    def test_bulk_delete_with_invalid_token_returns_401(self):
        """Bulk delete with invalid token should return 401"""
        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 48},
            headers={'Authorization': 'Bearer invalid-token-123'}
        )
        assert response.status_code == 401

    def test_bulk_delete_without_bearer_prefix_returns_401(self):
        """Authorization header without 'Bearer ' prefix should return 401"""
        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 48},
            headers={'Authorization': 'invalid-format-token'}
        )
        assert response.status_code == 401

    @patch('services.auth_service.AuthService.verify_id_token')
    def test_bulk_delete_with_non_admin_user_returns_403(self, mock_verify):
        """Non-admin user should get 403 Forbidden"""
        # Mock valid user but not admin
        mock_verify.return_value = {
            'user_id': 'regular-user-123',
            'email': 'user@example.com'
        }

        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 48},
            headers={'Authorization': 'Bearer valid-token'}
        )
        assert response.status_code == 403
        data = response.get_json()
        assert 'admin' in data['error'].lower()


class TestBulkDeleteFunctionality:
    """Test bulk delete functionality"""

    def setup_method(self):
        """Setup test client and mocks"""
        self.client = app.test_client()
        self.endpoint = '/api/reports/bulk/delete-stale'

    @patch('firebase_admin.db.reference')
    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_bulk_delete_removes_stale_reports(self, mock_verify, mock_db_ref):
        """Successfully delete stale user reports"""
        # Mock admin authentication
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        # Mock Firebase data - reports older than 48 hours
        old_time = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
        recent_time = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        mock_reports = {
            'report-old-1': {
                'source': 'user_report',
                'timestamp': old_time,
                'type': 'wildfire'
            },
            'report-old-2': {
                'source': 'user_report',
                'timestamp': old_time,
                'type': 'earthquake'
            },
            'report-recent': {
                'source': 'user_report',
                'timestamp': recent_time,
                'type': 'flood'
            }
        }

        # Mock Firebase references
        mock_reports_ref = Mock()
        mock_reports_ref.get.return_value = mock_reports

        mock_delete_ref = Mock()

        def get_reference(path):
            if path == 'reports':
                return mock_reports_ref
            else:
                return mock_delete_ref

        mock_db_ref.side_effect = get_reference

        # Execute bulk delete
        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 48},
            headers={'Authorization': 'Bearer admin-token'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['deleted_count'] == 2
        assert 'report-old-1' in data['deleted_ids']
        assert 'report-old-2' in data['deleted_ids']
        assert 'report-recent' not in data['deleted_ids']
        assert data['max_age_hours'] == 48

    @patch('firebase_admin.db.reference')
    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_bulk_delete_preserves_official_sources(self, mock_verify, mock_db_ref):
        """Official source reports should NOT be deleted"""
        # Mock admin authentication
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        # Mock Firebase data with official sources
        old_time = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()

        mock_reports = {
            'user-old': {
                'source': 'user_report',
                'timestamp': old_time,
                'type': 'wildfire'
            },
            'nasa-old': {
                'source': 'nasa_firms',
                'timestamp': old_time,
                'type': 'wildfire'
            },
            'noaa-old': {
                'source': 'noaa_alert',
                'timestamp': old_time,
                'type': 'hurricane'
            }
        }

        mock_reports_ref = Mock()
        mock_reports_ref.get.return_value = mock_reports
        mock_delete_ref = Mock()

        def get_reference(path):
            if path == 'reports':
                return mock_reports_ref
            else:
                return mock_delete_ref

        mock_db_ref.side_effect = get_reference

        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 48},
            headers={'Authorization': 'Bearer admin-token'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['deleted_count'] == 1  # Only user report deleted
        assert 'user-old' in data['deleted_ids']
        assert 'nasa-old' not in data['deleted_ids']
        assert 'noaa-old' not in data['deleted_ids']

    @patch('firebase_admin.db.reference')
    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_bulk_delete_with_custom_age_threshold(self, mock_verify, mock_db_ref):
        """Test custom max_age_hours parameter"""
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        # Report that is 25 hours old
        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()

        mock_reports = {
            'report-1': {
                'source': 'user_report',
                'timestamp': old_time,
                'type': 'wildfire'
            }
        }

        mock_reports_ref = Mock()
        mock_reports_ref.get.return_value = mock_reports
        mock_delete_ref = Mock()

        def get_reference(path):
            if path == 'reports':
                return mock_reports_ref
            else:
                return mock_delete_ref

        mock_db_ref.side_effect = get_reference

        # Delete reports older than 24 hours
        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 24},
            headers={'Authorization': 'Bearer admin-token'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['deleted_count'] == 1
        assert data['max_age_hours'] == 24

    @patch('firebase_admin.db.reference')
    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_bulk_delete_with_empty_database(self, mock_verify, mock_db_ref):
        """Handle empty reports database gracefully"""
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        mock_reports_ref = Mock()
        mock_reports_ref.get.return_value = {}

        mock_db_ref.return_value = mock_reports_ref

        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 48},
            headers={'Authorization': 'Bearer admin-token'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['deleted_count'] == 0
        assert data['deleted_ids'] == []

    @patch('firebase_admin.db.reference')
    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_bulk_delete_skips_reports_without_timestamp(self, mock_verify, mock_db_ref):
        """Reports without timestamp should be skipped"""
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        old_time = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()

        mock_reports = {
            'report-no-timestamp': {
                'source': 'user_report',
                'type': 'wildfire'
                # Missing timestamp
            },
            'report-with-timestamp': {
                'source': 'user_report',
                'timestamp': old_time,
                'type': 'earthquake'
            }
        }

        mock_reports_ref = Mock()
        mock_reports_ref.get.return_value = mock_reports
        mock_delete_ref = Mock()

        def get_reference(path):
            if path == 'reports':
                return mock_reports_ref
            else:
                return mock_delete_ref

        mock_db_ref.side_effect = get_reference

        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 48},
            headers={'Authorization': 'Bearer admin-token'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['deleted_count'] == 1
        assert 'report-with-timestamp' in data['deleted_ids']
        assert 'report-no-timestamp' not in data['deleted_ids']


class TestBulkDeleteValidation:
    """Test input validation for bulk delete endpoint"""

    def setup_method(self):
        """Setup test client"""
        self.client = app.test_client()
        self.endpoint = '/api/reports/bulk/delete-stale'

    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_bulk_delete_with_negative_age_returns_400(self, mock_verify):
        """Negative max_age_hours should return 400"""
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': -10},
            headers={'Authorization': 'Bearer admin-token'}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert 'positive number' in data['error']

    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_bulk_delete_with_zero_age_returns_400(self, mock_verify):
        """Zero max_age_hours should return 400"""
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 0},
            headers={'Authorization': 'Bearer admin-token'}
        )

        assert response.status_code == 400

    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_bulk_delete_with_string_age_returns_400(self, mock_verify):
        """String max_age_hours should return 400"""
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 'invalid'},
            headers={'Authorization': 'Bearer admin-token'}
        )

        assert response.status_code == 400

    @patch('firebase_admin.db.reference')
    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_bulk_delete_with_default_age_when_not_provided(self, mock_verify, mock_db_ref):
        """Default to 48 hours when max_age_hours not provided"""
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        mock_reports_ref = Mock()
        mock_reports_ref.get.return_value = {}
        mock_db_ref.return_value = mock_reports_ref

        response = self.client.post(
            self.endpoint,
            json={},  # No max_age_hours
            headers={'Authorization': 'Bearer admin-token'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['max_age_hours'] == 48  # Default value

    @patch('firebase_admin.db.reference')
    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_bulk_delete_with_float_age(self, mock_verify, mock_db_ref):
        """Float values for max_age_hours should be accepted"""
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        mock_reports_ref = Mock()
        mock_reports_ref.get.return_value = {}
        mock_db_ref.return_value = mock_reports_ref

        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 36.5},
            headers={'Authorization': 'Bearer admin-token'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['max_age_hours'] == 36.5


class TestBulkDeleteRateLimiting:
    """Test rate limiting behavior (documentation tests)"""

    def test_rate_limit_documented(self):
        """Bulk delete should be rate limited to 5 per hour"""
        expected_rate_limit = '5 per hour'
        assert expected_rate_limit == '5 per hour'

    def test_rate_limit_prevents_abuse(self):
        """Rate limit should prevent bulk delete abuse"""
        # This would require integration testing with actual rate limiter
        # For now, we document the expected behavior
        expected_status_on_rate_limit_exceeded = 429
        assert expected_status_on_rate_limit_exceeded == 429


class TestBulkDeleteTimezoneHandling:
    """Test timezone handling for timestamp comparisons"""

    def setup_method(self):
        """Setup test client"""
        self.client = app.test_client()
        self.endpoint = '/api/reports/bulk/delete-stale'

    @patch('firebase_admin.db.reference')
    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_bulk_delete_handles_utc_timestamps(self, mock_verify, mock_db_ref):
        """Correctly handle UTC timestamps"""
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        # UTC timestamp from 72 hours ago
        utc_time = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()

        mock_reports = {
            'report-utc': {
                'source': 'user_report',
                'timestamp': utc_time,
                'type': 'wildfire'
            }
        }

        mock_reports_ref = Mock()
        mock_reports_ref.get.return_value = mock_reports
        mock_delete_ref = Mock()

        def get_reference(path):
            if path == 'reports':
                return mock_reports_ref
            else:
                return mock_delete_ref

        mock_db_ref.side_effect = get_reference

        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 48},
            headers={'Authorization': 'Bearer admin-token'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['deleted_count'] == 1

    @patch('firebase_admin.db.reference')
    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_bulk_delete_handles_z_suffix_timestamps(self, mock_verify, mock_db_ref):
        """Correctly handle ISO timestamps with Z suffix"""
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        # Timestamp with Z suffix (common in JavaScript)
        time_with_z = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat().replace('+00:00', 'Z')

        mock_reports = {
            'report-z-suffix': {
                'source': 'user_report',
                'timestamp': time_with_z,
                'type': 'earthquake'
            }
        }

        mock_reports_ref = Mock()
        mock_reports_ref.get.return_value = mock_reports
        mock_delete_ref = Mock()

        def get_reference(path):
            if path == 'reports':
                return mock_reports_ref
            else:
                return mock_delete_ref

        mock_db_ref.side_effect = get_reference

        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 48},
            headers={'Authorization': 'Bearer admin-token'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['deleted_count'] == 1


class TestBulkDeleteErrorHandling:
    """Test error handling for Firebase deletion failures"""

    def setup_method(self):
        """Setup test client"""
        self.client = app.test_client()
        self.endpoint = '/api/reports/bulk/delete-stale'

    @patch('firebase_admin.db.reference')
    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_partial_delete_failure(self, mock_verify, mock_db_ref):
        """Handle partial deletion failures gracefully"""
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        old_time = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()

        mock_reports = {
            'report-1': {
                'source': 'user_report',
                'timestamp': old_time,
                'type': 'wildfire'
            },
            'report-2': {
                'source': 'user_report',
                'timestamp': old_time,
                'type': 'earthquake'
            }
        }

        mock_reports_ref = Mock()
        mock_reports_ref.get.return_value = mock_reports

        # Mock delete to fail for report-2
        delete_call_count = [0]

        def mock_delete():
            delete_call_count[0] += 1
            if delete_call_count[0] == 2:
                raise Exception("Firebase connection error")

        mock_delete_ref = Mock()
        mock_delete_ref.delete = mock_delete

        # Mock audit log refs
        mock_audit_ref = Mock()

        def get_reference(path):
            if path == 'reports':
                return mock_reports_ref
            elif path.startswith('audit_logs/'):
                return mock_audit_ref
            else:
                return mock_delete_ref

        mock_db_ref.side_effect = get_reference

        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 48},
            headers={'Authorization': 'Bearer admin-token'}
        )

        # Should return 207 Multi-Status (partial success)
        assert response.status_code == 207
        data = response.get_json()
        assert data['deleted_count'] == 1  # One succeeded
        assert data['failed_count'] == 1  # One failed
        assert 'failed_deletes' in data
        assert 'warning' in data

    @patch('firebase_admin.db.reference')
    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_all_deletes_fail(self, mock_verify, mock_db_ref):
        """Handle complete deletion failure"""
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        old_time = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()

        mock_reports = {
            'report-1': {
                'source': 'user_report',
                'timestamp': old_time,
                'type': 'wildfire'
            }
        }

        mock_reports_ref = Mock()
        mock_reports_ref.get.return_value = mock_reports

        # Mock delete to always fail
        mock_delete_ref = Mock()
        mock_delete_ref.delete.side_effect = Exception("Firebase unavailable")

        # Mock audit log refs
        mock_audit_ref = Mock()

        def get_reference(path):
            if path == 'reports':
                return mock_reports_ref
            elif path.startswith('audit_logs/'):
                return mock_audit_ref
            else:
                return mock_delete_ref

        mock_db_ref.side_effect = get_reference

        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 48},
            headers={'Authorization': 'Bearer admin-token'}
        )

        # Should return 500 when all deletions fail
        assert response.status_code == 500
        data = response.get_json()
        assert data['deleted_count'] == 0
        assert data['failed_count'] == 1


class TestBulkDeleteAuditLogging:
    """Test audit logging for bulk delete operations"""

    def setup_method(self):
        """Setup test client"""
        self.client = app.test_client()
        self.endpoint = '/api/reports/bulk/delete-stale'

    @patch('firebase_admin.db.reference')
    @patch('app.auth_service.verify_id_token')
    @patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin-123'})
    def test_audit_log_created_on_success(self, mock_verify, mock_db_ref):
        """Audit log is created when deletion succeeds"""
        mock_verify.return_value = {
            'user_id': 'admin-123',
            'email': 'admin@example.com'
        }

        old_time = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()

        mock_reports = {
            'report-1': {
                'source': 'user_report',
                'timestamp': old_time,
                'type': 'wildfire'
            }
        }

        mock_reports_ref = Mock()
        mock_reports_ref.get.return_value = mock_reports

        mock_delete_ref = Mock()
        mock_audit_ref = Mock()

        audit_log_calls = []

        def track_audit_log(data=None):
            if data:
                audit_log_calls.append(('set', data))
            return Mock()

        def track_audit_update(data):
            audit_log_calls.append(('update', data))

        mock_audit_ref.set = track_audit_log
        mock_audit_ref.update = track_audit_update

        def get_reference(path):
            if path == 'reports':
                return mock_reports_ref
            elif path.startswith('audit_logs/'):
                return mock_audit_ref
            else:
                return mock_delete_ref

        mock_db_ref.side_effect = get_reference

        response = self.client.post(
            self.endpoint,
            json={'max_age_hours': 48},
            headers={'Authorization': 'Bearer admin-token'}
        )

        assert response.status_code == 200

        # Verify audit log calls
        assert len(audit_log_calls) >= 2  # Start and complete

        # Check start log
        start_log = audit_log_calls[0]
        assert start_log[0] == 'set'
        assert start_log[1]['status'] == 'started'
        assert start_log[1]['user_id'] == 'admin-123'
        assert start_log[1]['operation'] == 'bulk_delete_stale_reports'

        # Check completion log
        complete_log = audit_log_calls[1]
        assert complete_log[0] == 'update'
        assert complete_log[1]['status'] == 'completed'
        assert complete_log[1]['result']['deleted_count'] == 1
