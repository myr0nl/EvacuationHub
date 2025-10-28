"""
Configuration file for the Disaster Alert System backend.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration"""
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

    # Firebase
    FIREBASE_CREDENTIALS_PATH = os.getenv('FIREBASE_CREDENTIALS_PATH')
    FIREBASE_DATABASE_URL = os.getenv('FIREBASE_DATABASE_URL')

    # API Keys for Phase 2
    NASA_FIRMS_API_KEY = os.getenv('NASA_FIRMS_API_KEY')
    NOAA_API_KEY = os.getenv('NOAA_API_KEY')

    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(',')

    # Rate Limiting (for future use)
    RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'False').lower() == 'true'
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', '60'))


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
