"""
Tests for validation utilities
"""
import pytest
from utils.validators import CoordinateValidator, DisasterValidator


class TestCoordinateValidator:
    """Test suite for CoordinateValidator"""

    def test_valid_coordinates(self):
        """Test valid latitude and longitude ranges"""
        assert CoordinateValidator.validate_coordinates(37.7749, -122.4194) is True
        assert CoordinateValidator.validate_coordinates(0, 0) is True
        assert CoordinateValidator.validate_coordinates(90, 180) is True
        assert CoordinateValidator.validate_coordinates(-90, -180) is True

    def test_invalid_latitude(self):
        """Test invalid latitude values"""
        assert CoordinateValidator.validate_coordinates(91, 0) is False
        assert CoordinateValidator.validate_coordinates(-91, 0) is False
        assert CoordinateValidator.validate_coordinates(100, 0) is False

    def test_invalid_longitude(self):
        """Test invalid longitude values"""
        assert CoordinateValidator.validate_coordinates(0, 181) is False
        assert CoordinateValidator.validate_coordinates(0, -181) is False
        assert CoordinateValidator.validate_coordinates(0, 200) is False

    def test_invalid_types(self):
        """Test non-numeric coordinate values"""
        assert CoordinateValidator.validate_coordinates("invalid", 0) is False
        assert CoordinateValidator.validate_coordinates(0, "invalid") is False
        assert CoordinateValidator.validate_coordinates(None, 0) is False
        assert CoordinateValidator.validate_coordinates(0, None) is False

    def test_coordinate_dict_valid(self):
        """Test valid coordinate dictionary"""
        assert CoordinateValidator.validate_coordinate_dict({'lat': 37.7749, 'lon': -122.4194}) is True
        assert CoordinateValidator.validate_coordinate_dict({'lat': 0, 'lon': 0}) is True

    def test_coordinate_dict_invalid(self):
        """Test invalid coordinate dictionary"""
        assert CoordinateValidator.validate_coordinate_dict({'lat': 91, 'lon': 0}) is False
        assert CoordinateValidator.validate_coordinate_dict({'lat': 0, 'lon': 181}) is False
        assert CoordinateValidator.validate_coordinate_dict({'invalid': 'keys'}) is False
        assert CoordinateValidator.validate_coordinate_dict({}) is False


