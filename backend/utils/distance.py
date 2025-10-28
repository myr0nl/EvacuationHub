"""
Distance calculation utilities with memoization for performance optimization.
"""
import math
from functools import lru_cache


@lru_cache(maxsize=10000)
def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth using the Haversine formula.

    This function is memoized using LRU cache to improve performance for repeated calculations
    with the same coordinate pairs. The cache can store up to 10,000 unique calculations.

    Args:
        lat1: Latitude of the first point in decimal degrees (-90 to 90)
        lon1: Longitude of the first point in decimal degrees (-180 to 180)
        lat2: Latitude of the second point in decimal degrees (-90 to 90)
        lon2: Longitude of the second point in decimal degrees (-180 to 180)

    Returns:
        Distance between the two points in miles

    Examples:
        >>> # Distance between San Francisco and Los Angeles
        >>> haversine_distance(37.7749, -122.4194, 34.0522, -118.2437)
        347.4...

        >>> # Distance between New York and Boston
        >>> haversine_distance(40.7128, -74.0060, 42.3601, -71.0589)
        190.4...

        >>> # Same point (should be 0)
        >>> haversine_distance(37.7749, -122.4194, 37.7749, -122.4194)
        0.0

    Note:
        - This function uses the Earth's mean radius (3958.8 miles)
        - Accuracy is typically within 0.5% for most terrestrial distances
        - Does NOT validate coordinates - caller is responsible for validation
        - Memoization makes repeated calls with same coordinates extremely fast
    """
    # Earth's mean radius in miles
    R = 3958.8

    # Convert decimal degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Calculate differences
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    # Haversine formula
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance


def clear_distance_cache() -> None:
    """
    Clear the haversine_distance LRU cache.

    Useful for testing or when memory usage is a concern.
    """
    haversine_distance.cache_clear()


def get_cache_info() -> dict:
    """
    Get information about the haversine_distance cache.

    Returns:
        Dictionary with cache statistics including hits, misses, and current size
    """
    info = haversine_distance.cache_info()
    return {
        'hits': info.hits,
        'misses': info.misses,
        'maxsize': info.maxsize,
        'currsize': info.currsize
    }
