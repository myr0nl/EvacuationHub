"""
Validation utilities for disaster reports and coordinates.

Provides centralized validation logic for:
- Coordinate ranges (latitude/longitude)
- Disaster types and severity levels
- Complete report data validation

This module consolidates validation logic previously scattered across
app.py, route_calculation_service.py, and confidence_scorer.py.
"""
from typing import Dict, Tuple, Optional


class CoordinateValidator:
    """Validator for geographic coordinates."""

    @staticmethod
    def validate_coordinates(lat: float, lon: float) -> bool:
        """
        Validate latitude and longitude ranges.

        Args:
            lat: Latitude value
            lon: Longitude value

        Returns:
            True if coordinates are valid, False otherwise

        Examples:
            >>> CoordinateValidator.validate_coordinates(37.7749, -122.4194)
            True
            >>> CoordinateValidator.validate_coordinates(91, 0)  # Invalid latitude
            False
            >>> CoordinateValidator.validate_coordinates(0, 181)  # Invalid longitude
            False
        """
        try:
            latitude = float(lat)
            longitude = float(lon)
            return -90 <= latitude <= 90 and -180 <= longitude <= 180
        except (TypeError, ValueError):
            return False

    @staticmethod
    def validate_coordinate_dict(coord: Dict[str, float]) -> bool:
        """
        Validate coordinate dictionary with 'lat' and 'lon' keys.

        Args:
            coord: Dictionary with 'lat' and 'lon' keys

        Returns:
            True if coordinates are valid, False otherwise

        Examples:
            >>> CoordinateValidator.validate_coordinate_dict({'lat': 37.7749, 'lon': -122.4194})
            True
            >>> CoordinateValidator.validate_coordinate_dict({'lat': 91, 'lon': 0})
            False
            >>> CoordinateValidator.validate_coordinate_dict({'invalid': 'keys'})
            False
        """
        try:
            lat = coord['lat']
            lon = coord['lon']
            return CoordinateValidator.validate_coordinates(lat, lon)
        except (KeyError, TypeError):
            return False