class TestDisasterValidator:
    """Test suite for DisasterValidator"""

    def test_valid_disaster_types(self):
        """Test valid disaster types"""
        assert DisasterValidator.validate_disaster_type('earthquake') is True
        assert DisasterValidator.validate_disaster_type('flood') is True
        assert DisasterValidator.validate_disaster_type('wildfire') is True
        assert DisasterValidator.validate_disaster_type('hurricane') is True
        assert DisasterValidator.validate_disaster_type('tornado') is True
        assert DisasterValidator.validate_disaster_type('volcano') is True
        assert DisasterValidator.validate_disaster_type('drought') is True
        assert DisasterValidator.validate_disaster_type('weather_alert') is True
        assert DisasterValidator.validate_disaster_type('other') is True

    def test_invalid_disaster_types(self):
        """Test invalid disaster types"""
        assert DisasterValidator.validate_disaster_type('tsunami') is False
        assert DisasterValidator.validate_disaster_type('avalanche') is False
        assert DisasterValidator.validate_disaster_type('') is False
        assert DisasterValidator.validate_disaster_type('invalid') is False

    def test_case_insensitive_disaster_types(self):
        """Test case-insensitive disaster type validation"""
        assert DisasterValidator.validate_disaster_type('EARTHQUAKE') is True
        assert DisasterValidator.validate_disaster_type('Flood') is True
        assert DisasterValidator.validate_disaster_type('WiLdFiRe') is True

    def test_valid_severities(self):
        """Test valid severity levels"""
        assert DisasterValidator.validate_severity('low') is True
        assert DisasterValidator.validate_severity('medium') is True
        assert DisasterValidator.validate_severity('high') is True
        assert DisasterValidator.validate_severity('critical') is True

    def test_invalid_severities(self):
        """Test invalid severity levels"""
        assert DisasterValidator.validate_severity('extreme') is False
        assert DisasterValidator.validate_severity('minor') is False
        assert DisasterValidator.validate_severity('') is False
        assert DisasterValidator.validate_severity('invalid') is False

    def test_case_insensitive_severities(self):
        """Test case-insensitive severity validation"""
        assert DisasterValidator.validate_severity('LOW') is True
        assert DisasterValidator.validate_severity('Medium') is True
        assert DisasterValidator.validate_severity('HIGH') is True
        assert DisasterValidator.validate_severity('CrItIcAl') is True

    def test_valid_weather_severities(self):
        """Test valid NOAA weather severity levels"""
        assert DisasterValidator.validate_weather_severity('Extreme') is True
        assert DisasterValidator.validate_weather_severity('Severe') is True
        assert DisasterValidator.validate_weather_severity('Moderate') is True
        assert DisasterValidator.validate_weather_severity('Minor') is True
        assert DisasterValidator.validate_weather_severity('Unknown') is True

    def test_case_insensitive_weather_severities(self):
        """Test case-insensitive weather severity validation"""
        assert DisasterValidator.validate_weather_severity('extreme') is True
        assert DisasterValidator.validate_weather_severity('SEVERE') is True
        assert DisasterValidator.validate_weather_severity('moderate') is True

    def test_valid_recaptcha_score(self):
        """Test valid reCAPTCHA scores"""
        is_valid, error = DisasterValidator.validate_recaptcha_score(0.0)
        assert is_valid is True
        assert error is None

        is_valid, error = DisasterValidator.validate_recaptcha_score(0.5)
        assert is_valid is True
        assert error is None

        is_valid, error = DisasterValidator.validate_recaptcha_score(1.0)
        assert is_valid is True
        assert error is None

    def test_invalid_recaptcha_score(self):
        """Test invalid reCAPTCHA scores"""
        is_valid, error = DisasterValidator.validate_recaptcha_score(1.5)
        assert is_valid is False
        assert 'between 0 and 1' in error

        is_valid, error = DisasterValidator.validate_recaptcha_score(-0.1)
        assert is_valid is False
        assert 'between 0 and 1' in error

        is_valid, error = DisasterValidator.validate_recaptcha_score('invalid')
        assert is_valid is False
        assert 'must be a number' in error

    def test_valid_report_data(self):
        """Test complete valid report data"""
        data = {
            'latitude': 37.7749,
            'longitude': -122.4194,
            'type': 'earthquake',
            'severity': 'high'
        }
        is_valid, error = DisasterValidator.validate_report_data(data)
        assert is_valid is True
        assert error is None

    def test_minimal_valid_report(self):
        """Test minimal valid report (required fields only)"""
        data = {
            'latitude': 37.7749,
            'longitude': -122.4194,
            'type': 'earthquake'
        }
        is_valid, error = DisasterValidator.validate_report_data(data)
        assert is_valid is True
        assert error is None

    def test_missing_required_fields(self):
        """Test missing required fields"""
        # Missing latitude
        data = {'longitude': -122.4194, 'type': 'earthquake'}
        is_valid, error = DisasterValidator.validate_report_data(data)
        assert is_valid is False
        assert 'Missing required fields' in error
        assert 'latitude' in error

        # Missing longitude
        data = {'latitude': 37.7749, 'type': 'earthquake'}
        is_valid, error = DisasterValidator.validate_report_data(data)
        assert is_valid is False
        assert 'longitude' in error

        # Missing type
        data = {'latitude': 37.7749, 'longitude': -122.4194}
        is_valid, error = DisasterValidator.validate_report_data(data)
        assert is_valid is False
        assert 'type' in error

    def test_invalid_coordinates_in_report(self):
        """Test invalid coordinates in report data"""
        data = {
            'latitude': 91,  # Invalid
            'longitude': -122.4194,
            'type': 'earthquake'
        }
        is_valid, error = DisasterValidator.validate_report_data(data)
        assert is_valid is False
        assert 'Latitude must be between' in error

        data = {
            'latitude': 37.7749,
            'longitude': 181,  # Invalid
            'type': 'earthquake'
        }
        is_valid, error = DisasterValidator.validate_report_data(data)
        assert is_valid is False
        assert 'Longitude must be between' in error

    def test_invalid_disaster_type_in_report(self):
        """Test invalid disaster type in report data"""
        data = {
            'latitude': 37.7749,
            'longitude': -122.4194,
            'type': 'tsunami'  # Invalid
        }
        is_valid, error = DisasterValidator.validate_report_data(data)
        assert is_valid is False
        assert 'Invalid disaster type' in error

    def test_invalid_severity_in_report(self):
        """Test invalid severity in report data"""
        data = {
            'latitude': 37.7749,
            'longitude': -122.4194,
            'type': 'earthquake',
            'severity': 'extreme'  # Invalid
        }
        is_valid, error = DisasterValidator.validate_report_data(data)
        assert is_valid is False
        assert 'Invalid severity' in error

    def test_invalid_recaptcha_score_in_report(self):
        """Test invalid reCAPTCHA score in report data"""
        data = {
            'latitude': 37.7749,
            'longitude': -122.4194,
            'type': 'earthquake',
            'recaptcha_score': 1.5  # Invalid
        }
        is_valid, error = DisasterValidator.validate_report_data(data)
        assert is_valid is False
        assert 'recaptcha_score' in error

    def test_get_valid_types_list(self):
        """Test getting list of valid disaster types"""
        types = DisasterValidator.get_valid_types_list()
        assert isinstance(types, list)
        assert 'earthquake' in types
        assert 'wildfire' in types
        assert len(types) == 9

    def test_get_valid_severities_list(self):
        """Test getting list of valid severity levels"""
        severities = DisasterValidator.get_valid_severities_list()
        assert isinstance(severities, list)
        assert 'low' in severities
        assert 'critical' in severities
        assert len(severities) == 4
