"""
URL validation utilities for secure image URL handling.

Prevents SSRF (Server-Side Request Forgery) attacks by validating external URLs
before the application fetches them.

Usage:
    from utils.url_validator import validate_image_url

    is_valid, error = validate_image_url(user_provided_url)
    if not is_valid:
        return jsonify({'error': error}), 400
"""

from urllib.parse import urlparse
from typing import Tuple


# Private IP ranges to block (SSRF prevention)
PRIVATE_IP_RANGES = [
    '10.',  # 10.0.0.0/8
    '172.16.', '172.17.', '172.18.', '172.19.',  # 172.16.0.0/12
    '172.20.', '172.21.', '172.22.', '172.23.',
    '172.24.', '172.25.', '172.26.', '172.27.',
    '172.28.', '172.29.', '172.30.', '172.31.',
    '192.168.',  # 192.168.0.0/16
]

# Allowed image file extensions
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']


def validate_image_url(url: str) -> Tuple[bool, str]:
    """
    Validate an image URL to prevent SSRF and malicious content injection.

    Security checks:
    1. URL must use HTTPS (prevent downgrade attacks)
    2. Hostname must not be localhost or private IP (prevent SSRF)
    3. File extension must be an allowed image type
    4. URL length must be reasonable (< 2048 characters)

    Args:
        url: The URL to validate

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
            - (True, None) if valid
            - (False, error_message) if invalid

    Examples:
        >>> validate_image_url('https://example.com/image.jpg')
        (True, None)

        >>> validate_image_url('http://example.com/image.jpg')
        (False, 'Only HTTPS URLs are allowed')

        >>> validate_image_url('https://localhost/image.jpg')
        (False, 'Local URLs not allowed')
    """
    # Allow empty/None URLs (optional field)
    if not url:
        return (True, None)

    # Check URL length
    if len(url) > 2048:
        return (False, 'URL too long (max 2048 characters)')

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception:
        return (False, 'Invalid URL format')

    # Check scheme (must be HTTPS)
    if parsed.scheme != 'https':
        return (False, 'Only HTTPS URLs are allowed')

    # Check hostname exists
    hostname = parsed.hostname
    if not hostname:
        return (False, 'Invalid hostname')

    # Block localhost and 127.x.x.x
    if hostname in ['localhost', '127.0.0.1', '0.0.0.0', '::1']:
        return (False, 'Local URLs not allowed')

    # Block private IP ranges (SSRF prevention)
    if any(hostname.startswith(prefix) for prefix in PRIVATE_IP_RANGES):
        return (False, 'Private network URLs not allowed')

    # Check file extension
    path_lower = parsed.path.lower()
    if not any(path_lower.endswith(ext) for ext in ALLOWED_IMAGE_EXTENSIONS):
        allowed_list = ', '.join(ALLOWED_IMAGE_EXTENSIONS)
        return (False, f'Only image files allowed: {allowed_list}')

    # All checks passed
    return (True, None)


def validate_url(url: str, allowed_schemes: list = None) -> Tuple[bool, str]:
    """
    General URL validation (not specific to images).

    Args:
        url: The URL to validate
        allowed_schemes: List of allowed schemes (default: ['http', 'https'])

    Returns:
        Tuple[bool, str]: (is_valid, error_message)

    Examples:
        >>> validate_url('https://example.com/api/data')
        (True, None)

        >>> validate_url('ftp://example.com/file')
        (False, 'Scheme not allowed: ftp')
    """
    if not url:
        return (True, None)

    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']

    # Check URL length
    if len(url) > 2048:
        return (False, 'URL too long (max 2048 characters)')

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception:
        return (False, 'Invalid URL format')

    # Check scheme
    if parsed.scheme not in allowed_schemes:
        return (False, f'Scheme not allowed: {parsed.scheme}')

    # Check hostname exists
    if not parsed.hostname:
        return (False, 'Invalid hostname')

    return (True, None)
