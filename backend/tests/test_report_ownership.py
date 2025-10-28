#!/usr/bin/env python3
"""
Test suite for report ownership validation

Tests the security feature that ensures users can only delete their own reports.
Covers scenarios:
1. User can delete their own report ✓
2. User cannot delete another user's report (403) ✓
3. Unauthenticated deletion attempt on owned report (401) ✓
4. Admin can delete any report (admin override) ✓
5. Legacy reports without user_id can be deleted by anyone (backward compatibility) ✓
6. Report not found (404) ✓
"""

import sys
import os
import json
from datetime import datetime, timezone
import pytest
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from services.auth_service import AuthService


@pytest.fixture
def client():
    """Create a test client for the Flask app"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_firebase_db():
    """Mock Firebase database for testing"""
    with patch('app.db') as mock_db:
        # Mock database reference structure
        mock_ref = MagicMock()
        mock_db.reference.return_value = mock_ref
        yield mock_db, mock_ref


@pytest.fixture
def mock_auth_service():
    """Mock authentication service"""
    with patch('app.auth_service') as mock_auth:
        yield mock_auth


class TestReportOwnership:
    """Test report ownership validation for DELETE endpoint"""

    def test_delete_own_report_success(self, client, mock_firebase_db, mock_auth_service):
        """Test: User can successfully delete their own report"""
        mock_db, mock_ref = mock_firebase_db

        # Setup: Report owned by user123
        mock_report = {
            'type': 'wildfire',
            'latitude': 34.0522,
            'longitude': -118.2437,
            'severity': 'high',
            'user_id': 'user123',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Mock Firebase get() to return the report
        mock_ref.get.return_value = mock_report

        # Mock auth service to verify token and return user123
        mock_auth_service.verify_id_token.return_value = {
            'user_id': 'user123',
            'email': 'user@example.com',
            'email_verified': True
        }

        # Make DELETE request with valid token
        response = client.delete(
            '/api/reports/test_report_id',
            headers={'Authorization': 'Bearer valid_token_user123'}
        )

        # Assert: Successful deletion (200)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'deleted'
        assert data['id'] == 'test_report_id'
        assert data['deleted_by'] == 'user123'

        # Verify delete was called on Firebase (twice: report + user_reports tracking)
        assert mock_ref.delete.call_count == 2

    def test_delete_other_user_report_forbidden(self, client, mock_firebase_db, mock_auth_service):
        """Test: User cannot delete another user's report (403 Forbidden)"""
        mock_db, mock_ref = mock_firebase_db

        # Setup: Report owned by user456
        mock_report = {
            'type': 'flood',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'severity': 'medium',
            'user_id': 'user456',  # Different owner
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        mock_ref.get.return_value = mock_report

        # Mock auth service to verify token and return user123 (different user)
        mock_auth_service.verify_id_token.return_value = {
            'user_id': 'user123',  # Requesting user
            'email': 'user@example.com',
            'email_verified': True
        }

        # Mock environment variable for admin list (user123 is NOT admin)
        with patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin_user_999'}):
            response = client.delete(
                '/api/reports/test_report_id',
                headers={'Authorization': 'Bearer valid_token_user123'}
            )

        # Assert: Forbidden (403)
        assert response.status_code == 403
        data = json.loads(response.data)
        assert 'Forbidden' in data['error']
        assert 'You can only delete your own reports' in data['message']

        # Verify delete was NOT called
        mock_ref.delete.assert_not_called()

    def test_delete_owned_report_unauthenticated(self, client, mock_firebase_db):
        """Test: Unauthenticated request to delete owned report (401)"""
        mock_db, mock_ref = mock_firebase_db

        # Setup: Report owned by user123
        mock_report = {
            'type': 'earthquake',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'severity': 'critical',
            'user_id': 'user123',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        mock_ref.get.return_value = mock_report

        # Make DELETE request WITHOUT Authorization header
        response = client.delete('/api/reports/test_report_id')

        # Assert: Unauthorized (401)
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Authentication required' in data['error']
        assert 'This report belongs to a user' in data['message']

        # Verify delete was NOT called
        mock_ref.delete.assert_not_called()

    def test_delete_owned_report_invalid_token(self, client, mock_firebase_db, mock_auth_service):
        """Test: Invalid token when trying to delete owned report (401)"""
        mock_db, mock_ref = mock_firebase_db

        # Setup: Report owned by user123
        mock_report = {
            'type': 'wildfire',
            'latitude': 34.0522,
            'longitude': -118.2437,
            'severity': 'high',
            'user_id': 'user123',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        mock_ref.get.return_value = mock_report

        # Mock auth service to raise ValueError for invalid token
        mock_auth_service.verify_id_token.side_effect = ValueError('Invalid ID token')

        # Make DELETE request with invalid token
        response = client.delete(
            '/api/reports/test_report_id',
            headers={'Authorization': 'Bearer invalid_token'}
        )

        # Assert: Unauthorized (401)
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Authentication failed' in data['error']

        # Verify delete was NOT called
        mock_ref.delete.assert_not_called()

    def test_admin_can_delete_any_report(self, client, mock_firebase_db, mock_auth_service):
        """Test: Admin can delete any user's report (admin override)"""
        mock_db, mock_ref = mock_firebase_db

        # Setup: Report owned by user123
        mock_report = {
            'type': 'tornado',
            'latitude': 35.4676,
            'longitude': -97.5164,
            'severity': 'critical',
            'user_id': 'user123',  # Different owner
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        mock_ref.get.return_value = mock_report

        # Mock auth service to verify token and return admin_user
        mock_auth_service.verify_id_token.return_value = {
            'user_id': 'admin_user_999',
            'email': 'admin@example.com',
            'email_verified': True
        }

        # Mock environment variable with admin_user_999 as admin
        with patch.dict(os.environ, {'ADMIN_USER_IDS': 'admin_user_999,another_admin'}):
            response = client.delete(
                '/api/reports/test_report_id',
                headers={'Authorization': 'Bearer valid_admin_token'}
            )

        # Assert: Successful deletion (200) - admin override
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'deleted'
        assert data['id'] == 'test_report_id'
        assert data['deleted_by'] == 'admin_user_999'

        # Verify delete was called (twice: report + user_reports tracking)
        assert mock_ref.delete.call_count == 2

    def test_delete_legacy_report_no_owner(self, client, mock_firebase_db):
        """Test: Legacy report without user_id can be deleted by anyone (backward compatibility)"""
        mock_db, mock_ref = mock_firebase_db

        # Setup: Legacy report WITHOUT user_id field
        mock_report = {
            'type': 'flood',
            'latitude': 29.7604,
            'longitude': -95.3698,
            'severity': 'medium',
            'timestamp': datetime.now(timezone.utc).isoformat()
            # No user_id field (legacy report)
        }

        mock_ref.get.return_value = mock_report

        # Make DELETE request WITHOUT authentication (allowed for legacy)
        response = client.delete('/api/reports/test_legacy_report_id')

        # Assert: Successful deletion (200) - backward compatibility
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'deleted'
        assert data['id'] == 'test_legacy_report_id'
        assert 'Legacy report deleted' in data['note']

        # Verify delete was called
        mock_ref.delete.assert_called_once()

    def test_delete_nonexistent_report(self, client, mock_firebase_db):
        """Test: Attempting to delete non-existent report returns 404"""
        mock_db, mock_ref = mock_firebase_db

        # Mock Firebase get() to return None (report not found)
        mock_ref.get.return_value = None

        # Make DELETE request
        response = client.delete(
            '/api/reports/nonexistent_id',
            headers={'Authorization': 'Bearer valid_token'}
        )

        # Assert: Not Found (404)
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'Report not found' in data['error']

        # Verify delete was NOT called
        mock_ref.delete.assert_not_called()

    def test_delete_own_report_removes_from_user_reports_tracking(self, client, mock_firebase_db, mock_auth_service):
        """Test: Deleting own report also removes from user_reports tracking"""
        mock_db, mock_ref = mock_firebase_db

        # Setup: Report owned by user123
        mock_report = {
            'type': 'wildfire',
            'latitude': 34.0522,
            'longitude': -118.2437,
            'severity': 'high',
            'user_id': 'user123',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        mock_ref.get.return_value = mock_report

        # Mock auth service
        mock_auth_service.verify_id_token.return_value = {
            'user_id': 'user123',
            'email': 'user@example.com',
            'email_verified': True
        }

        # Track calls to db.reference()
        reference_calls = []

        def mock_reference(path):
            reference_calls.append(path)
            return mock_ref

        mock_db.reference.side_effect = mock_reference

        # Make DELETE request
        response = client.delete(
            '/api/reports/test_report_id',
            headers={'Authorization': 'Bearer valid_token_user123'}
        )

        # Assert: Success
        assert response.status_code == 200

        # Verify both references were called
        assert 'reports/test_report_id' in reference_calls
        assert 'user_reports/user123/reports/test_report_id' in reference_calls


class TestReportOwnershipEdgeCases:
    """Test edge cases for report ownership"""

    def test_delete_with_malformed_authorization_header(self, client, mock_firebase_db):
        """Test: Malformed Authorization header on owned report"""
        mock_db, mock_ref = mock_firebase_db

        mock_report = {
            'type': 'wildfire',
            'user_id': 'user123',
            'latitude': 34.0522,
            'longitude': -118.2437,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        mock_ref.get.return_value = mock_report

        # Test missing "Bearer " prefix
        response = client.delete(
            '/api/reports/test_report_id',
            headers={'Authorization': 'invalid_format_token'}
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Authentication required' in data['error']

    def test_delete_with_expired_token(self, client, mock_firebase_db, mock_auth_service):
        """Test: Expired token when deleting owned report"""
        mock_db, mock_ref = mock_firebase_db

        mock_report = {
            'type': 'earthquake',
            'user_id': 'user123',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        mock_ref.get.return_value = mock_report

        # Mock auth service to raise ExpiredIdTokenError
        from firebase_admin.auth import ExpiredIdTokenError
        mock_auth_service.verify_id_token.side_effect = ValueError('Token has expired')

        response = client.delete(
            '/api/reports/test_report_id',
            headers={'Authorization': 'Bearer expired_token'}
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Authentication failed' in data['error']

    def test_delete_report_firebase_error(self, client, mock_firebase_db, mock_auth_service):
        """Test: Firebase database error during deletion"""
        mock_db, mock_ref = mock_firebase_db

        mock_report = {
            'type': 'wildfire',
            'user_id': 'user123',
            'latitude': 34.0522,
            'longitude': -118.2437,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        mock_ref.get.return_value = mock_report

        mock_auth_service.verify_id_token.return_value = {
            'user_id': 'user123',
            'email': 'user@example.com'
        }

        # Mock Firebase delete() to raise an exception
        mock_ref.delete.side_effect = Exception('Firebase connection error')

        response = client.delete(
            '/api/reports/test_report_id',
            headers={'Authorization': 'Bearer valid_token'}
        )

        # Should return 500 Internal Server Error
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data


def run_tests():
    """Run all ownership tests"""
    print("\n" + "="*60)
    print("🧪 RUNNING REPORT OWNERSHIP VALIDATION TESTS")
    print("="*60 + "\n")

    # Run pytest programmatically
    pytest.main([__file__, '-v', '--tb=short'])


if __name__ == '__main__':
    run_tests()