class DisasterValidator:
    """Validator for disaster types, severity levels, and report data."""

    # Valid disaster types across the system
    VALID_TYPES = [
        'earthquake',
        'flood',
        'wildfire',
        'hurricane',
        'tornado',
        'volcano',
        'drought',
        'weather_alert',
        'other'
    ]

    # Valid severity levels
    VALID_SEVERITIES = ['low', 'medium', 'high', 'critical']

    # Additional NOAA weather alert severity levels (for compatibility)
    VALID_WEATHER_SEVERITIES = ['Extreme', 'Severe', 'Moderate', 'Minor', 'Unknown']

    @staticmethod
    def validate_disaster_type(disaster_type: str) -> bool:
        """
        Validate disaster type against allowed values.

        Args:
            disaster_type: Type of disaster (e.g., 'earthquake', 'wildfire')

        Returns:
            True if disaster type is valid, False otherwise

        Examples:
            >>> DisasterValidator.validate_disaster_type('earthquake')
            True
            >>> DisasterValidator.validate_disaster_type('tsunami')
            False
            >>> DisasterValidator.validate_disaster_type('')
            False
        """
        if not disaster_type:
            return False

        return disaster_type.lower() in DisasterValidator.VALID_TYPES

    @staticmethod
    def validate_severity(severity: str) -> bool:
        """
        Validate severity level against allowed values.

        Args:
            severity: Severity level (e.g., 'low', 'medium', 'high', 'critical')

        Returns:
            True if severity is valid, False otherwise

        Examples:
            >>> DisasterValidator.validate_severity('high')
            True
            >>> DisasterValidator.validate_severity('extreme')
            False
            >>> DisasterValidator.validate_severity('')
            False
        """
        if not severity:
            return False

        return severity.lower() in DisasterValidator.VALID_SEVERITIES

    @staticmethod
    def validate_weather_severity(severity: str) -> bool:
        """
        Validate NOAA weather alert severity level.

        Args:
            severity: NOAA severity level (e.g., 'Extreme', 'Severe')

        Returns:
            True if severity is valid, False otherwise

        Examples:
            >>> DisasterValidator.validate_weather_severity('Extreme')
            True
            >>> DisasterValidator.validate_weather_severity('extreme')
            True
            >>> DisasterValidator.validate_weather_severity('Invalid')
            False
        """
        if not severity:
            return False

        # Case-insensitive check
        return severity.capitalize() in DisasterValidator.VALID_WEATHER_SEVERITIES

    @staticmethod
    def validate_recaptcha_score(score: float) -> Tuple[bool, Optional[str]]:
        """
        Validate reCAPTCHA score range.

        Args:
            score: reCAPTCHA score (should be 0.0 to 1.0)

        Returns:
            Tuple of (is_valid, error_message)

        Examples:
            >>> DisasterValidator.validate_recaptcha_score(0.7)
            (True, None)
            >>> DisasterValidator.validate_recaptcha_score(1.5)
            (False, 'recaptcha_score must be between 0 and 1')
        """
        try:
            score_value = float(score)
            if not (0 <= score_value <= 1):
                return False, 'recaptcha_score must be between 0 and 1'
            return True, None
        except (ValueError, TypeError):
            return False, 'recaptcha_score must be a number'

    @staticmethod
    def validate_report_data(data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate complete disaster report data.

        Checks:
        - Required fields (latitude, longitude, type)
        - Coordinate ranges
        - Disaster type validity
        - Optional field validations (severity, recaptcha_score)

        Args:
            data: Dictionary containing report data

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if all validations pass, False otherwise
            - error_message: Description of validation error, or None if valid

        Examples:
            >>> data = {
            ...     'latitude': 37.7749,
            ...     'longitude': -122.4194,
            ...     'type': 'earthquake',
            ...     'severity': 'high'
            ... }
            >>> DisasterValidator.validate_report_data(data)
            (True, None)

            >>> bad_data = {'latitude': 91, 'longitude': 0, 'type': 'earthquake'}
            >>> DisasterValidator.validate_report_data(bad_data)
            (False, 'Latitude must be between -90 and 90')
        """
        # Check required fields
        required_fields = ['latitude', 'longitude', 'type']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return False, f'Missing required fields: {", ".join(missing_fields)}'

        # Validate latitude
        try:
            lat = float(data['latitude'])
            if not (-90 <= lat <= 90):
                return False, 'Latitude must be between -90 and 90'
        except (ValueError, TypeError):
            return False, 'Latitude must be a valid number'

        # Validate longitude
        try:
            lon = float(data['longitude'])
            if not (-180 <= lon <= 180):
                return False, 'Longitude must be between -180 and 180'
        except (ValueError, TypeError):
            return False, 'Longitude must be a valid number'

        # Validate disaster type
        if not DisasterValidator.validate_disaster_type(data['type']):
            valid_types_str = ', '.join(DisasterValidator.VALID_TYPES)
            return False, f'Invalid disaster type. Must be one of: {valid_types_str}'

        # Validate optional severity field
        if 'severity' in data:
            if not DisasterValidator.validate_severity(data['severity']):
                valid_severities_str = ', '.join(DisasterValidator.VALID_SEVERITIES)
                return False, f'Invalid severity. Must be one of: {valid_severities_str}'

        # Validate optional recaptcha_score field
        if 'recaptcha_score' in data:
            is_valid, error_msg = DisasterValidator.validate_recaptcha_score(data['recaptcha_score'])
            if not is_valid:
                return False, error_msg

        # All validations passed
        return True, None

    @staticmethod
    def get_valid_types_list() -> list:
        """
        Get list of valid disaster types.

        Returns:
            List of valid disaster type strings

        Examples:
            >>> types = DisasterValidator.get_valid_types_list()
            >>> 'earthquake' in types
            True
            >>> 'tsunami' in types
            False
        """
        return DisasterValidator.VALID_TYPES.copy()

    @staticmethod
    def get_valid_severities_list() -> list:
        """
        Get list of valid severity levels.

        Returns:
            List of valid severity level strings

        Examples:
            >>> severities = DisasterValidator.get_valid_severities_list()
            >>> 'high' in severities
            True
            >>> 'extreme' in severities
            False
        """
        return DisasterValidator.VALID_SEVERITIES.copy()
