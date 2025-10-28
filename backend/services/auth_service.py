"""
Firebase Authentication Service
Handles user registration, login, token verification, and profile management
"""
from firebase_admin import auth, db
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
import logging
import re
from bleach import clean
from utils.secure_logging import redact_pii, hash_user_id

logger = logging.getLogger(__name__)


class AuthService:
    """Firebase Authentication integration for user management"""

    def __init__(self):
        """Initialize auth service"""
        pass

    @staticmethod
    def validate_password(password: str) -> Tuple[bool, str]:
        """
        Validate password strength

        Args:
            password: Password to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters"
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        if not re.search(r'[0-9]', password):
            return False, "Password must contain at least one digit"
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)"
        return True, "Password is valid"

    @staticmethod
    def validate_email(email: str) -> Tuple[bool, str]:
        """
        Validate email format

        Args:
            email: Email address to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Email regex pattern
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if not re.match(email_pattern, email):
            return False, "Invalid email format"

        # Check length constraints
        if len(email) > 254:  # RFC 5321
            return False, "Email address is too long"

        return True, "Email is valid"

    @staticmethod
    def sanitize_display_name(name: str) -> str:
        """
        Sanitize display name to prevent XSS attacks

        Args:
            name: Display name to sanitize

        Returns:
            Sanitized display name (max 50 chars, HTML stripped)
        """
        if not name:
            return ""

        # Remove all HTML tags, keep only text
        clean_name = clean(name, tags=[], strip=True)

        # Limit length to 50 characters
        clean_name = clean_name[:50]

        # Strip leading/trailing whitespace
        clean_name = clean_name.strip()

        return clean_name

    def create_user(self, email: str, password: str, display_name: str = None) -> Dict:
        """
        Create a new user with email/password authentication

        Args:
            email: User email address
            password: User password (min 8 characters, strong requirements)
            display_name: Optional display name

        Returns:
            Dict with user_id, email, and initial credibility data

        Raises:
            ValueError: If user creation fails or validation fails
        """
        try:
            # Validate email format
            email_valid, email_error = self.validate_email(email)
            if not email_valid:
                raise ValueError(email_error)

            # Validate password strength
            password_valid, password_error = self.validate_password(password)
            if not password_valid:
                raise ValueError(password_error)

            # Sanitize display name
            if display_name:
                display_name = self.sanitize_display_name(display_name)

            # Create Firebase Auth user
            user_record = auth.create_user(
                email=email,
                password=password,
                display_name=display_name
            )

            # Initialize user profile in Realtime Database
            user_data = {
                'email': email,
                'display_name': display_name or email.split('@')[0],
                'created_at': datetime.now(timezone.utc).isoformat(),
                'last_active': datetime.now(timezone.utc).isoformat(),
                'credibility_score': 50,  # Default neutral credibility
                'credibility_level': 'Neutral',
                'total_reports': 0,
                'successful_reports': 0,
                'flagged_reports': 0,
                'last_report_timestamp': None,
                'oauth_provider': 'email'
            }

            # Save to Firebase Realtime Database
            user_ref = db.reference(f'users/{user_record.uid}')
            user_ref.set(user_data)

            logger.info(redact_pii(f"User created successfully: {email} (UID: {hash_user_id(user_record.uid)})"))

            return {
                'user_id': user_record.uid,
                'email': email,
                'display_name': user_data['display_name'],
                'credibility_score': 50,
                'credibility_level': 'Neutral'
            }

        except auth.EmailAlreadyExistsError:
            raise ValueError('Email already in use')
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise ValueError(f'Failed to create user: {str(e)}')

    def verify_id_token(self, id_token: str) -> Dict:
        """
        Verify Firebase ID token and return user data

        Args:
            id_token: Firebase ID token from frontend

        Returns:
            Dict with user_id, email, email_verified

        Raises:
            ValueError: If token is invalid
        """
        try:
            # Verify token using Firebase Admin SDK
            decoded_token = auth.verify_id_token(id_token)

            # Get user profile from database
            user_id = decoded_token['uid']
            user_ref = db.reference(f'users/{user_id}')
            user_data = user_ref.get()

            if not user_data:
                # Create minimal profile if it doesn't exist (OAuth users)
                user_data = self._create_oauth_profile(decoded_token)

            # Update last active timestamp
            user_ref.child('last_active').set(datetime.now(timezone.utc).isoformat())

            return {
                'user_id': user_id,
                'email': decoded_token.get('email'),
                'email_verified': decoded_token.get('email_verified', False),
                'credibility_score': user_data.get('credibility_score', 50),
                'credibility_level': user_data.get('credibility_level', 'Neutral'),
                'display_name': user_data.get('display_name', decoded_token.get('name', 'User'))
            }

        except auth.InvalidIdTokenError:
            raise ValueError('Invalid ID token')
        except auth.ExpiredIdTokenError:
            raise ValueError('Token has expired')
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            raise ValueError(f'Token verification failed: {str(e)}')

    def _create_oauth_profile(self, decoded_token: Dict) -> Dict:
        """
        Create user profile for OAuth users (Google/Facebook)

        Args:
            decoded_token: Decoded Firebase token with user info

        Returns:
            User profile data
        """
        user_id = decoded_token['uid']
        email = decoded_token.get('email', 'unknown')
        display_name = decoded_token.get('name', email.split('@')[0])

        # OAuth users get +5 bonus credibility (verified identity)
        user_data = {
            'email': email,
            'display_name': display_name,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'last_active': datetime.now(timezone.utc).isoformat(),
            'credibility_score': 55,  # OAuth bonus: 50 + 5
            'credibility_level': 'Neutral',
            'total_reports': 0,
            'successful_reports': 0,
            'flagged_reports': 0,
            'last_report_timestamp': None,
            'oauth_provider': decoded_token.get('firebase', {}).get('sign_in_provider', 'google')
        }

        # Save to database
        user_ref = db.reference(f'users/{user_id}')
        user_ref.set(user_data)

        logger.info(redact_pii(f"OAuth user profile created: {email} (UID: {hash_user_id(user_id)})"))

        return user_data

    def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """
        Get user profile data

        Args:
            user_id: Firebase user ID

        Returns:
            User profile dict or None if not found
        """
        try:
            user_ref = db.reference(f'users/{user_id}')
            user_data = user_ref.get()

            if not user_data:
                return None

            # Get recent reports count
            reports_ref = db.reference(f'user_reports/{user_id}/reports')
            reports = reports_ref.get() or {}

            user_data['total_reports'] = len(reports)

            return user_data

        except Exception as e:
            logger.error(f"Error fetching user profile: {e}")
            return None

    def update_user_profile(self, user_id: str, updates: Dict) -> Dict:
        """
        Update user profile (display_name, etc.)

        Args:
            user_id: Firebase user ID
            updates: Dict with fields to update (e.g., {'display_name': 'New Name'})

        Returns:
            Updated user profile

        Raises:
            ValueError: If update fails
        """
        try:
            # Whitelist of allowed updates (security)
            allowed_fields = ['display_name']
            filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

            if not filtered_updates:
                raise ValueError('No valid fields to update')

            # Sanitize display_name if present
            if 'display_name' in filtered_updates:
                sanitized_name = self.sanitize_display_name(filtered_updates['display_name'])
                filtered_updates['display_name'] = sanitized_name

                # Update Firebase Auth
                auth.update_user(user_id, display_name=sanitized_name)

            # Update database
            user_ref = db.reference(f'users/{user_id}')
            user_ref.update(filtered_updates)

            # Get updated profile
            return self.get_user_profile(user_id)

        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            raise ValueError(f'Failed to update profile: {str(e)}')

    def delete_user(self, user_id: str):
        """
        Delete user account (GDPR compliance)

        Args:
            user_id: Firebase user ID

        Raises:
            ValueError: If deletion fails
        """
        try:
            # Delete from Firebase Auth
            auth.delete_user(user_id)

            # Delete user data from database
            user_ref = db.reference(f'users/{user_id}')
            user_ref.delete()

            # Delete user reports tracking
            reports_ref = db.reference(f'user_reports/{user_id}')
            reports_ref.delete()

            logger.info(f"User deleted: {user_id}")

        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            raise ValueError(f'Failed to delete user: {str(e)}')

    def revoke_refresh_tokens(self, user_id: str):
        """
        Revoke all refresh tokens for a user (force logout)

        Args:
            user_id: Firebase user ID

        Raises:
            ValueError: If revocation fails
        """
        try:
            auth.revoke_refresh_tokens(user_id)
            logger.info(f"Refresh tokens revoked for user: {user_id}")

        except Exception as e:
            logger.error(f"Error revoking tokens: {e}")
            raise ValueError(f'Failed to revoke tokens: {str(e)}')
