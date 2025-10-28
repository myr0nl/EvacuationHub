"""
API Endpoint Tests for Map Settings Service

Tests the Flask API endpoints:
- GET /api/settings/map
- PUT /api/settings/map
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_app():
    """Create a mock Flask app for testing."""
    with patch('app.db') as mock_db:
        # Import app after patching
        import app as flask_app

        flask_app.app.config['TESTING'] = True
        flask_app.db = mock_db

        yield flask_app.app.test_client(), mock_db


@pytest.fixture
def mock_firebase_auth():
    """Mock Firebase authentication."""
    with patch('services.auth_service.AuthService.verify_id_token') as mock_verify:
        mock_verify.return_value = {'uid': 'test_user_123'}
        yield mock_verify


@pytest.fixture
def default_map_settings():
    """Default map settings returned for new users."""
    return {
        'zoom_radius_mi': 20,
        'display_radius_mi': 20,
        'auto_zoom': True,
        'show_all_disasters': False
    }


@pytest.fixture
def saved_map_settings():
    """Saved map settings for existing user."""
    return {
        'zoom_radius_mi': 10,
        'display_radius_mi': 25,
        'auto_zoom': False,
        'show_all_disasters': True,
        'updated_at': datetime.now(timezone.utc).isoformat()
    }


# ============================================================================
# TEST GET /api/settings/map
# ============================================================================

class TestGetMapSettings:
    """Test GET /api/settings/map endpoint."""

    def test_get_map_settings_no_auth(self, mock_app):
        """Test that endpoint requires authentication."""
        client, _ = mock_app

        response = client.get('/api/settings/map')

        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data
        assert 'authorization' in data['error'].lower() or 'token' in data['error'].lower()

    def test_get_map_settings_invalid_token(self, mock_app):
        """Test with invalid authentication token."""
        client, _ = mock_app

        with patch('services.auth_service.AuthService.verify_id_token') as mock_verify:
            mock_verify.side_effect = ValueError('Invalid token')

            response = client.get(
                '/api/settings/map',
                headers={'Authorization': 'Bearer invalid_token'}
            )

            assert response.status_code == 401

    def test_get_map_settings_default_for_new_user(self, mock_app, mock_firebase_auth):
        """Test returning default settings for new user."""
        client, _ = mock_app

        # Mock proximity_alert_service to return default settings
        with patch('app.proximity_alert_service.get_map_settings') as mock_get:
            mock_get.return_value = {
                'zoom_radius_mi': 20,
                'display_radius_mi': 20,
                'auto_zoom': True,
                'show_all_disasters': False
            }

            response = client.get(
                '/api/settings/map',
                headers={'Authorization': 'Bearer valid_token'}
            )

            assert response.status_code == 200
            data = json.loads(response.data)

            assert data['zoom_radius_mi'] == 20
            assert data['display_radius_mi'] == 20
            assert data['auto_zoom'] is True
            assert data['show_all_disasters'] is False

    def test_get_map_settings_existing_user(self, mock_app, mock_firebase_auth, saved_map_settings):
        """Test returning saved settings for existing user."""
        client, mock_db = mock_app

        # Mock proximity_alert_service.get_map_settings to return saved settings
        with patch('app.proximity_alert_service.get_map_settings') as mock_get:
            mock_get.return_value = saved_map_settings

            response = client.get(
                '/api/settings/map',
                headers={'Authorization': 'Bearer valid_token'}
            )

            assert response.status_code == 200
            data = json.loads(response.data)

            assert data['zoom_radius_mi'] == 10
            assert data['display_radius_mi'] == 25
            assert data['auto_zoom'] is False
            assert data['show_all_disasters'] is True
            assert 'updated_at' in data

    def test_get_map_settings_firebase_error(self, mock_app, mock_firebase_auth):
        """Test handling of Firebase read errors."""
        client, _ = mock_app

        # Mock proximity_alert_service to raise an error
        with patch('app.proximity_alert_service.get_map_settings') as mock_get:
            mock_get.side_effect = Exception('Firebase error')

            response = client.get(
                '/api/settings/map',
                headers={'Authorization': 'Bearer valid_token'}
            )

            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data


# ============================================================================
# TEST PUT /api/settings/map
# ============================================================================

class TestUpdateMapSettings:
    """Test PUT /api/settings/map endpoint."""

    def test_update_map_settings_no_auth(self, mock_app):
        """Test that endpoint requires authentication."""
        client, _ = mock_app

        response = client.put(
            '/api/settings/map',
            json={'zoom_radius_mi': 10},
            content_type='application/json'
        )

        assert response.status_code == 401

    def test_update_map_settings_success(self, mock_app, mock_firebase_auth):
        """Test successful settings update."""
        client, _ = mock_app

        settings = {
            'zoom_radius_mi': 15,
            'display_radius_mi': 30,
            'auto_zoom': True,
            'show_all_disasters': False
        }

        # Mock proximity_alert_service methods
        with patch('app.proximity_alert_service.update_map_settings') as mock_update, \
             patch('app.proximity_alert_service.get_map_settings') as mock_get:

            mock_update.return_value = True
            mock_get.return_value = {
                **settings,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }

            response = client.put(
                '/api/settings/map',
                json=settings,
                headers={'Authorization': 'Bearer valid_token'},
                content_type='application/json'
            )

            assert response.status_code == 200
            data = json.loads(response.data)

            assert data['zoom_radius_mi'] == 15
            assert data['display_radius_mi'] == 30
            assert 'updated_at' in data

    def test_update_map_settings_validation_zoom_radius_too_low(self, mock_app, mock_firebase_auth):
        """Test validation: zoom_radius_mi must be >= 1."""
        client, _ = mock_app

        response = client.put(
            '/api/settings/map',
            json={'zoom_radius_mi': 0, 'display_radius_mi': 20, 'auto_zoom': True, 'show_all_disasters': False},
            headers={'Authorization': 'Bearer valid_token'},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'zoom_radius_mi' in data['error']

    def test_update_map_settings_validation_zoom_radius_too_high(self, mock_app, mock_firebase_auth):
        """Test validation: zoom_radius_mi must be <= 100."""
        client, _ = mock_app

        response = client.put(
            '/api/settings/map',
            json={'zoom_radius_mi': 101, 'display_radius_mi': 20, 'auto_zoom': True, 'show_all_disasters': False},
            headers={'Authorization': 'Bearer valid_token'},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'zoom_radius_mi' in data['error']

    def test_update_map_settings_validation_display_radius_too_low(self, mock_app, mock_firebase_auth):
        """Test validation: display_radius_mi must be >= 1."""
        client, _ = mock_app

        response = client.put(
            '/api/settings/map',
            json={'zoom_radius_mi': 20, 'display_radius_mi': 0, 'auto_zoom': True, 'show_all_disasters': False},
            headers={'Authorization': 'Bearer valid_token'},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'display_radius_mi' in data['error']

    def test_update_map_settings_validation_display_radius_too_high(self, mock_app, mock_firebase_auth):
        """Test validation: display_radius_mi must be <= 100."""
        client, _ = mock_app

        response = client.put(
            '/api/settings/map',
            json={'zoom_radius_mi': 20, 'display_radius_mi': 101, 'auto_zoom': True, 'show_all_disasters': False},
            headers={'Authorization': 'Bearer valid_token'},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'display_radius_mi' in data['error']

    def test_update_map_settings_validation_invalid_types(self, mock_app, mock_firebase_auth):
        """Test validation: correct data types required."""
        client, _ = mock_app

        # Test string instead of number
        response = client.put(
            '/api/settings/map',
            json={'zoom_radius_mi': 'twenty', 'display_radius_mi': 20, 'auto_zoom': True, 'show_all_disasters': False},
            headers={'Authorization': 'Bearer valid_token'},
            content_type='application/json'
        )

        assert response.status_code == 400

        # Test string instead of boolean
        response = client.put(
            '/api/settings/map',
            json={'zoom_radius_mi': 20, 'display_radius_mi': 20, 'auto_zoom': 'yes', 'show_all_disasters': False},
            headers={'Authorization': 'Bearer valid_token'},
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_update_map_settings_partial_update(self, mock_app, mock_firebase_auth):
        """Test partial settings update (API allows partial updates)."""
        client, _ = mock_app

        # Only updating zoom_radius_mi
        with patch('app.proximity_alert_service.update_map_settings') as mock_update, \
             patch('app.proximity_alert_service.get_map_settings') as mock_get:

            mock_update.return_value = True
            mock_get.return_value = {
                'zoom_radius_mi': 25,
                'display_radius_mi': 20,
                'auto_zoom': True,
                'show_all_disasters': False,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }

            response = client.put(
                '/api/settings/map',
                json={'zoom_radius_mi': 25},
                headers={'Authorization': 'Bearer valid_token'},
                content_type='application/json'
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['zoom_radius_mi'] == 25

    def test_update_map_settings_firebase_error(self, mock_app, mock_firebase_auth):
        """Test handling of Firebase write errors."""
        client, _ = mock_app

        # Mock proximity_alert_service to return failure
        with patch('app.proximity_alert_service.update_map_settings') as mock_update:
            mock_update.return_value = False

            response = client.put(
                '/api/settings/map',
                json={'zoom_radius_mi': 20, 'display_radius_mi': 20, 'auto_zoom': True, 'show_all_disasters': False},
                headers={'Authorization': 'Bearer valid_token'},
                content_type='application/json'
            )

            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data

    def test_update_map_settings_timestamp_added(self, mock_app, mock_firebase_auth):
        """Test that updated_at timestamp is added."""
        client, _ = mock_app

        with patch('app.proximity_alert_service.update_map_settings') as mock_update, \
             patch('app.proximity_alert_service.get_map_settings') as mock_get:

            mock_update.return_value = True
            test_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc).isoformat()
            mock_get.return_value = {
                'zoom_radius_mi': 20,
                'display_radius_mi': 20,
                'auto_zoom': True,
                'show_all_disasters': False,
                'updated_at': test_time
            }

            response = client.put(
                '/api/settings/map',
                json={'zoom_radius_mi': 20, 'display_radius_mi': 20, 'auto_zoom': True, 'show_all_disasters': False},
                headers={'Authorization': 'Bearer valid_token'},
                content_type='application/json'
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'updated_at' in data


# ============================================================================
# TEST EDGE CASES
# ============================================================================

class TestMapSettingsEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_update_map_settings_boundary_values(self, mock_app, mock_firebase_auth):
        """Test boundary values (1 and 100 for both radius fields)."""
        client, _ = mock_app

        with patch('app.proximity_alert_service.update_map_settings') as mock_update, \
             patch('app.proximity_alert_service.get_map_settings') as mock_get:

            mock_update.return_value = True
            mock_get.return_value = {
                'zoom_radius_mi': 1,
                'display_radius_mi': 1,
                'auto_zoom': True,
                'show_all_disasters': False,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }

            # Test minimum values
            response = client.put(
                '/api/settings/map',
                json={'zoom_radius_mi': 1, 'display_radius_mi': 1, 'auto_zoom': True, 'show_all_disasters': False},
                headers={'Authorization': 'Bearer valid_token'},
                content_type='application/json'
            )

            assert response.status_code == 200

            # Test maximum values
            mock_get.return_value['zoom_radius_mi'] = 100
            mock_get.return_value['display_radius_mi'] = 100

            response = client.put(
                '/api/settings/map',
                json={'zoom_radius_mi': 100, 'display_radius_mi': 100, 'auto_zoom': True, 'show_all_disasters': False},
                headers={'Authorization': 'Bearer valid_token'},
                content_type='application/json'
            )

            assert response.status_code == 200

    def test_update_map_settings_boolean_variations(self, mock_app, mock_firebase_auth):
        """Test all boolean combinations."""
        client, _ = mock_app

        test_cases = [
            (True, True),
            (True, False),
            (False, True),
            (False, False)
        ]

        for auto_zoom, show_all in test_cases:
            with patch('app.proximity_alert_service.update_map_settings') as mock_update, \
                 patch('app.proximity_alert_service.get_map_settings') as mock_get:

                mock_update.return_value = True
                mock_get.return_value = {
                    'zoom_radius_mi': 20,
                    'display_radius_mi': 20,
                    'auto_zoom': auto_zoom,
                    'show_all_disasters': show_all,
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }

                response = client.put(
                    '/api/settings/map',
                    json={'zoom_radius_mi': 20, 'display_radius_mi': 20, 'auto_zoom': auto_zoom, 'show_all_disasters': show_all},
                    headers={'Authorization': 'Bearer valid_token'},
                    content_type='application/json'
                )

                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['auto_zoom'] == auto_zoom
                assert data['show_all_disasters'] == show_all
