"""
Geospatial utilities for the alert system.
Includes coordinate validation and distance calculations.
"""
import math
from utils.distance import haversine_distance as _haversine_distance


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points on Earth using Haversine formula.

    Args:
        lat1: First point latitude (-90 to 90)
        lon1: First point longitude (-180 to 180)
        lat2: Second point latitude (-90 to 90)
        lon2: Second point longitude (-180 to 180)

    Returns:
        Distance in miles

    Raises:
        ValueError: If coordinates are invalid
    """
    if not is_valid_coordinates(lat1, lon1) or not is_valid_coordinates(lat2, lon2):
        raise ValueError(f"Invalid coordinates: ({lat1}, {lon1}) or ({lat2}, {lon2})")

    return _haversine_distance(lat1, lon1, lat2, lon2)


def is_valid_coordinates(latitude: float, longitude: float) -> bool:
    """
    Validate geographic coordinates, including edge cases at equator and prime meridian.

    Edge Cases Handled:
        - Equator (latitude = 0): Valid and common for equatorial countries
        - Prime Meridian (longitude = 0): Valid and common for West Africa/UK
        - Poles (latitude = ±90): Valid endpoints
        - International Date Line (longitude = ±180): Valid, normalized to 180

    Args:
        latitude: Latitude value (-90 to 90), where 0 is the equator
        longitude: Longitude value (-180 to 180), where 0 is the prime meridian

    Returns:
        True if coordinates are valid, False otherwise

    Examples:
        >>> is_valid_coordinates(0, 0)  # Gulf of Guinea (equator + prime meridian)
        True
        >>> is_valid_coordinates(0, -122.4194)  # Equator crossing Pacific
        True
        >>> is_valid_coordinates(37.7749, 0)  # Prime meridian in Algeria
        True
        >>> is_valid_coordinates(90, 0)  # North Pole
        True
        >>> is_valid_coordinates(-90, 0)  # South Pole
        True
        >>> is_valid_coordinates(91, 0)  # Invalid latitude
        False
        >>> is_valid_coordinates(0, 181)  # Invalid longitude
        False
    """
    try:
        lat = float(latitude)
        lon = float(longitude)

        # NaN and infinity checks
        if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
            return False

        # Range validation - use <= and >= to include 0 (equator/prime meridian)
        # Latitude: -90 (South Pole) to +90 (North Pole), inclusive
        # Longitude: -180 (antimeridian west) to +180 (antimeridian east), inclusive
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except (TypeError, ValueError):
        return False


def normalize_longitude(longitude: float) -> float:
    """
    Normalize longitude to the range [-180, 180].
    Useful for handling coordinates that cross the International Date Line.

    Args:
        longitude: Longitude in decimal degrees

    Returns:
        Normalized longitude in range [-180, 180]

    Examples:
        >>> normalize_longitude(181)
        -179.0
        >>> normalize_longitude(-181)
        179.0
        >>> normalize_longitude(360)
        0.0
        >>> normalize_longitude(0)  # Prime meridian
        0.0
    """
    # Normalize to [-180, 180]
    normalized = longitude % 360
    if normalized > 180:
        normalized -= 360
    elif normalized < -180:
        normalized += 360
    return normalized
