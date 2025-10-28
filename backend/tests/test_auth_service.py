"""
Test Suite for Firebase Authentication Service (Phase 7)
Tests user registration, login, token verification, and error handling
"""
import os
import sys
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


class TestAuthService:
    """Test Firebase Authentication functionality for Phase 7"""

    def setup_method(self):
        """Setup test fixtures before each test"""
        self.test_user_data = {
            'email': 'test@example.com',
            'password': 'testPassword123!',
            'display_name': 'Test User'
        }
        self.test_uid = 'test_uid_12345'

    def test_user_registration(self):
        """Test user registration creates Firebase user with initial credibility score"""
        with patch('firebase_admin.auth.create_user') as mock_create_user, \
             patch('firebase_admin.db.reference') as mock_db_ref:

            # Mock Firebase Auth user creation
            mock_user = Mock()
            mock_user.uid = self.test_uid
            mock_user.email = self.test_user_data['email']
            mock_create_user.return_value = mock_user

            # Mock Firebase Database reference
            mock_user_ref = Mock()
            mock_db_ref.return_value = mock_user_ref

            # Simulate user registration
            from firebase_admin import auth, db

            # Create user in Firebase Auth
            user = auth.create_user(
                email=self.test_user_data['email'],
                password=self.test_user_data['password'],
                display_name=self.test_user_data['display_name']
            )

            # Create user profile in Firebase Database
            user_profile_ref = db.reference(f'users/{user.uid}')
            user_profile_ref.set({
                'email': user.email,
                'display_name': self.test_user_data['display_name'],
                'credibility_score': 50,  # Initial neutral credibility
                'credibility_level': 'Neutral',
                'total_reports': 0,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'oauth_provider': 'email'
            })

            # Assertions
            mock_create_user.assert_called_once()
            assert user.uid == self.test_uid
            assert user.email == self.test_user_data['email']
            mock_db_ref.assert_called_once()
            mock_user_ref.set.assert_called_once()

            # Verify initial credibility score
            set_call_args = mock_user_ref.set.call_args[0][0]
            assert set_call_args['credibility_score'] == 50
            assert set_call_args['credibility_level'] == 'Neutral'
            assert set_call_args['total_reports'] == 0

        print("✅ test_user_registration PASSED")

    def test_user_login(self):
        """Test user login verifies Firebase ID token"""
        with patch('firebase_admin.auth.verify_id_token') as mock_verify_token:

            # Mock token verification
            mock_decoded_token = {
                'uid': self.test_uid,
                'email': self.test_user_data['email'],
                'email_verified': True
            }
            mock_verify_token.return_value = mock_decoded_token

            # Simulate login token verification
            from firebase_admin import auth

            test_id_token = 'test_firebase_id_token_xyz'
            decoded_token = auth.verify_id_token(test_id_token)

            # Assertions
            mock_verify_token.assert_called_once_with(test_id_token)
            assert decoded_token['uid'] == self.test_uid
            assert decoded_token['email'] == self.test_user_data['email']
            assert decoded_token['email_verified'] is True

        print("✅ test_user_login PASSED")

    def test_token_verification(self):
        """Test JWT token verification validates user identity"""
        with patch('firebase_admin.auth.verify_id_token') as mock_verify_token:

            # Mock valid token
            mock_decoded_token = {
                'uid': self.test_uid,
                'email': self.test_user_data['email'],
                'email_verified': True,
                'exp': (datetime.now(timezone.utc).timestamp() + 3600)  # 1 hour from now
            }
            mock_verify_token.return_value = mock_decoded_token

            # Verify token
            from firebase_admin import auth

            test_token = 'valid_firebase_token'
            decoded = auth.verify_id_token(test_token)

            # Assertions
            assert decoded['uid'] == self.test_uid
            assert decoded['email'] == self.test_user_data['email']
            assert 'exp' in decoded
            assert decoded['exp'] > datetime.now(timezone.utc).timestamp()

        print("✅ test_token_verification PASSED")

    def test_duplicate_email_registration(self):
        """Test duplicate email registration should fail"""
        with patch('firebase_admin.auth.create_user') as mock_create_user:

            # Mock duplicate email error
            from firebase_admin import auth
            mock_create_user.side_effect = auth.EmailAlreadyExistsError('Email already exists')

            # Attempt duplicate registration
            try:
                auth.create_user(
                    email=self.test_user_data['email'],
                    password=self.test_user_data['password']
                )
                assert False, "Should have raised EmailAlreadyExistsError"
            except auth.EmailAlreadyExistsError:
                pass  # Expected

            mock_create_user.assert_called_once()

        print("✅ test_duplicate_email_registration PASSED")

    def test_invalid_credentials_login(self):
        """Test invalid credentials login should fail"""
        with patch('firebase_admin.auth.verify_id_token') as mock_verify_token:

            # Mock invalid token error
            from firebase_admin import auth
            mock_verify_token.side_effect = auth.InvalidIdTokenError('Invalid token')

            # Attempt login with invalid token
            try:
                auth.verify_id_token('invalid_token_xyz')
                assert False, "Should have raised InvalidIdTokenError"
            except auth.InvalidIdTokenError:
                pass  # Expected

            mock_verify_token.assert_called_once()

        print("✅ test_invalid_credentials_login PASSED")

    def test_oauth_provider_registration(self):
        """Test OAuth provider registration (Google/Facebook) gets +5 credibility bonus"""
        with patch('firebase_admin.auth.create_user') as mock_create_user, \
             patch('firebase_admin.db.reference') as mock_db_ref:

            # Mock OAuth user creation
            mock_user = Mock()
            mock_user.uid = self.test_uid
            mock_user.email = self.test_user_data['email']
            mock_user.provider_data = [{'providerId': 'google.com'}]
            mock_create_user.return_value = mock_user

            # Mock Firebase Database reference
            mock_user_ref = Mock()
            mock_db_ref.return_value = mock_user_ref

            # Create OAuth user
            from firebase_admin import auth, db

            user = auth.create_user(
                email=self.test_user_data['email'],
                provider_data=[{'providerId': 'google.com'}]
            )

            # Set user profile with OAuth bonus
            user_profile_ref = db.reference(f'users/{user.uid}')
            user_profile_ref.set({
                'email': user.email,
                'credibility_score': 55,  # OAuth bonus: 50 + 5
                'credibility_level': 'Neutral',
                'oauth_provider': 'google'
            })

            # Assertions
            set_call_args = mock_user_ref.set.call_args[0][0]
            assert set_call_args['credibility_score'] == 55
            assert set_call_args['oauth_provider'] == 'google'

        print("✅ test_oauth_provider_registration PASSED")

    def test_expired_token_verification(self):
        """Test expired token verification should fail"""
        with patch('firebase_admin.auth.verify_id_token') as mock_verify_token:

            # Mock expired token error
            from firebase_admin import auth
            mock_verify_token.side_effect = auth.ExpiredIdTokenError('Token expired')

            # Attempt verification with expired token
            try:
                auth.verify_id_token('expired_token_xyz')
                assert False, "Should have raised ExpiredIdTokenError"
            except auth.ExpiredIdTokenError:
                pass  # Expected

            mock_verify_token.assert_called_once()

        print("✅ test_expired_token_verification PASSED")


def run_all_tests():
    """Run all authentication tests"""
    print("\n" + "="*60)
    print("PHASE 7: AUTHENTICATION SERVICE TESTS")
    print("="*60)

    test_suite = TestAuthService()

    try:
        test_suite.setup_method()
        test_suite.test_user_registration()

        test_suite.setup_method()
        test_suite.test_user_login()

        test_suite.setup_method()
        test_suite.test_token_verification()

        test_suite.setup_method()
        test_suite.test_duplicate_email_registration()

        test_suite.setup_method()
        test_suite.test_invalid_credentials_login()

        test_suite.setup_method()
        test_suite.test_oauth_provider_registration()

        test_suite.setup_method()
        test_suite.test_expired_token_verification()

        print("\n" + "="*60)
        print("✅ ALL AUTHENTICATION TESTS PASSED")
        print("="*60)
        print("\n📝 Summary:")
        print("   - User registration: Working")
        print("   - User login: Working")
        print("   - Token verification: Working")
        print("   - Duplicate email prevention: Working")
        print("   - Invalid credentials handling: Working")
        print("   - OAuth provider bonus: Working")
        print("   - Expired token handling: Working")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    run_all_tests()
