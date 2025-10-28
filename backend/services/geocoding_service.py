"""
Geocoding Service - Reverse Geocoding with OpenStreetMap Nominatim

Converts latitude/longitude coordinates to human-readable location names
(city, state, country) for enhanced AI prompts and user experience.

Features:
- OpenStreetMap Nominatim API integration (free, no API key)
- Firebase caching (30-day TTL for geocoding results)
- Rate limiting (1 request/second as per Nominatim ToS)
- Graceful error handling with coordinate fallback
"""

import requests
import time
from typing import Dict, Optional
import logging
from firebase_admin import db

logger = logging.getLogger(__name__)


class GeocodingService:
    """
    Reverse geocoding service using OpenStreetMap Nominatim API

    Usage:
        service = GeocodingService(cache_manager)
        location = service.reverse_geocode(37.7749, -122.4194)
        # Returns: {city: "San Francisco", state: "California", ...}

        # For AI prompts:
        formatted = service.format_location_for_ai(37.7749, -122.4194)
        # Returns: "San Francisco, California, United States (37.77, -122.42)"
    """

    def __init__(self, cache_manager):
        """
        Initialize geocoding service

        Args:
            cache_manager: CacheManager instance for Firebase caching
        """
        self.cache_manager = cache_manager
        self.base_url = "https://nominatim.openstreetmap.org/reverse"
        self.last_request_time = 0
        self.rate_limit_delay = 1.0  # 1 second between requests (Nominatim ToS)

    def reverse_geocode(self, latitude: float, longitude: float) -> Optional[Dict]:
        """
        Convert coordinates to location name

        Args:
            latitude: Latitude coordinate (-90 to 90)
            longitude: Longitude coordinate (-180 to 180)

        Returns:
            Dict with 'city', 'state', 'country', 'display_name' or None on error

        Example:
            result = service.reverse_geocode(37.7749, -122.4194)
            # {
            #   'city': 'San Francisco',
            #   'state': 'California',
            #   'country': 'United States',
            #   'display_name': 'San Francisco, California, United States'
            # }
        """
        # Validate coordinates
        if not self._validate_coordinates(latitude, longitude):
            logger.warning(f"Invalid coordinates: ({latitude}, {longitude})")
            return None

        # Check cache first (4 decimal precision = ~11m accuracy)
        # Replace periods with underscores for Firebase path compatibility
        cache_key = f"geocode_{latitude:.4f}_{longitude:.4f}".replace('.', '_').replace('-', 'n')
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        # Rate limiting: ensure 1 second between requests
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)

        try:
            response = requests.get(
                self.base_url,
                params={
                    'lat': latitude,
                    'lon': longitude,
                    'format': 'json',
                    'addressdetails': 1
                },
                headers={'User-Agent': 'DisasterAlertSystem/1.0'},
                timeout=5
            )

            self.last_request_time = time.time()

            if response.status_code == 200:
                data = response.json()
                result = self._parse_nominatim_response(data)

                # Cache for 30 days (coordinates don't change)
                self._save_to_cache(cache_key, result, ttl_days=30)

                return result
            else:
                logger.warning(f"Geocoding API error: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Geocoding error for ({latitude}, {longitude}): {e}")
            return None

    def format_location_for_ai(self, latitude: float, longitude: float) -> str:
        """
        Get human-readable location string for AI prompt

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            Formatted location string

        Examples:
            "San Francisco, California, United States (37.7749, -122.4194)"
            "Rural Area, Nevada, United States (39.1234, -119.5678)"
            "(37.7749, -122.4194)" [if geocoding fails]
        """
        location_data = self.reverse_geocode(latitude, longitude)

        if location_data and location_data.get('display_name'):
            display = location_data['display_name']
            return f"{display} ({latitude:.4f}, {longitude:.4f})"
        else:
            # Fallback to coordinates only
            return f"({latitude:.4f}, {longitude:.4f})"

    def _validate_coordinates(self, latitude: float, longitude: float) -> bool:
        """Validate coordinate ranges"""
        return (-90 <= latitude <= 90) and (-180 <= longitude <= 180)

    def _parse_nominatim_response(self, data: Dict) -> Dict:
        """
        Extract relevant fields from Nominatim API response

        Args:
            data: Raw JSON response from Nominatim API

        Returns:
            Parsed location dict with city, state, country fields
        """
        address = data.get('address', {})

        # Try to get city (multiple possible fields)
        city = (
            address.get('city') or
            address.get('town') or
            address.get('village') or
            address.get('hamlet') or
            address.get('county') or
            address.get('municipality')
        )

        state = address.get('state')
        country = address.get('country')

        # Build short display name
        parts = []
        if city:
            parts.append(city)
        if state:
            parts.append(state)
        if country:
            parts.append(country)

        display_name = ", ".join(parts) if parts else "Unknown Location"

        return {
            'city': city,
            'state': state,
            'country': country,
            'display_name': display_name,
            'full_address': data.get('display_name', '')
        }

    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """
        Get geocoding result from Firebase cache

        Args:
            key: Cache key (e.g., "geocode_37_7749_n122_4194")

        Returns:
            Cached location dict or None if not found
        """
        try:
            ref = db.reference(f'geocoding_cache/{key}')
            cached = ref.get()

            if cached:
                # Remove cache metadata before returning
                result = {k: v for k, v in cached.items() if k not in ['cached_at', 'ttl_days']}
                logger.info(f"Geocoding cache HIT: {key} -> {result.get('display_name')}")
                return result

        except Exception as e:
            logger.error(f"Geocoding cache read error: {e}")

        return None

    def _save_to_cache(self, key: str, data: Dict, ttl_days: int = 30):
        """
        Save geocoding result to Firebase cache

        Args:
            key: Cache key
            data: Location data to cache
            ttl_days: Time-to-live in days (default: 30)
        """
        try:
            ref = db.reference(f'geocoding_cache/{key}')
            ref.set({
                **data,
                'cached_at': time.time(),
                'ttl_days': ttl_days
            })
            logger.info(f"Geocoding cached: {key} -> {data.get('display_name')}")

        except Exception as e:
            logger.error(f"Geocoding cache write error: {e}")
