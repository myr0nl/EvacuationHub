"""
Firebase credentials setup for multiple deployment environments.

Supports two methods of providing Firebase credentials:
1. Base64-encoded JSON (FIREBASE_CREDENTIALS_BASE64) - for Railway, Heroku, etc.
2. File path (FIREBASE_CREDENTIALS_PATH) - for local development, VPS

This allows seamless deployment to platforms that don't support file uploads.
"""

import os
import json
import base64
from firebase_admin import credentials


def get_firebase_credentials():
    """
    Get Firebase credentials from environment.

    Supports two methods:
    1. FIREBASE_CREDENTIALS_BASE64 - base64 encoded service account JSON (for Railway/Heroku)
    2. FIREBASE_CREDENTIALS_PATH - path to service account JSON file (for local/VPS)

    Returns:
        firebase_admin.credentials.Certificate: Firebase credentials object

    Raises:
        ValueError: If no valid credentials are found

    Examples:
        >>> # In Railway/Heroku environment:
        >>> os.environ['FIREBASE_CREDENTIALS_BASE64'] = '<base64_encoded_json>'
        >>> cred = get_firebase_credentials()

        >>> # In local/VPS environment:
        >>> os.environ['FIREBASE_CREDENTIALS_PATH'] = '/path/to/serviceAccount.json'
        >>> cred = get_firebase_credentials()
    """
    # Method 1: Base64 encoded credentials (Railway/Heroku/PaaS)
    base64_creds = os.getenv('FIREBASE_CREDENTIALS_BASE64')
    if base64_creds:
        try:
            # Decode base64 to JSON string
            json_str = base64.b64decode(base64_creds).decode('utf-8')
            cred_dict = json.loads(json_str)
            return credentials.Certificate(cred_dict)
        except Exception as e:
            raise ValueError(f"Failed to decode FIREBASE_CREDENTIALS_BASE64: {e}")

    # Method 2: File path (local development, VPS)
    cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
    if cred_path and os.path.exists(cred_path):
        return credentials.Certificate(cred_path)

    # No valid credentials found
    raise ValueError(
        "No Firebase credentials found. Set either:\n"
        "  - FIREBASE_CREDENTIALS_BASE64 (base64-encoded service account JSON)\n"
        "  - FIREBASE_CREDENTIALS_PATH (path to service account JSON file)\n\n"
        "To generate FIREBASE_CREDENTIALS_BASE64:\n"
        "  base64 -i /path/to/serviceAccount.json | tr -d '\\n'"
    )
