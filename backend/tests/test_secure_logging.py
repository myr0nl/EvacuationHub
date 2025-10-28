"""
Tests for secure logging utilities with PII redaction.
"""

import pytest
from utils.secure_logging import (
    redact_pii,
    hash_user_id,
    redact_coordinates,
    safe_log_dict
)


class TestRedactPII:
    """Tests for PII redaction function"""

    def test_redact_email_addresses(self):
        """Email addresses should be redacted"""
        text = "User john.doe@example.com logged in"
        result = redact_pii(text)
        assert result == "User [EMAIL_REDACTED] logged in"
        assert "@example.com" not in result

    def test_redact_multiple_emails(self):
        """Multiple email addresses should all be redacted"""
        text = "Emails: alice@test.com, bob@example.org"
        result = redact_pii(text)
        assert result == "Emails: [EMAIL_REDACTED], [EMAIL_REDACTED]"

    def test_redact_precise_coordinates(self):
        """Precise coordinates (4+ decimals) should be redacted"""
        text = "Location: 37.7749, -122.4194"
        result = redact_pii(text)
        assert result == "Location: [COORD_REDACTED], [COORD_REDACTED]"

    def test_keep_rough_coordinates(self):
        """Rough coordinates (1-3 decimals) should be preserved for debugging"""
        text = "City location: 37.7, -122.4"
        result = redact_pii(text)
        assert result == "City location: 37.7, -122.4"

    def test_redact_ipv4_addresses(self):
        """IPv4 addresses should be redacted"""
        text = "Request from 192.168.1.100"
        result = redact_pii(text)
        assert result == "Request from [IP_REDACTED]"

    def test_redact_phone_numbers(self):
        """US phone numbers should be redacted"""
        text = "Contact: (555) 123-4567 or 555-987-6543"
        result = redact_pii(text)
        assert "[PHONE_REDACTED]" in result
        assert "555" not in result or result.count("555") == 0

    def test_redact_credit_cards(self):
        """Credit card numbers should be redacted"""
        text = "Card: 4532-1234-5678-9010"
        result = redact_pii(text)
        assert result == "Card: [CARD_REDACTED]"

    def test_empty_string(self):
        """Empty strings should be handled gracefully"""
        assert redact_pii("") == ""

    def test_none_value(self):
        """None values should be handled gracefully"""
        assert redact_pii(None) is None


class TestHashUserID:
    """Tests for user ID hashing function"""

    def test_hash_is_consistent(self):
        """Same user ID should always produce same hash"""
        user_id = "user_12345"
        hash1 = hash_user_id(user_id)
        hash2 = hash_user_id(user_id)
        assert hash1 == hash2

    def test_hash_is_different_for_different_users(self):
        """Different user IDs should produce different hashes"""
        hash1 = hash_user_id("user_123")
        hash2 = hash_user_id("user_456")
        assert hash1 != hash2

    def test_hash_length(self):
        """Hash should be truncated to specified length"""
        user_id = "user_12345"
        assert len(hash_user_id(user_id, length=16)) == 16
        assert len(hash_user_id(user_id, length=8)) == 8

    def test_hash_cannot_be_reversed(self):
        """Hash should not reveal original user ID"""
        user_id = "user_sensitive_info_12345"
        hashed = hash_user_id(user_id)
        assert "sensitive_info" not in hashed
        assert "12345" not in hashed

    def test_empty_user_id(self):
        """Empty user ID should be handled gracefully"""
        assert hash_user_id("") == "[NO_USER_ID]"

    def test_none_user_id(self):
        """None user ID should be handled gracefully"""
        assert hash_user_id(None) == "[NO_USER_ID]"


class TestRedactCoordinates:
    """Tests for coordinate redaction function"""

    def test_redact_to_neighborhood_level(self):
        """Coordinates should be rounded to neighborhood level by default"""
        lat, lon = redact_coordinates(37.7749, -122.4194)
        assert lat == "37.77"
        assert lon == "-122.42"

    def test_custom_precision(self):
        """Custom precision levels should work"""
        lat, lon = redact_coordinates(37.7749, -122.4194, precision=1)
        assert lat == "37.8"
        assert lon == "-122.4"

    def test_zero_precision(self):
        """Zero precision should round to integers"""
        lat, lon = redact_coordinates(37.7749, -122.4194, precision=0)
        assert lat == "38"
        assert lon == "-122"

    def test_none_coordinates(self):
        """None coordinates should be fully redacted"""
        lat, lon = redact_coordinates(None, None)
        assert lat == "[REDACTED]"
        assert lon == "[REDACTED]"

    def test_partial_none(self):
        """Partial None should redact both"""
        lat, lon = redact_coordinates(37.7749, None)
        assert lat == "[REDACTED]"
        assert lon == "[REDACTED]"


