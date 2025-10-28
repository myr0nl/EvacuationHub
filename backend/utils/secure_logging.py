"""
Secure logging utilities with PII redaction.

This module provides functions to redact personally identifiable information (PII)
from log messages to comply with privacy regulations (GDPR, CCPA) and security best practices.

Usage:
    from utils.secure_logging import redact_pii, hash_user_id

    logger.info(redact_pii(f"User {email} logged in from {ip_address}"))
    # Output: "User [EMAIL_REDACTED] logged in from [IP_REDACTED]"

    logger.info(f"Report created by user {hash_user_id(user_id)}")
    # Output: "Report created by user abc123def456..."
"""

import re
import hashlib
from typing import Optional


def redact_pii(text: str) -> str:
    """
    Redact personally identifiable information from log messages.

    Redacts:
    - Email addresses → [EMAIL_REDACTED]
    - Precise coordinates (4+ decimal places) → [COORD_REDACTED]
    - IP addresses → [IP_REDACTED]
    - Phone numbers → [PHONE_REDACTED]
    - Credit card numbers → [CARD_REDACTED]

    Args:
        text: The log message to redact

    Returns:
        str: The redacted log message

    Examples:
        >>> redact_pii("User john@example.com logged in")
        'User [EMAIL_REDACTED] logged in'

        >>> redact_pii("Location: 37.7749, -122.4194")
        'Location: [COORD_REDACTED], [COORD_REDACTED]'
    """
    if not text:
        return text

    # Redact email addresses
    text = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        '[EMAIL_REDACTED]',
        text
    )

    # Redact precise coordinates (4+ decimal places = ~11m accuracy)
    # Keep rough coordinates (1-3 decimals = city-level) for debugging
    text = re.sub(
        r'-?\d{1,3}\.\d{4,}',
        '[COORD_REDACTED]',
        text
    )

    # Redact IP addresses (IPv4 and IPv6)
    text = re.sub(
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        '[IP_REDACTED]',
        text
    )
    text = re.sub(
        r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b',
        '[IP_REDACTED]',
        text
    )

    # Redact phone numbers (US format)
    text = re.sub(
        r'\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        '[PHONE_REDACTED]',
        text
    )

    # Redact credit card numbers (13-19 digits, optionally separated)
    text = re.sub(
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4,7}\b',
        '[CARD_REDACTED]',
        text
    )

    return text


def hash_user_id(user_id: str, length: int = 16) -> str:
    """
    Create a one-way hash of a user ID for logging.

    Uses SHA-256 to create a consistent, anonymized identifier that:
    - Cannot be reversed to find the original user ID
    - Always produces the same hash for the same user ID
    - Allows correlation of logs for the same user

    Args:
        user_id: The user ID to hash
        length: Length of the returned hash (default: 16 characters)

    Returns:
        str: Truncated SHA-256 hash of the user ID

    Examples:
        >>> hash_user_id("user_12345")
        'a1b2c3d4e5f6g7h8'

        >>> hash_user_id("user_12345")  # Same input = same output
        'a1b2c3d4e5f6g7h8'
    """
    if not user_id:
        return '[NO_USER_ID]'

    return hashlib.sha256(user_id.encode()).hexdigest()[:length]


def redact_coordinates(lat: Optional[float], lon: Optional[float], precision: int = 2) -> tuple[str, str]:
    """
    Redact coordinates to a safe precision level for logging.

    Precision levels:
    - 0 decimals: ~111 km (country level)
    - 1 decimal: ~11 km (city level)
    - 2 decimals: ~1.1 km (neighborhood level) **RECOMMENDED**
    - 3 decimals: ~110 m (street level)
    - 4+ decimals: ~11 m (building level) **TOO PRECISE FOR LOGS**

    Args:
        lat: Latitude coordinate
        lon: Longitude coordinate
        precision: Number of decimal places to keep (default: 2)

    Returns:
        tuple[str, str]: Rounded coordinates as strings, or ('[REDACTED]', '[REDACTED]') if None

    Examples:
        >>> redact_coordinates(37.7749, -122.4194, precision=2)
        ('37.77', '-122.42')

        >>> redact_coordinates(None, None)
        ('[REDACTED]', '[REDACTED]')
    """
    if lat is None or lon is None:
        return ('[REDACTED]', '[REDACTED]')

    return (
        f"{lat:.{precision}f}",
        f"{lon:.{precision}f}"
    )


def safe_log_dict(data: dict, redact_keys: Optional[list[str]] = None) -> dict:
    """
    Create a safe version of a dictionary for logging by redacting sensitive keys.

    Args:
        data: Dictionary to sanitize
        redact_keys: List of keys to redact (default: common PII fields)

    Returns:
        dict: Dictionary with sensitive values redacted

    Examples:
        >>> safe_log_dict({'email': 'john@example.com', 'name': 'John'})
        {'email': '[REDACTED]', 'name': 'John'}

        >>> safe_log_dict({'api_key': 'secret123', 'count': 5}, redact_keys=['api_key'])
        {'api_key': '[REDACTED]', 'count': 5}
    """
    if redact_keys is None:
        # Default sensitive keys
        redact_keys = [
            'email', 'password', 'token', 'api_key', 'secret',
            'credit_card', 'ssn', 'phone', 'address',
            'latitude', 'longitude', 'user_id', 'ip_address'
        ]

    safe_data = {}
    for key, value in data.items():
        if any(sensitive_key in key.lower() for sensitive_key in redact_keys):
            safe_data[key] = '[REDACTED]'
        elif isinstance(value, dict):
            safe_data[key] = safe_log_dict(value, redact_keys)
        elif isinstance(value, list):
            safe_data[key] = [
                safe_log_dict(item, redact_keys) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            safe_data[key] = value

    return safe_data