class TestSafeLogDict:
    """Tests for dictionary sanitization function"""

    def test_redact_default_sensitive_keys(self):
        """Default sensitive keys should be redacted"""
        data = {
            'email': 'john@example.com',
            'password': 'secret123',
            'name': 'John Doe'
        }
        result = safe_log_dict(data)
        assert result['email'] == '[REDACTED]'
        assert result['password'] == '[REDACTED]'
        assert result['name'] == 'John Doe'

    def test_redact_custom_keys(self):
        """Custom sensitive keys should be redacted"""
        data = {
            'api_key': 'secret123',
            'count': 5
        }
        result = safe_log_dict(data, redact_keys=['api_key'])
        assert result['api_key'] == '[REDACTED]'
        assert result['count'] == 5

    def test_nested_dictionaries(self):
        """Nested dictionaries should be recursively sanitized"""
        data = {
            'user': {
                'email': 'john@example.com',
                'name': 'John'
            }
        }
        result = safe_log_dict(data)
        assert result['user']['email'] == '[REDACTED]'
        assert result['user']['name'] == 'John'

    def test_lists_of_dictionaries(self):
        """Lists containing dictionaries should be sanitized"""
        data = {
            'users': [
                {'email': 'alice@test.com', 'name': 'Alice'},
                {'email': 'bob@test.com', 'name': 'Bob'}
            ]
        }
        result = safe_log_dict(data)
        assert result['users'][0]['email'] == '[REDACTED]'
        assert result['users'][1]['email'] == '[REDACTED]'
        assert result['users'][0]['name'] == 'Alice'

    def test_case_insensitive_matching(self):
        """Key matching should be case-insensitive"""
        data = {
            'Email': 'john@example.com',
            'PASSWORD': 'secret123',
            'User_ID': 'user_123'  # Contains 'user_id' substring
        }
        result = safe_log_dict(data)
        assert result['Email'] == '[REDACTED]'
        assert result['PASSWORD'] == '[REDACTED]'
        assert result['User_ID'] == '[REDACTED]'

    def test_partial_key_matching(self):
        """Partial key matching should work (e.g., 'user_email' contains 'email')"""
        data = {
            'user_email': 'john@example.com',
            'reset_token': 'abc123',
            'description': 'Normal field'
        }
        result = safe_log_dict(data)
        assert result['user_email'] == '[REDACTED]'
        assert result['reset_token'] == '[REDACTED]'
        assert result['description'] == 'Normal field'


class TestRealWorldScenarios:
    """Tests for real-world logging scenarios"""

    def test_user_login_log(self):
        """User login scenario"""
        log_message = "User john.doe@example.com logged in from IP 192.168.1.100"
        result = redact_pii(log_message)
        assert "[EMAIL_REDACTED]" in result
        assert "[IP_REDACTED]" in result
        assert "john.doe" not in result
        assert "192.168.1.100" not in result

    def test_disaster_report_log(self):
        """Disaster report scenario"""
        log_message = "Report created at location 37.7749, -122.4194 by user user_abc123"
        result = redact_pii(log_message)
        assert "[COORD_REDACTED]" in result
        assert "37.7749" not in result

    def test_api_request_log(self):
        """API request scenario"""
        data = {
            'endpoint': '/api/reports',
            'user_id': 'user_123',
            'ip_address': '10.0.0.1',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'disaster_type': 'earthquake'
        }
        result = safe_log_dict(data)
        assert result['user_id'] == '[REDACTED]'
        assert result['ip_address'] == '[REDACTED]'
        assert result['latitude'] == '[REDACTED]'
        assert result['longitude'] == '[REDACTED]'
        assert result['disaster_type'] == 'earthquake'
