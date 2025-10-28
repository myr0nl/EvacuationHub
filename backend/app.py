from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import firebase_admin
from firebase_admin import credentials, db, auth as firebase_auth
import os
import logging
from dotenv import load_dotenv
from services.nasa_firms import NASAFirmsService
from services.noaa_weather import NOAAWeatherService
from services.gdacs_service import GDACSService
from services.fema_disaster_service import FEMADisasterService
from services.usgs_earthquake_service import USGSEarthquakeService
from services.cal_fire_service import CalFireService
from services.cal_oes_service import CalOESService
from services.cache_manager import CacheManager
from services.geocoding_service import GeocodingService
from services.confidence_scorer import ConfidenceScorer
from services.auth_service import AuthService
from services.credibility_service import CredibilityService
from services.proximity_alert_service import ProximityAlertService
from services.time_decay import TimeDecayService
from services.safe_zone_service import SafeZoneService
from services.hifld_shelter_service import HIFLDShelterService
from services.route_calculation_service import RouteCalculationService
from services.here_routing_service import HERERoutingService
from services.google_maps_routing_service import GoogleMapsRoutingService
from utils.geo import haversine_distance
from utils.validators import CoordinateValidator, DisasterValidator
import math
import re
from functools import wraps
from datetime import datetime, timedelta, timezone

load_dotenv()

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Security: Request size limits to prevent DoS attacks
# 10 MB max request size (sufficient for disaster reports with images)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

# CORS Configuration - Environment-aware origin restriction
if os.getenv('FLASK_ENV') == 'production':
    # Production: Only allow explicitly configured frontend URL
    FRONTEND_URL = os.getenv('FRONTEND_URL')
    if not FRONTEND_URL:
        raise ValueError("FRONTEND_URL must be set in production environment")
    ALLOWED_ORIGINS = [FRONTEND_URL]
else:
    # Development: Allow local origins + optional mobile testing
    ALLOWED_ORIGINS = [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost:3001',
        'http://127.0.0.1:3001'
    ]
    # Optional: Add mobile device URL from environment
    dev_mobile_url = os.getenv('DEV_MOBILE_URL', '')
    if dev_mobile_url:
        ALLOWED_ORIGINS.append(dev_mobile_url)

# Remove empty strings
ALLOWED_ORIGINS = [origin for origin in ALLOWED_ORIGINS if origin]

CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)

# Security Headers Middleware
@app.after_request
def set_security_headers(response):
    """
    Add security headers to all responses.

    Security headers protect against common web vulnerabilities:
    - HSTS: Forces HTTPS for 1 year (only in production)
    - X-Frame-Options: Prevents clickjacking
    - X-Content-Type-Options: Prevents MIME sniffing
    - CSP: Restricts resource loading to prevent XSS
    - Referrer-Policy: Controls referrer information leakage
    - Permissions-Policy: Disables unnecessary browser APIs
    """
    # Force HTTPS (Strict Transport Security) - only in production
    if os.getenv('FLASK_ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'

    # Prevent MIME sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'

    # Content Security Policy
    # Note: Adjusted for React development (unsafe-inline, unsafe-eval) and external APIs
    csp_directives = [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # React requires unsafe-inline/eval
        "style-src 'self' 'unsafe-inline'",  # Leaflet requires inline styles
        "img-src 'self' data: https:",  # Allow map tiles from any HTTPS source
        "connect-src 'self' https://api.openrouteservice.org https://router.hereapi.com https://routes.googleapis.com https://firms.modaps.eosdis.nasa.gov https://api.weather.gov https://www.gdacs.org https://services.arcgis.com",
        "font-src 'self' data:",
        "frame-ancestors 'none'"
    ]
    response.headers['Content-Security-Policy'] = "; ".join(csp_directives)

    # Referrer policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

    # Permissions policy (disable unnecessary features)
    response.headers['Permissions-Policy'] = 'geolocation=(self), camera=(), microphone=(), payment=()'

    return response

# Rate Limiting Configuration
# Security: Use Redis in production for distributed rate limiting across multiple servers
# Set REDIS_URL environment variable to enable: redis://your-redis-host:6379
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.getenv('REDIS_URL', 'memory://')  # Falls back to memory for development
)

# Initialize data services
nasa_service = NASAFirmsService()
noaa_service = NOAAWeatherService()
gdacs_service = GDACSService()
fema_service = FEMADisasterService()
usgs_service = USGSEarthquakeService()
cal_fire_service = CalFireService()
cal_oes_service = CalOESService()
cache_manager = CacheManager()
geocoding_service = GeocodingService(cache_manager)  # Phase 5: Location enrichment
confidence_scorer = ConfidenceScorer(geocoding_service=geocoding_service)  # Pass geocoding service
auth_service = AuthService()  # Phase 7: Firebase Authentication
credibility_service = CredibilityService()  # Phase 7: User Credibility System
proximity_alert_service = None  # Phase 8: Proximity Alert Service (initialized after Firebase)
safe_zone_service = None  # Phase 10: Safe Zone Service (initialized after Firebase)
route_service = None  # Phase 10: Route Calculation Service (initialized after Firebase)

# Initialize Firebase
# Supports two methods:
# 1. FIREBASE_CREDENTIALS_BASE64 (base64-encoded JSON) - for Railway, Heroku, etc.
# 2. FIREBASE_CREDENTIALS_PATH (file path) - for local development, VPS
from firebase_setup import get_firebase_credentials

try:
    cred = get_firebase_credentials()
    firebase_admin.initialize_app(cred, {
        'databaseURL': os.getenv('FIREBASE_DATABASE_URL')
    })
    # Initialize ProximityAlertService, SafeZoneService, and RouteCalculationService after Firebase is ready
    proximity_alert_service = ProximityAlertService(db, cache_manager)

    # Initialize HIFLD shelter service (Phase 9)
    hifld_service = HIFLDShelterService(confidence_scorer=confidence_scorer)

    # Initialize SafeZoneService with HIFLD integration
    safe_zone_service = SafeZoneService(db, cache_manager, hifld_service=hifld_service)

    # Initialize routing services
    here_service = HERERoutingService()  # HERE API fallback (optional)
    google_service = GoogleMapsRoutingService()  # Google Maps baseline shortest path (optional)

    try:
        route_service = RouteCalculationService(
            db=db,
            here_service=here_service,
            google_service=google_service
        )
        logger.info("RouteCalculationService initialized successfully")
    except ValueError as e:
        logger.warning(f"RouteCalculationService not initialized: {e}")
        route_service = None

except ValueError as e:
    logger.error(f"Firebase initialization failed: {e}")
    logger.error("Set either FIREBASE_CREDENTIALS_BASE64 or FIREBASE_CREDENTIALS_PATH in environment")
    raise

# Helper function for spatial queries
def _get_nearby_user_reports(lat: float, lon: float, radius_mi: float = 50) -> list:
    """
    Fetch ONLY user-submitted reports within radius (fast version for submission)

    This function only fetches user reports for fast initial confidence scoring.
    Official data sources are fetched later in the background /enhance-ai endpoint.

    Args:
        lat: Latitude of center point
        lon: Longitude of center point
        radius_mi: Search radius in miles (default 50 miles)

    Returns:
        List of nearby user reports only
    """
    nearby = []

    try:
        # Get user-submitted reports ONLY (skip official data for speed)
        user_reports_ref = db.reference('reports')
        user_reports_dict = user_reports_ref.get() or {}

        for key, report in user_reports_dict.items():
            if 'latitude' in report and 'longitude' in report:
                distance = haversine_distance(lat, lon, report['latitude'], report['longitude'])
                if distance <= radius_mi:
                    nearby.append({**report, 'id': key, 'source': report.get('source', 'user_report')})

    except Exception as e:
        logger.error(f"Error fetching nearby user reports: {e}")

    return nearby


def _get_nearby_reports(lat: float, lon: float, radius_mi: float = 50) -> list:
    """
    Fetch all reports (user reports + official data) within radius of given location

    Args:
        lat: Latitude of center point
        lon: Longitude of center point
        radius_mi: Search radius in miles (default 50 miles)

    Returns:
        List of nearby reports from all sources
    """
    nearby = []

    try:
        # Get user-submitted reports
        user_reports_ref = db.reference('reports')
        user_reports_dict = user_reports_ref.get() or {}

        for key, report in user_reports_dict.items():
            if 'latitude' in report and 'longitude' in report:
                distance = haversine_distance(lat, lon, report['latitude'], report['longitude'])
                if distance <= radius_mi:
                    nearby.append({**report, 'id': key, 'source': report.get('source', 'user_report')})

        # Get wildfire data
        wildfire_ref = db.reference('public_data_cache/wildfires/data')
        wildfires = wildfire_ref.get() or []

        for fire in wildfires:
            if 'latitude' in fire and 'longitude' in fire:
                distance = haversine_distance(lat, lon, fire['latitude'], fire['longitude'])
                if distance <= radius_mi:
                    nearby.append({**fire, 'source': 'nasa_firms'})

        # Get weather alerts
        weather_ref = db.reference('public_data_cache/weather_alerts/data')
        alerts = weather_ref.get() or []

        for alert in alerts:
            if 'latitude' in alert and 'longitude' in alert:
                distance = haversine_distance(lat, lon, alert['latitude'], alert['longitude'])
                if distance <= radius_mi:
                    nearby.append({**alert, 'source': 'noaa'})

        # Get GDACS events
        gdacs_ref = db.reference('public_data_cache/gdacs_events/data')
        gdacs_events = gdacs_ref.get() or []

        for event in gdacs_events:
            if 'latitude' in event and 'longitude' in event:
                distance = haversine_distance(lat, lon, event['latitude'], event['longitude'])
                if distance <= radius_mi:
                    nearby.append({**event, 'source': 'gdacs'})

        # Get FEMA disasters
        fema_ref = db.reference('public_data_cache/fema_disasters/data')
        fema_disasters = fema_ref.get() or []

        for disaster in fema_disasters:
            if 'latitude' in disaster and 'longitude' in disaster:
                distance = haversine_distance(lat, lon, disaster['latitude'], disaster['longitude'])
                if distance <= radius_mi:
                    nearby.append({**disaster, 'source': 'fema'})

        # Get USGS earthquakes
        usgs_ref = db.reference('public_data_cache/usgs_earthquakes/data')
        usgs_earthquakes = usgs_ref.get() or []

        for earthquake in usgs_earthquakes:
            if 'latitude' in earthquake and 'longitude' in earthquake:
                distance = haversine_distance(lat, lon, earthquake['latitude'], earthquake['longitude'])
                if distance <= radius_mi:
                    nearby.append({**earthquake, 'source': 'usgs'})

        # Get Cal Fire incidents
        cal_fire_ref = db.reference('public_data_cache/cal_fire/data')
        cal_fire_incidents = cal_fire_ref.get() or []

        for incident in cal_fire_incidents:
            if 'latitude' in incident and 'longitude' in incident:
                distance = haversine_distance(lat, lon, incident['latitude'], incident['longitude'])
                if distance <= radius_mi:
                    nearby.append({**incident, 'source': 'cal_fire'})

        # Get Cal OES alerts
        cal_oes_ref = db.reference('public_data_cache/cal_oes_alerts/data')
        cal_oes_alerts = cal_oes_ref.get() or []

        for alert in cal_oes_alerts:
            if 'latitude' in alert and 'longitude' in alert:
                distance = haversine_distance(lat, lon, alert['latitude'], alert['longitude'])
                if distance <= radius_mi:
                    nearby.append({**alert, 'source': 'cal_oes'})

    except Exception as e:
        logger.error(f"Error fetching nearby reports: {e}")

    return nearby


def _update_nearby_reports_confidence(new_lat: float, new_lon: float, new_report_id: str, radius_mi: float = 50):
    """
    Retroactively update confidence scores for nearby user reports after a new report is added.
    This ensures earlier reports benefit from the new corroboration.

    Performance optimizations:
    - Filters by distance BEFORE fetching nearby reports (reduces unnecessary lookups)
    - Batches Firebase updates to reduce network calls
    - Limits to 20 nearest reports to prevent excessive processing

    Args:
        new_lat: Latitude of the new report
        new_lon: Longitude of the new report
        new_report_id: ID of the newly added report (to exclude from updates)
        radius_mi: Search radius in miles (default 50 miles)
    """
    try:
        # OPTIMIZATION: Only fetch user reports (filter in query would require index)
        user_reports_ref = db.reference('reports')
        all_reports = user_reports_ref.get() or {}

        # OPTIMIZATION: Pre-filter and sort by distance to limit processing
        nearby_candidates = []
        for report_id, report in all_reports.items():
            # Skip the newly added report itself
            if report_id == new_report_id:
                continue

            # Only update user reports (not official sources)
            source = report.get('source', '')
            if source not in ('user_report', 'user_report_authenticated'):
                continue

            # Check if report is within radius
            if 'latitude' in report and 'longitude' in report:
                distance = haversine_distance(new_lat, new_lon, report['latitude'], report['longitude'])

                if distance <= radius_mi:
                    nearby_candidates.append((report_id, report, distance))

        # OPTIMIZATION: Limit to 20 nearest reports to prevent excessive processing
        # Sort by distance and take the 20 closest
        nearby_candidates.sort(key=lambda x: x[2])
        reports_to_update = nearby_candidates[:20]

        if not reports_to_update:
            return  # No reports to update

        logger.info(f"Found {len(nearby_candidates)} nearby reports, updating {len(reports_to_update)} closest")

        # OPTIMIZATION: Prepare batch updates
        updates = {}
        updated_count = 0

        for report_id, report, distance in reports_to_update:
            # Fetch fresh nearby reports for this old report
            nearby_reports = _get_nearby_reports(report['latitude'], report['longitude'], radius_mi=50)

            # Recalculate confidence with updated corroboration
            updated_confidence = confidence_scorer.calculate_confidence(report, nearby_reports=nearby_reports)

            # Preserve existing AI enhancement if present (don't re-run AI)
            if report.get('confidence_breakdown', {}).get('ai_enhancement'):
                updated_confidence['breakdown']['ai_enhancement'] = report['confidence_breakdown']['ai_enhancement']
                # Re-blend scores with preserved AI
                heuristic_score = updated_confidence['confidence_score']
                ai_score = report['confidence_breakdown']['ai_enhancement']['score']
                updated_confidence['confidence_score'] = (heuristic_score * 0.7) + (ai_score * 0.3)
                # Update confidence level based on new score
                if updated_confidence['confidence_score'] >= 0.8:
                    updated_confidence['confidence_level'] = "High"
                elif updated_confidence['confidence_score'] >= 0.6:
                    updated_confidence['confidence_level'] = "Medium"
                else:
                    updated_confidence['confidence_level'] = "Low"

            # OPTIMIZATION: Collect updates in batch instead of individual writes
            updates[f'reports/{report_id}/confidence_score'] = round(updated_confidence['confidence_score'], 3)
            updates[f'reports/{report_id}/confidence_level'] = updated_confidence['confidence_level']
            updates[f'reports/{report_id}/confidence_breakdown'] = updated_confidence['breakdown']

            updated_count += 1
            logger.info(f"Queued update for {report_id}: {report.get('confidence_score', 0):.3f} → {updated_confidence['confidence_score']:.3f}")

        # OPTIMIZATION: Single batch update instead of multiple individual updates
        if updates:
            db.reference().update(updates)
            logger.info(f"Batch updated {updated_count} nearby report(s) with new corroboration")

    except Exception as e:
        logger.error(f"Error updating nearby reports: {e}")
        # Don't fail the main request if retroactive updates fail

# ===== MIDDLEWARE & DECORATORS =====

def require_admin(f):
    """
    Decorator to require admin authentication for endpoints
    Checks Firebase custom claims for admin role
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Get ID token from Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Admin authentication required'}), 401

            id_token = auth_header.split('Bearer ')[1]

            # Verify token and get decoded claims
            decoded_token = firebase_auth.verify_id_token(id_token)
            user_id = decoded_token['uid']

            # Check if user has admin custom claim
            is_admin = decoded_token.get('admin', False)

            if not is_admin:
                logger.warning(f"User {user_id} attempted to access admin endpoint without admin claim")
                return jsonify({'error': 'Admin access required'}), 403

            # Attach user_id to request for use in endpoint
            request.user_id = user_id

            return f(*args, **kwargs)

        except ValueError as e:
            return jsonify({'error': f'Authentication failed: {str(e)}'}), 401
        except Exception as e:
            logger.error(f"Error in require_admin: {e}")
            return jsonify({'error': 'Authentication failed'}), 401

    return decorated_function


# ===== AUTHENTICATION ENDPOINTS (Phase 7) =====

@app.route('/api/auth/register', methods=['POST'])
@limiter.limit("3 per hour")  # Stricter: Prevent mass account creation
@limiter.limit("10 per day")  # Daily cap to prevent distributed attacks
def register_user():
    """Register a new user with email/password"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Request body is required'}), 400

        email = data.get('email')
        password = data.get('password')
        display_name = data.get('display_name')

        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400

        # Password validation is now done in auth_service.create_user()
        # Email validation is also done in auth_service.create_user()
        user_data = auth_service.create_user(email, password, display_name)
        return jsonify(user_data), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error in register_user: {e}")
        return jsonify({'error': 'Registration failed'}), 500


@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("5 per 15 minutes")  # Stricter: 5 attempts per 15 minutes
@limiter.limit("20 per day")  # Daily cap to prevent persistent brute force
def login_user():
    """Verify Firebase ID token and return user profile"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Request body is required'}), 400

        id_token = data.get('id_token')
        if not id_token:
            return jsonify({'error': 'id_token is required'}), 400

        user_data = auth_service.verify_id_token(id_token)

        # Get full user profile
        profile = auth_service.get_user_profile(user_data['user_id'])

        return jsonify({
            'user_id': user_data['user_id'],
            'email': user_data['email'],
            'email_verified': user_data['email_verified'],
            'display_name': user_data['display_name'],
            'credibility_score': user_data['credibility_score'],
            'credibility_level': user_data['credibility_level'],
            'total_reports': profile.get('total_reports', 0) if profile else 0
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        logger.error(f"Error in login_user: {e}")
        return jsonify({'error': 'Authentication failed'}), 500


@app.route('/api/auth/logout', methods=['POST'])
def logout_user():
    """
    Revoke user's refresh tokens (force logout)

    Note: Firebase Authentication is primarily client-side.
    This endpoint optionally revokes refresh tokens server-side if id_token is provided.
    If no token is provided, returns success (client should handle logout locally).
    """
    try:
        data = request.json or {}

        id_token = data.get('id_token')

        # If no token provided, just return success (client-side logout)
        if not id_token:
            return jsonify({
                'status': 'logged_out',
                'message': 'Client-side logout successful'
            }), 200

        # If token provided, verify and revoke refresh tokens server-side
        try:
            user_data = auth_service.verify_id_token(id_token)
            user_id = user_data['user_id']

            # Revoke all refresh tokens
            auth_service.revoke_refresh_tokens(user_id)

            return jsonify({
                'status': 'logged_out',
                'user_id': user_id,
                'message': 'Server-side tokens revoked'
            }), 200

        except ValueError as e:
            # Token invalid/expired - still allow logout (client should clear local state)
            return jsonify({
                'status': 'logged_out',
                'message': 'Client-side logout successful (token was invalid)'
            }), 200

    except Exception as e:
        logger.error(f"Error in logout_user: {e}")
        # Even on error, allow logout to succeed (fail gracefully)
        return jsonify({
            'status': 'logged_out',
            'message': 'Client-side logout successful'
        }), 200


@app.route('/api/auth/profile', methods=['GET'])
def get_user_profile_endpoint():
    """Get user profile (requires Authorization header)"""
    try:
        # Get ID token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization header required'}), 401

        id_token = auth_header.split('Bearer ')[1]

        # Verify token
        user_data = auth_service.verify_id_token(id_token)
        user_id = user_data['user_id']

        # Get profile
        profile = auth_service.get_user_profile(user_id)
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404

        return jsonify(profile)

    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        logger.error(f"Error in get_user_profile_endpoint: {e}")
        return jsonify({'error': 'Failed to fetch profile'}), 500


@app.route('/api/auth/profile', methods=['PUT'])
def update_user_profile_endpoint():
    """Update user profile (display name, etc.)"""
    try:
        # Get ID token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization header required'}), 401

        id_token = auth_header.split('Bearer ')[1]

        # Verify token
        user_data = auth_service.verify_id_token(id_token)
        user_id = user_data['user_id']

        # Get updates from request body
        updates = request.json
        if not updates:
            return jsonify({'error': 'Request body is required'}), 400

        # Update profile
        updated_profile = auth_service.update_user_profile(user_id, updates)

        return jsonify(updated_profile)

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error in update_user_profile_endpoint: {e}")
        return jsonify({'error': 'Failed to update profile'}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'disasterscope-api'})

@app.route('/api/cache/status', methods=['GET'])
def cache_status():
    """Get cache status and metadata (all sources including hidden confidence-only sources)"""
    try:
        status = {}
        # Display sources (NASA FIRMS + NOAA)
        display_types = ['wildfires', 'weather_alerts']
        # Hidden confidence-only sources (FEMA, USGS, GDACS, Cal Fire, Cal OES)
        confidence_types = ['gdacs_events', 'fema_disasters', 'usgs_earthquakes', 'cal_fire', 'cal_oes_alerts']

        all_types = display_types + confidence_types
        for data_type in all_types:
            ref = db.reference(f'public_data_cache/{data_type}/metadata')
            metadata = ref.get()
            status[data_type] = metadata if metadata else {'status': 'empty'}
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cache/clear', methods=['POST'])
@require_admin  # Admin-only endpoint
def clear_cache():
    """Clear cache (admin endpoint - requires admin authentication)"""
    try:
        data_type = request.json.get('type') if request.json else None
        cache_manager.clear_cache(data_type)
        return jsonify({'status': 'cleared', 'type': data_type or 'all'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cache/refresh', methods=['POST'])
@require_admin  # Admin-only endpoint
def force_refresh():
    """Force refresh data from external APIs, bypassing cache (admin-only)"""
    try:
        data_type = request.json.get('type') if request.json else 'all'
        results = {}

        if data_type in ['wildfires', 'all']:
            logger.info("Force refreshing wildfire data from NASA FIRMS...")
            fresh_wildfires = nasa_service.get_us_wildfires(days=3)  # Use 3 days for consistent visibility
            cache_manager.update_cache('wildfires', fresh_wildfires)
            results['wildfires'] = {'count': len(fresh_wildfires), 'status': 'refreshed'}

        if data_type in ['weather_alerts', 'all']:
            logger.info("Force refreshing weather alerts from NOAA...")
            fresh_alerts = noaa_service.get_us_weather_alerts(severity_threshold='Minor')
            cache_manager.update_cache('weather_alerts', fresh_alerts)
            results['weather_alerts'] = {'count': len(fresh_alerts), 'status': 'refreshed'}

        if data_type in ['gdacs_events', 'all']:
            logger.info("Force refreshing GDACS events...")
            fresh_events = gdacs_service.fetch_recent_events(days=3)
            cache_manager.update_cache('gdacs_events', fresh_events)
            results['gdacs_events'] = {'count': len(fresh_events), 'status': 'refreshed'}

        if data_type in ['fema_disasters', 'all']:
            logger.info("Force refreshing FEMA disasters...")
            fresh_disasters = fema_service.get_recent_disasters(days=30)
            cache_manager.update_cache('fema_disasters', fresh_disasters)
            results['fema_disasters'] = {'count': len(fresh_disasters), 'status': 'refreshed'}

        if data_type in ['usgs_earthquakes', 'all']:
            logger.info("Force refreshing USGS earthquakes...")
            fresh_earthquakes = usgs_service.get_us_earthquakes(days=7)
            cache_manager.update_cache('usgs_earthquakes', fresh_earthquakes)
            results['usgs_earthquakes'] = {'count': len(fresh_earthquakes), 'status': 'refreshed'}

        if data_type in ['cal_fire', 'all']:
            logger.info("Force refreshing Cal Fire incidents...")
            fresh_incidents = cal_fire_service.fetch_active_incidents()
            cache_manager.update_cache('cal_fire', fresh_incidents)
            results['cal_fire'] = {'count': len(fresh_incidents), 'status': 'refreshed'}

        if data_type in ['cal_oes_alerts', 'all']:
            logger.info("Force refreshing Cal OES alerts...")
            fresh_alerts = cal_oes_service.fetch_recent_alerts()
            cache_manager.update_cache('cal_oes_alerts', fresh_alerts)
            results['cal_oes_alerts'] = {'count': len(fresh_alerts), 'status': 'refreshed'}

        return jsonify({'status': 'success', 'results': results})
    except Exception as e:
        logger.error(f"Error in force_refresh: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports', methods=['GET'])
def get_reports():
    """
    Get all disaster reports with time decay metadata and optional age filtering.

    Query Parameters:
        - max_age_hours (optional): Filter out reports older than this many hours
          Example: ?max_age_hours=48 (only show reports from last 48 hours)

    Returns:
        Array of reports, each with time_decay metadata:
        {
            id: str,
            latitude: float,
            longitude: float,
            type: str,
            severity: str,
            timestamp: str,
            confidence_score: float,
            time_decay: {
                age_hours: float,
                age_category: "fresh" | "recent" | "old" | "stale" | "very_stale",
                decay_score: float (0.0-1.0 for opacity)
            },
            ...
        }
    """
    try:
        # Get optional max_age_hours filter parameter
        max_age_hours = request.args.get('max_age_hours', type=float)

        # Validate max_age_hours if provided
        if max_age_hours is not None:
            if max_age_hours < 0:
                return jsonify({'error': 'max_age_hours must be non-negative'}), 400
            if max_age_hours > 8760:  # 1 year in hours
                return jsonify({'error': 'max_age_hours cannot exceed 8760 (1 year)'}), 400

        ref = db.reference('reports')
        reports_dict = ref.get()

        # Current time for consistent age calculations
        current_time = datetime.now(timezone.utc)

        # Convert Firebase object to array format
        if reports_dict and isinstance(reports_dict, dict):
            reports = []
            for key, report in reports_dict.items():
                # Preserve all fields from Firebase, just add id
                report_data = {**report, 'id': key}

                # Ensure source is set for user reports
                if 'source' not in report_data:
                    report_data['source'] = 'user_report'

                # Handle legacy disaster_type field (backwards compatibility)
                if 'disaster_type' in report_data and 'type' not in report_data:
                    report_data['type'] = report_data['disaster_type']

                # Calculate time decay metadata
                timestamp = report_data.get('timestamp')
                if timestamp:
                    time_decay = TimeDecayService.calculate_time_decay(timestamp, current_time)
                    report_data['time_decay'] = time_decay

                    # Apply age filter if specified
                    if TimeDecayService.should_filter_by_age(time_decay.get('age_hours'), max_age_hours):
                        continue  # Skip this report (too old)
                else:
                    # Missing timestamp - include with unknown age
                    report_data['time_decay'] = {
                        'age_hours': None,
                        'age_category': 'unknown',
                        'decay_score': 0.5
                    }

                reports.append(report_data)
        else:
            reports = []

        return jsonify(reports)
    except Exception as e:
        logger.error(f"Error in get_reports: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports', methods=['POST'])
@limiter.limit("20 per hour")  # Allow burst reporting during emergencies
@limiter.limit("100 per day")  # Daily cap for legitimate emergency reporting
def create_report():
    """Create a new disaster report with confidence scoring (supports anonymous and authenticated users)"""
    import time
    start_time = time.time()

    try:
        data = request.json
        logger.info(f"⏱️ Request parsing: {(time.time() - start_time)*1000:.0f}ms")

        # Validate required fields and data integrity
        if not data:
            return jsonify({'error': 'Request body is required'}), 400

        # Use centralized validation
        is_valid, error_message = DisasterValidator.validate_report_data(data)
        if not is_valid:
            return jsonify({'error': error_message}), 400

        # Security: Validate image URL to prevent SSRF attacks
        if 'image_url' in data and data['image_url']:
            from utils.url_validator import validate_image_url
            is_valid_url, url_error = validate_image_url(data['image_url'])
            if not is_valid_url:
                return jsonify({'error': f'Invalid image URL: {url_error}'}), 400

        # Phase 7: Check for authenticated user (optional id_token in request body)
        user_id = None
        user_credibility = None
        user_credibility_level = None

        if 'id_token' in data:
            try:
                # Verify Firebase ID token
                user_data = auth_service.verify_id_token(data['id_token'])
                user_id = user_data['user_id']
                user_credibility = credibility_service.get_user_credibility(user_id)
                user_credibility_level = credibility_service.get_credibility_level(user_credibility)['name']

                # Store user credibility snapshot
                data['user_id'] = user_id
                data['user_credibility_at_submission'] = user_credibility
                data['source'] = 'user_report_authenticated'

                logger.info(f"Authenticated report from user {user_id} (credibility: {user_credibility})")

            except ValueError as e:
                # Invalid token, treat as anonymous
                logger.warning(f"Invalid token, treating as anonymous: {e}")
                user_id = None

        # Set source for anonymous reports
        if 'source' not in data:
            data['source'] = 'user_report'
        logger.info(f"⏱️ Validation complete: {(time.time() - start_time)*1000:.0f}ms")

        # Fetch nearby USER REPORTS ONLY for fast initial scoring
        # Official sources (NASA, NOAA, etc.) are fetched later in background /enhance-ai
        t1 = time.time()
        nearby_reports = _get_nearby_user_reports(data['latitude'], data['longitude'], radius_mi=50)
        logger.info(f"⏱️ Nearby reports fetch: {(time.time() - t1)*1000:.0f}ms ({len(nearby_reports)} user reports)")

        # Calculate confidence score WITHOUT AI (fast heuristic + corroboration only)
        t2 = time.time()
        if user_id and user_credibility is not None:
            # Authenticated user: apply credibility penalty
            confidence_result = confidence_scorer.calculate_confidence_with_user_credibility(
                data, user_credibility, nearby_reports=nearby_reports, skip_ai=True
            )
        else:
            # Anonymous user: use reCAPTCHA-based scoring (backward compatible)
            confidence_result = confidence_scorer.calculate_confidence(data, nearby_reports=nearby_reports, skip_ai=True)
        logger.info(f"⏱️ Confidence calculation: {(time.time() - t2)*1000:.0f}ms")

        # Add confidence data to report
        data['confidence_score'] = confidence_result['confidence_score']
        data['confidence_level'] = confidence_result['confidence_level']
        data['confidence_breakdown'] = confidence_result['breakdown']

        # Mark AI analysis status based on whether AI will be triggered
        is_user_report = data.get('source') in ['user_report', 'user_report_authenticated']
        has_content = bool(data.get('description') or data.get('image_url'))
        within_rate_limit = confidence_scorer._check_rate_limit_readonly()

        should_run_ai = is_user_report and has_content and within_rate_limit

        logger.info(f"AI decision: user_report={is_user_report}, has_content={has_content}, rate_limit_ok={within_rate_limit}, will_run={should_run_ai}")

        data['ai_analysis_status'] = 'pending' if should_run_ai else 'not_applicable'

        # Add timestamp if not present
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now(timezone.utc).isoformat()

        # Save to Firebase reports IMMEDIATELY (fast path)
        t3 = time.time()
        ref = db.reference('reports')
        new_report = ref.push(data)
        logger.info(f"⏱️ Firebase save: {(time.time() - t3)*1000:.0f}ms")

        # Phase 7: Update user credibility and track report (fast operations)
        user_credibility_change = None
        if user_id:
            t4 = time.time()
            # Update user credibility based on final confidence score
            user_credibility_change = credibility_service.update_user_credibility(
                user_id, data['confidence_score'], data['latitude'], data['longitude']
            )
            logger.info(f"⏱️ Credibility update: {(time.time() - t4)*1000:.0f}ms")

            # Track report in user_reports collection
            t5 = time.time()
            user_report_ref = db.reference(f'user_reports/{user_id}/reports/{new_report.key}')
            user_report_ref.set({
                'report_id': new_report.key,
                'timestamp': data['timestamp'],
                'latitude': data['latitude'],
                'longitude': data['longitude'],
                'type': data['type'],
                'confidence_score': data['confidence_score']
            })
            logger.info(f"⏱️ User tracking save: {(time.time() - t5)*1000:.0f}ms")

        # NOTE: Geocoding and retroactive updates moved to background
        # These slow operations now happen via the /enhance-ai endpoint
        # This ensures instant report submission (< 500ms)

        response_data = {
            'id': new_report.key,
            'data': data,
            'confidence': confidence_result
        }

        # Include credibility update in response
        if user_credibility_change:
            response_data['user_update'] = user_credibility_change

        total_time = (time.time() - start_time) * 1000
        logger.info(f"⏱️ TOTAL REQUEST TIME: {total_time:.0f}ms")
        return jsonify(response_data), 201

    except Exception as e:
        logger.error(f"Error creating report: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/reports/<report_id>/enhance-ai', methods=['POST'])
@limiter.limit("100 per hour")  # Allow async AI requests
def enhance_report_with_ai(report_id):
    """
    Trigger background AI analysis for a report (async endpoint)

    This endpoint runs AI enhancement and updates the report's confidence score.
    It's called automatically after report submission if AI analysis is applicable.

    Returns:
        200: AI analysis completed successfully
        202: AI analysis already in progress
        404: Report not found
        409: AI analysis not applicable for this report
        429: Rate limit exceeded
        500: Server error
    """
    try:
        # Fetch the report
        ref = db.reference(f'reports/{report_id}')
        report = ref.get()

        if not report:
            return jsonify({'error': 'Report not found'}), 404

        # Check AI analysis status
        ai_status = report.get('ai_analysis_status', 'not_applicable')

        if ai_status == 'not_applicable':
            return jsonify({
                'status': 'not_applicable',
                'message': 'AI analysis is not applicable for this report (no description/image or not a user report)'
            }), 409

        if ai_status == 'processing':
            return jsonify({
                'status': 'processing',
                'message': 'AI analysis is already in progress'
            }), 202

        if ai_status == 'completed':
            return jsonify({
                'status': 'completed',
                'message': 'AI analysis already completed',
                'confidence_score': report.get('confidence_score'),
                'ai_reasoning': report.get('confidence_breakdown', {}).get('ai_enhancement', {}).get('reasoning')
            }), 200

        # Mark as processing
        ref.update({'ai_analysis_status': 'processing'})

        # Phase 5: Add human-readable location name (if not already present)
        if not report.get('location_name') and geocoding_service:
            location_data = geocoding_service.reverse_geocode(report['latitude'], report['longitude'])
            if location_data:
                ref.update({'location_name': location_data['display_name']})
                report['location_name'] = location_data['display_name']

        # Fetch nearby reports for context
        nearby_reports = _get_nearby_reports(report['latitude'], report['longitude'], radius_mi=50)

        # Run AI enhancement only
        ai_result = confidence_scorer._get_ai_enhancement(report, nearby_reports)

        if not ai_result:
            # AI analysis failed (rate limit or error)
            ref.update({
                'ai_analysis_status': 'failed',
                'ai_analysis_error': 'AI analysis failed - rate limit reached or API error'
            })
            return jsonify({
                'status': 'failed',
                'message': 'AI analysis failed - rate limit reached or API error'
            }), 429

        # Get current heuristic score (without AI)
        current_heuristic = report.get('confidence_score', 0.0)

        # Blend with AI score (70% heuristic, 30% AI)
        final_score = (current_heuristic * 0.7) + (ai_result['score'] * 0.3)

        # Determine new confidence level
        if final_score >= 0.8:
            level = "High"
        elif final_score >= 0.6:
            level = "Medium"
        else:
            level = "Low"

        # Update report with AI enhancement
        breakdown = report.get('confidence_breakdown', {})
        breakdown['ai_enhancement'] = {
            'score': ai_result['score'],
            'reasoning': ai_result['reasoning'],
            'provider': ai_result.get('provider', 'unknown')
        }

        ref.update({
            'confidence_score': round(final_score, 3),
            'confidence_level': level,
            'confidence_breakdown': breakdown,
            'ai_analysis_status': 'completed',
            'ai_enhanced_at': datetime.now(timezone.utc).isoformat()
        })

        logger.info(f"AI enhancement completed for report {report_id}: {current_heuristic:.3f} → {final_score:.3f}")

        # Update user credibility based on the NEW (AI-enhanced) confidence score
        user_credibility_change = None
        user_id = report.get('user_id')
        if user_id and credibility_service:
            try:
                # Calculate the DIFFERENCE in credibility change
                # (new score vs. original score that was used during submission)
                original_credibility_change = credibility_service.calculate_user_credibility_change(current_heuristic)
                new_credibility_change = credibility_service.calculate_user_credibility_change(final_score)
                delta_change = new_credibility_change - original_credibility_change

                if delta_change != 0:
                    # Apply the ADDITIONAL credibility change
                    user_ref = db.reference(f'users/{user_id}')
                    user_data = user_ref.get()

                    if user_data:
                        old_credibility = user_data.get('credibility_score', 50)
                        new_credibility = max(0, min(100, old_credibility + delta_change))

                        user_ref.update({
                            'credibility_score': new_credibility,
                            'credibility_level': credibility_service.get_credibility_level(new_credibility)['name']
                        })

                        user_credibility_change = {
                            'old_credibility': old_credibility,
                            'new_credibility': new_credibility,
                            'delta': delta_change,
                            'reason': f'AI enhancement: {current_heuristic:.2f} → {final_score:.2f}'
                        }

                        logger.info(f"Updated user {user_id} credibility after AI: {old_credibility} → {new_credibility} ({delta_change:+d})")
            except Exception as e:
                logger.error(f"Error updating user credibility after AI: {e}")
                # Don't fail the request if credibility update fails

        # Retroactively update confidence scores for nearby user reports
        # (so earlier reports benefit from this new corroboration)
        # This runs in background after AI completes
        try:
            _update_nearby_reports_confidence(report['latitude'], report['longitude'], report_id)
        except Exception as e:
            logger.error(f"Error updating nearby reports for {report_id}: {e}")
            # Don't fail the request if retroactive updates fail

        response_data = {
            'status': 'completed',
            'confidence_score': round(final_score, 3),
            'confidence_level': level,
            'ai_reasoning': ai_result['reasoning'],
            'previous_score': round(current_heuristic, 3)
        }

        # Include credibility update in response
        if user_credibility_change:
            response_data['user_update'] = user_credibility_change

        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Error enhancing report with AI: {e}")
        # Mark as failed
        try:
            ref = db.reference(f'reports/{report_id}')
            ref.update({
                'ai_analysis_status': 'failed',
                'ai_analysis_error': str(e)
            })
        except:
            pass
        return jsonify({'error': 'Failed to enhance report with AI'}), 500


@app.route('/api/reports/<report_id>', methods=['GET'])
def get_report_by_id(report_id):
    """
    Get a single disaster report by ID

    Returns:
        200: Report data
        404: Report not found
        500: Server error
    """
    try:
        ref = db.reference(f'reports/{report_id}')
        report = ref.get()

        if report is None:
            return jsonify({'error': 'Report not found'}), 404

        # Add ID to the report data
        report['id'] = report_id

        return jsonify(report), 200

    except Exception as e:
        logger.error(f"Error fetching report {report_id}: {e}")
        return jsonify({'error': 'Failed to fetch report'}), 500


@app.route('/api/reports/<report_id>', methods=['DELETE'])
def delete_report(report_id):
    """
    Delete a disaster report by ID (requires ownership or admin privileges)

    Headers:
        - Authorization: Bearer {token} (optional for legacy support, required for owned reports)

    Returns:
        200: Report deleted successfully
        401: Authentication required (report has owner, but no token provided)
        403: Forbidden (user doesn't own the report)
        404: Report not found
        500: Server error

    Backward Compatibility:
        - Reports without user_id field can be deleted by anyone (legacy reports)
        - Reports with user_id can only be deleted by the owner or admin
    """
    try:
        # Fetch the report
        ref = db.reference(f'reports/{report_id}')
        report = ref.get()

        if report is None:
            return jsonify({'error': 'Report not found'}), 404

        # Check if report has an owner
        report_owner_id = report.get('user_id')

        if report_owner_id:
            # Report has owner - authentication required
            auth_header = request.headers.get('Authorization')

            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({
                    'error': 'Authentication required',
                    'message': 'This report belongs to a user. Please log in to delete it.'
                }), 401

            id_token = auth_header.split('Bearer ')[1]

            try:
                # Verify token and get user_id
                decoded_token = firebase_auth.verify_id_token(id_token)
                requesting_user_id = decoded_token['uid']
                is_admin = decoded_token.get('admin', False)

                # Check ownership
                if requesting_user_id != report_owner_id:
                    # Check if user is admin (optional admin override)
                    if not is_admin:
                        return jsonify({
                            'error': 'Forbidden',
                            'message': 'You can only delete your own reports.'
                        }), 403
                    else:
                        logger.info(f"Admin {requesting_user_id} deleting report {report_id} owned by {report_owner_id}")

                # User owns the report or is admin - proceed with deletion
                # Cancel any pending AI analysis
                ai_status = report.get('ai_analysis_status')
                if ai_status in ['pending', 'processing']:
                    logger.info(f"Cancelling AI analysis for report {report_id} (status: {ai_status})")

                # Revert user credibility change from this report
                user_credibility_reversion = None
                if report_owner_id and credibility_service:
                    try:
                        # Calculate the original credibility change based on the report's confidence score
                        report_confidence = report.get('confidence_score', 0.0)
                        original_change = credibility_service.calculate_user_credibility_change(report_confidence)

                        # Revert the change (apply negative of original change)
                        user_ref = db.reference(f'users/{report_owner_id}')
                        user_data = user_ref.get()

                        if user_data:
                            old_credibility = user_data.get('credibility_score', 50)
                            new_credibility = max(0, min(100, old_credibility - original_change))

                            user_ref.update({
                                'credibility_score': new_credibility,
                                'credibility_level': credibility_service.get_credibility_level(new_credibility)['name']
                            })

                            user_credibility_reversion = {
                                'old_credibility': old_credibility,
                                'new_credibility': new_credibility,
                                'delta': -original_change,
                                'reason': f'Report deleted (reverted {original_change:+d} from confidence {report_confidence:.2f})'
                            }

                            logger.info(f"Reverted credibility for user {report_owner_id}: {old_credibility} → {new_credibility} ({-original_change:+d})")
                    except Exception as e:
                        logger.error(f"Error reverting user credibility on delete: {e}")
                        # Don't fail the deletion if credibility reversion fails

                ref.delete()

                # Also delete from user_reports tracking
                if report_owner_id:
                    user_report_ref = db.reference(f'user_reports/{report_owner_id}/reports/{report_id}')
                    user_report_ref.delete()

                logger.info(f"Report {report_id} deleted by user {requesting_user_id}")

                response_data = {
                    'status': 'deleted',
                    'id': report_id,
                    'deleted_by': requesting_user_id
                }

                # Include credibility reversion in response
                if user_credibility_reversion:
                    response_data['user_update'] = user_credibility_reversion

                return jsonify(response_data), 200

            except ValueError as e:
                return jsonify({
                    'error': 'Authentication failed',
                    'message': str(e)
                }), 401

        else:
            # Legacy report without owner - allow deletion (backward compatibility)
            logger.warning(f"Deleting legacy report {report_id} without owner (backward compatibility)")
            # Cancel any pending AI analysis
            ai_status = report.get('ai_analysis_status')
            if ai_status in ['pending', 'processing']:
                logger.info(f"Cancelling AI analysis for report {report_id} (status: {ai_status})")
            ref.delete()
            return jsonify({
                'status': 'deleted',
                'id': report_id,
                'note': 'Legacy report deleted (no owner)'
            }), 200

    except Exception as e:
        logger.error(f"Error deleting report: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/reports/<report_id>', methods=['PUT'])
def update_report(report_id):
    """
    Update a disaster report by ID (requires ownership or admin privileges)

    Headers:
        - Authorization: Bearer {token} (required)

    Returns:
        200: Report updated successfully
        401: Authentication required
        403: Forbidden (user doesn't own the report and is not admin)
        404: Report not found
        500: Server error
    """
    try:
        # Require authentication for updates
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'error': 'Authentication required',
                'message': 'Please log in to update reports.'
            }), 401

        id_token = auth_header.split('Bearer ')[1]

        try:
            # Verify token
            decoded_token = firebase_auth.verify_id_token(id_token)
            requesting_user_id = decoded_token['uid']
            is_admin = decoded_token.get('admin', False)

            # Fetch the report
            ref = db.reference(f'reports/{report_id}')
            report = ref.get()

            if report is None:
                return jsonify({'error': 'Report not found'}), 404

            # Check ownership or admin
            report_owner_id = report.get('user_id')
            if report_owner_id and requesting_user_id != report_owner_id and not is_admin:
                return jsonify({
                    'error': 'Forbidden',
                    'message': 'You can only edit your own reports.'
                }), 403

            # Get update data
            update_data = request.json
            if not update_data:
                return jsonify({'error': 'Update data is required'}), 400

            # Validate updateable fields
            allowed_fields = ['type', 'severity', 'description', 'affected_population', 'image_url']
            updates = {}
            for field in allowed_fields:
                if field in update_data:
                    updates[field] = update_data[field]

            # Handle AI reasoning update (admin only, updates confidence_breakdown)
            if 'ai_reasoning' in update_data and is_admin:
                # Update the AI reasoning in confidence_breakdown
                if 'confidence_breakdown' not in report:
                    report['confidence_breakdown'] = {}
                if 'ai_enhancement' not in report['confidence_breakdown']:
                    report['confidence_breakdown']['ai_enhancement'] = {}

                report['confidence_breakdown']['ai_enhancement']['reasoning'] = update_data['ai_reasoning']
                report['confidence_breakdown']['ai_enhancement']['manually_edited'] = True
                report['confidence_breakdown']['ai_enhancement']['edited_by'] = requesting_user_id
                report['confidence_breakdown']['ai_enhancement']['edited_at'] = datetime.now(timezone.utc).isoformat()

                updates['confidence_breakdown'] = report['confidence_breakdown']
                logger.info(f"Admin {requesting_user_id} updated AI reasoning for report {report_id}")

            if not updates:
                return jsonify({'error': 'No valid fields to update'}), 400

            # Validate updated data
            test_data = {**report, **updates}
            is_valid, error_message = DisasterValidator.validate_report_data(test_data)
            if not is_valid:
                return jsonify({'error': error_message}), 400

            # Add metadata about the update
            updates['updated_at'] = datetime.now(timezone.utc).isoformat()
            if is_admin and requesting_user_id != report_owner_id:
                updates['updated_by_admin'] = requesting_user_id
                logger.info(f"Admin {requesting_user_id} updating report {report_id} owned by {report_owner_id}")

            # Update the report
            ref.update(updates)

            # Fetch updated report
            updated_report = ref.get()
            updated_report['id'] = report_id

            return jsonify({
                'status': 'updated',
                'data': updated_report
            }), 200

        except ValueError as e:
            return jsonify({
                'error': 'Authentication failed',
                'message': str(e)
            }), 401

    except Exception as e:
        logger.error(f"Error updating report: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/reports/bulk/delete-stale', methods=['POST'])
@require_admin
@limiter.limit("5 per hour")  # Prevent abuse of bulk delete
def delete_stale_reports():
    """
    Bulk delete stale user reports older than specified hours

    **Requires admin authentication via Bearer token in Authorization header**
    Rate limited to 5 requests per hour per IP address

    Request body:
        {
            "max_age_hours": 48  // Delete reports older than this (default: 48)
        }

    Returns:
        {
            "deleted_count": int,
            "deleted_ids": [report_ids],
            "max_age_hours": int
        }
    """
    try:
        data = request.get_json() or {}
        max_age_hours = data.get('max_age_hours', 48)

        # Validate max_age_hours
        if not isinstance(max_age_hours, (int, float)) or max_age_hours <= 0:
            return jsonify({'error': 'max_age_hours must be a positive number'}), 400

        # Get all user reports
        reports_ref = db.reference('reports')
        all_reports = reports_ref.get() or {}

        # Calculate cutoff time
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

        deleted_ids = []
        failed_deletes = []
        deleted_count = 0

        # Audit log: Record bulk delete operation start
        user_id = getattr(request, 'user_id', 'unknown')
        operation_id = f"bulk_delete_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{user_id[:8]}"

        # Create audit log entry in Firebase
        audit_entry_start = {
            'operation_id': operation_id,
            'operation': 'bulk_delete_stale_reports',
            'user_id': user_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'parameters': {
                'max_age_hours': max_age_hours
            },
            'status': 'started'
        }

        try:
            db.reference(f'audit_logs/{operation_id}').set(audit_entry_start)
        except Exception as audit_error:
            logger.error(f"Failed to write audit log: {audit_error}")

        logger.info(f"Bulk delete operation started by user {user_id} - max_age_hours: {max_age_hours}")

        for report_id, report in all_reports.items():
            # Only delete user reports (not official sources)
            if report.get('source') not in ['user_report', 'user_report_authenticated']:
                continue

            # Parse timestamp
            timestamp_str = report.get('timestamp')
            if not timestamp_str:
                continue

            try:
                # Parse ISO format timestamp
                report_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

                # Delete if older than cutoff
                if report_time < cutoff_time:
                    try:
                        # Attempt Firebase deletion with error handling
                        db.reference(f'reports/{report_id}').delete()
                        deleted_ids.append(report_id)
                        deleted_count += 1
                    except Exception as delete_error:
                        # Log individual deletion failure but continue
                        error_msg = f"Failed to delete report {report_id}: {str(delete_error)}"
                        logger.error(error_msg)
                        failed_deletes.append({
                            'id': report_id,
                            'error': str(delete_error)
                        })
            except (ValueError, AttributeError) as e:
                logger.warning(f"Could not parse timestamp for report {report_id}: {e}")
                continue

        # Audit log: Record bulk delete operation completion
        audit_entry_complete = {
            'operation_id': operation_id,
            'operation': 'bulk_delete_stale_reports',
            'user_id': user_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'parameters': {
                'max_age_hours': max_age_hours
            },
            'status': 'completed' if not failed_deletes else 'partial_success',
            'result': {
                'deleted_count': deleted_count,
                'deleted_ids': deleted_ids,
                'failed_count': len(failed_deletes),
                'failed_ids': [f['id'] for f in failed_deletes] if failed_deletes else []
            }
        }

        try:
            db.reference(f'audit_logs/{operation_id}').update(audit_entry_complete)
        except Exception as audit_error:
            logger.error(f"Failed to update audit log: {audit_error}")

        logger.info(f"Bulk delete completed by user {user_id} - deleted: {deleted_count}, failed: {len(failed_deletes)}")

        # Build response with error information if any deletions failed
        response = {
            'deleted_count': deleted_count,
            'deleted_ids': deleted_ids,
            'max_age_hours': max_age_hours
        }

        # Add failure information if any deletions failed
        if failed_deletes:
            response['failed_count'] = len(failed_deletes)
            response['failed_deletes'] = failed_deletes
            response['warning'] = f"{len(failed_deletes)} deletion(s) failed - check logs for details"
            # Return 207 Multi-Status if some succeeded and some failed
            status_code = 207 if deleted_count > 0 else 500
            logger.warning(f"Partial success: {deleted_count} deleted, {len(failed_deletes)} failed")
            return jsonify(response), status_code

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error deleting stale reports: {e}")
        return jsonify({'error': str(e)}), 500


# ===== PROXIMITY ALERT ENDPOINTS (Phase 8) =====

@app.route('/api/alerts/proximity', methods=['GET'])
@limiter.limit("600 per hour")  # 10 per minute - supports adaptive polling (15min/30min/60min intervals)
def get_proximity_alerts():
    """
    Get proximity alerts for user location

    Query params:
        - lat (required): User latitude
        - lon (required): User longitude
        - radius (optional): Search radius in km (default from user preferences or 50km)

    Headers:
        - Authorization: Bearer {token} (optional - if provided, uses user preferences)

    Returns:
        {
            alerts: List of nearby disasters,
            highest_severity: str,
            count: int,
            closest_distance: float
        }
    """
    try:
        # Validate required parameters
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)
        radius = request.args.get('radius', type=float)

        if lat is None or lon is None:
            return jsonify({"error": "lat and lon query parameters are required"}), 400

        # Validate coordinate ranges
        if not CoordinateValidator.validate_coordinates(lat, lon):
            return jsonify({'error': 'Invalid coordinates: Latitude must be between -90 and 90, Longitude must be between -180 and 180'}), 400

        # Check if proximity alert service is initialized
        if not proximity_alert_service:
            return jsonify({'error': 'Proximity alert service not available. Check Firebase configuration.'}), 503

        # Get user_id if authenticated
        user_id = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            id_token = auth_header.replace('Bearer ', '')
            try:
                user_data = auth_service.verify_id_token(id_token)
                user_id = user_data.get('user_id')
            except ValueError as e:
                # Invalid token - proceed as anonymous user
                logger.warning(f"Invalid token in proximity alerts: {e}")
                pass

        # Get preferences if authenticated
        preferences = None
        if user_id:
            preferences = proximity_alert_service.get_user_alert_preferences(user_id)
            # Use user's preferred radius if not explicitly provided
            if radius is None:
                radius = preferences.get('radius_mi', 50)
        else:
            # Anonymous user - use provided radius or default
            radius = radius or 50

        # Validate radius (5-62 miles)
        if not (5 <= radius <= 50):
            return jsonify({'error': 'Radius must be between 5 and 50 miles'}), 400

        # Get proximity alerts
        result = proximity_alert_service.check_proximity_alerts(lat, lon, user_id, radius)

        # Save new alerts as notifications if user is authenticated
        if user_id and preferences and result.get('alerts'):
            severity_filter = set(preferences.get('severity_filter', ['critical', 'high', 'medium', 'low']))
            disaster_types_filter = set(preferences.get('disaster_types', []))

            # Get existing notifications to avoid duplicates
            existing_notifications = proximity_alert_service.get_notification_history(user_id, limit=100)
            existing_disaster_ids = {n.get('disaster_id') for n in existing_notifications}

            # Save only new, high-priority alerts
            for alert in result['alerts']:
                # Skip if already notified
                if alert.get('id') in existing_disaster_ids:
                    continue

                # Only save critical and high severity alerts
                if alert.get('alert_severity') in ['critical', 'high']:
                    proximity_alert_service.save_alert_notification(user_id, alert)

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error getting proximity alerts: {str(e)}")
        return jsonify({"error": "Failed to get proximity alerts"}), 500


@app.route('/api/alerts/preferences', methods=['GET'])
@limiter.limit("100 per hour")
def get_alert_preferences():
    """
    Get user alert preferences

    Headers:
        - Authorization: Bearer {token} (required)

    Returns:
        User preferences object with radius, severity filters, disaster types, etc.
    """
    try:
        # Get ID token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization header required'}), 401

        id_token = auth_header.replace('Bearer ', '')

        # Verify token
        user_data = auth_service.verify_id_token(id_token)
        user_id = user_data.get('user_id')

        # Check if proximity alert service is initialized
        if not proximity_alert_service:
            return jsonify({'error': 'Proximity alert service not available. Check Firebase configuration.'}), 503

        # Get user preferences
        preferences = proximity_alert_service.get_user_alert_preferences(user_id)

        return jsonify(preferences), 200

    except ValueError as e:
        return jsonify({'error': f'Authentication failed: {str(e)}'}), 401
    except Exception as e:
        logger.error(f"Error getting alert preferences: {str(e)}")
        return jsonify({'error': 'Failed to get alert preferences'}), 500


@app.route('/api/alerts/preferences', methods=['PUT'])
@limiter.limit("20 per hour")
def update_alert_preferences():
    """
    Update user alert preferences

    Headers:
        - Authorization: Bearer {token} (required)

    Body:
        {
            radius_mi: number (5-50),
            severity_filter: array of strings (critical, high, medium, low),
            disaster_types: array of strings (earthquake, flood, wildfire, etc.),
            notification_channels: array of strings (in_app, email, push),
            quiet_hours: {enabled: bool, start: "HH:MM", end: "HH:MM"}
        }

    Returns:
        Updated preferences object
    """
    try:
        # Get ID token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization header required'}), 401

        id_token = auth_header.replace('Bearer ', '')

        # Verify token
        user_data = auth_service.verify_id_token(id_token)
        user_id = user_data.get('user_id')

        # Check if proximity alert service is initialized
        if not proximity_alert_service:
            return jsonify({'error': 'Proximity alert service not available. Check Firebase configuration.'}), 503

        # Get updates from request body
        updates = request.json
        if not updates:
            return jsonify({'error': 'Request body is required'}), 400

        # Validate radius if provided
        if 'radius_mi' in updates:
            radius = updates['radius_mi']
            if not isinstance(radius, (int, float)) or not (5 <= radius <= 50):
                return jsonify({'error': 'radius_mi must be a number between 5 and 50'}), 400
        # Backwards compatibility: also accept radius_km (will be deprecated)
        elif 'radius_km' in updates:
            radius = updates['radius_km']
            if not isinstance(radius, (int, float)) or not (5 <= radius <= 50):
                return jsonify({'error': 'radius must be a number between 5 and 50'}), 400
            # Convert old field name to new one
            updates['radius_mi'] = updates.pop('radius_km')

        # Validate severity_filter if provided
        if 'severity_filter' in updates:
            valid_severities = {'critical', 'high', 'medium', 'low'}
            severity_filter = updates['severity_filter']
            if not isinstance(severity_filter, list):
                return jsonify({'error': 'severity_filter must be an array'}), 400
            if not set(severity_filter).issubset(valid_severities):
                return jsonify({
                    'error': f'Invalid severity levels. Must be one of: {", ".join(valid_severities)}'
                }), 400

        # Validate disaster_types if provided
        if 'disaster_types' in updates:
            valid_types = {'earthquake', 'flood', 'wildfire', 'hurricane', 'tornado', 'volcano', 'drought'}
            disaster_types = updates['disaster_types']
            if not isinstance(disaster_types, list):
                return jsonify({'error': 'disaster_types must be an array'}), 400
            if not set(disaster_types).issubset(valid_types):
                return jsonify({
                    'error': f'Invalid disaster types. Must be one of: {", ".join(valid_types)}'
                }), 400

        # Update preferences
        success = proximity_alert_service.update_alert_preferences(user_id, updates)

        if not success:
            return jsonify({'error': 'Failed to update preferences'}), 500

        # Return updated preferences
        updated_preferences = proximity_alert_service.get_user_alert_preferences(user_id)

        return jsonify(updated_preferences), 200

    except ValueError as e:
        return jsonify({'error': f'Authentication failed: {str(e)}'}), 401
    except Exception as e:
        logger.error(f"Error updating alert preferences: {str(e)}")
        return jsonify({'error': 'Failed to update alert preferences'}), 500


@app.route('/api/alerts/<alert_id>/acknowledge', methods=['POST'])
@limiter.limit("100 per hour")
def acknowledge_alert(alert_id):
    """
    Mark an alert as acknowledged by the user

    Headers:
        - Authorization: Bearer {token} (required)

    Returns:
        {success: true}
    """
    try:
        # Get ID token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization header required'}), 401

        id_token = auth_header.replace('Bearer ', '')

        # Verify token
        user_data = auth_service.verify_id_token(id_token)
        user_id = user_data.get('user_id')

        # Check if proximity alert service is initialized
        if not proximity_alert_service:
            return jsonify({'error': 'Proximity alert service not available. Check Firebase configuration.'}), 503

        # Acknowledge the alert
        success = proximity_alert_service.acknowledge_alert(user_id, alert_id)

        if not success:
            return jsonify({'error': 'Alert not found or already acknowledged'}), 404

        return jsonify({'success': True}), 200

    except ValueError as e:
        return jsonify({'error': f'Authentication failed: {str(e)}'}), 401
    except Exception as e:
        logger.error(f"Error acknowledging alert: {str(e)}")
        return jsonify({'error': 'Failed to acknowledge alert'}), 500


@app.route('/api/alerts/history', methods=['GET'])
@limiter.limit("100 per hour")
def get_notification_history():
    """
    Get user's notification history

    Headers:
        - Authorization: Bearer {token} (required)

    Query params:
        - limit (optional): Maximum number of notifications to return (default: 50)

    Returns:
        {
            notifications: List of notification objects,
            count: int
        }
    """
    try:
        # Get ID token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization header required'}), 401

        id_token = auth_header.replace('Bearer ', '')

        # Verify token
        user_data = auth_service.verify_id_token(id_token)
        user_id = user_data.get('user_id')

        # Check if proximity alert service is initialized
        if not proximity_alert_service:
            return jsonify({'error': 'Proximity alert service not available. Check Firebase configuration.'}), 503

        # Get limit parameter (default 50, max 200)
        limit = request.args.get('limit', default=50, type=int)
        limit = min(max(limit, 1), 200)  # Clamp between 1 and 200

        # Fetch notification history
        notifications = proximity_alert_service.get_notification_history(user_id, limit=limit)

        return jsonify({
            'notifications': notifications,
            'count': len(notifications)
        }), 200

    except ValueError as e:
        return jsonify({'error': f'Authentication failed: {str(e)}'}), 401
    except Exception as e:
        logger.error(f"Error getting notification history: {str(e)}")
        return jsonify({'error': 'Failed to get notification history'}), 500


# ===== MAP SETTINGS ENDPOINTS =====

@app.route('/api/settings/map', methods=['GET'])
@limiter.limit("100 per hour")
def get_map_settings():
    """
    Get user map settings

    Headers:
        - Authorization: Bearer {token} (required)

    Returns:
        Map settings object with zoom_radius_mi, display_radius_mi, auto_zoom, show_all_disasters
    """
    try:
        # Get ID token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization header required'}), 401

        id_token = auth_header.replace('Bearer ', '')

        # Verify token
        user_data = auth_service.verify_id_token(id_token)
        user_id = user_data.get('user_id')

        # Check if proximity alert service is initialized
        if not proximity_alert_service:
            return jsonify({'error': 'Map settings service not available. Check Firebase configuration.'}), 503

        # Get user map settings
        settings = proximity_alert_service.get_map_settings(user_id)

        return jsonify(settings), 200

    except ValueError as e:
        return jsonify({'error': f'Authentication failed: {str(e)}'}), 401
    except Exception as e:
        logger.error(f"Error getting map settings: {str(e)}")
        return jsonify({'error': 'Failed to get map settings'}), 500


@app.route('/api/settings/map', methods=['PUT'])
@limiter.limit("20 per hour")
def update_map_settings():
    """
    Update user map settings

    Headers:
        - Authorization: Bearer {token} (required)

    Body:
        {
            zoom_radius_mi: number (1-100),
            display_radius_mi: number (1-100),
            auto_zoom: boolean,
            show_all_disasters: boolean
        }

    Returns:
        Updated map settings object
    """
    try:
        # Get ID token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization header required'}), 401

        id_token = auth_header.replace('Bearer ', '')

        # Verify token
        user_data = auth_service.verify_id_token(id_token)
        user_id = user_data.get('user_id')

        # Check if proximity alert service is initialized
        if not proximity_alert_service:
            return jsonify({'error': 'Map settings service not available. Check Firebase configuration.'}), 503

        # Get updates from request body
        updates = request.json
        if not updates:
            return jsonify({'error': 'Request body is required'}), 400

        # Validate display_radius_mi if provided
        if 'display_radius_mi' in updates:
            display_radius = updates['display_radius_mi']
            if not isinstance(display_radius, (int, float)) or not (1 <= display_radius <= 100):
                return jsonify({'error': 'display_radius_mi must be a number between 1 and 100'}), 400

        # Validate zoom_radius_mi if provided
        if 'zoom_radius_mi' in updates:
            zoom_radius = updates['zoom_radius_mi']
            if not isinstance(zoom_radius, (int, float)) or not (1 <= zoom_radius <= 100):
                return jsonify({'error': 'zoom_radius_mi must be a number between 1 and 100'}), 400

        # Validate boolean fields if provided
        if 'auto_zoom' in updates and not isinstance(updates['auto_zoom'], bool):
            return jsonify({'error': 'auto_zoom must be a boolean'}), 400

        if 'show_all_disasters' in updates and not isinstance(updates['show_all_disasters'], bool):
            return jsonify({'error': 'show_all_disasters must be a boolean'}), 400

        # Update map settings
        success = proximity_alert_service.update_map_settings(user_id, updates)

        if not success:
            return jsonify({'error': 'Failed to update map settings'}), 500

        # Return updated settings
        updated_settings = proximity_alert_service.get_map_settings(user_id)

        return jsonify(updated_settings), 200

    except ValueError as e:
        return jsonify({'error': f'Authentication failed: {str(e)}'}), 401
    except Exception as e:
        logger.error(f"Error updating map settings: {str(e)}")
        return jsonify({'error': 'Failed to update map settings'}), 500


@app.route('/api/public-data/wildfires', methods=['GET'])
def get_wildfires():
    """Get wildfire data from NASA FIRMS with smart caching"""
    try:
        # Check if we should update the cache
        if cache_manager.should_update('wildfires'):
            logger.info("Cache expired, fetching fresh wildfire data from NASA FIRMS...")
            days = request.args.get('days', default=3, type=int)
            days = min(max(days, 1), 10)  # Allow 1-10 days (NASA FIRMS API limit)

            # Fetch fresh data
            fresh_data = nasa_service.get_us_wildfires(days=days)

            # Update cache
            cache_manager.update_cache('wildfires', fresh_data)

            wildfires = fresh_data
        else:
            logger.info("Using cached wildfire data")
            wildfires = cache_manager.get_cached_data('wildfires')

        response = jsonify(wildfires)
        # Cache in browser for 5 minutes to reduce Firebase download bandwidth
        response.headers['Cache-Control'] = 'public, max-age=300'
        return response
    except Exception as e:
        logger.error(f"Error in get_wildfires: {e}")
        # Return cached data on error
        return jsonify(cache_manager.get_cached_data('wildfires'))

@app.route('/api/public-data/weather-alerts', methods=['GET'])
def get_weather_alerts():
    """Get weather alerts from NOAA with smart caching"""
    try:
        severity = request.args.get('severity', default='Minor', type=str)
        valid_severities = ['Extreme', 'Severe', 'Moderate', 'Minor', 'Unknown']

        if severity not in valid_severities:
            severity = 'Minor'

        # Check if we should update the cache
        if cache_manager.should_update('weather_alerts'):
            logger.info("Cache expired, fetching fresh weather alerts from NOAA...")

            # Fetch fresh data
            fresh_data = noaa_service.get_us_weather_alerts(severity_threshold=severity)

            # Update cache
            cache_manager.update_cache('weather_alerts', fresh_data)

            alerts = fresh_data
        else:
            logger.info("Using cached weather alerts")
            cached_data = cache_manager.get_cached_data('weather_alerts')

            # Filter cached data by severity if needed
            # Note: severity is stored in lowercase in the database
            severity_order = {'extreme': 4, 'severe': 3, 'moderate': 2, 'minor': 1, 'medium': 1, 'unknown': 0}
            min_severity = severity_order.get(severity.lower(), 0)
            alerts = [
                alert for alert in cached_data
                if severity_order.get(alert.get('severity', 'unknown'), 0) >= min_severity
            ]

        response = jsonify(alerts)
        # Cache in browser for 5 minutes to reduce Firebase download bandwidth
        response.headers['Cache-Control'] = 'public, max-age=300'
        return response
    except Exception as e:
        logger.error(f"Error in get_weather_alerts: {e}")
        # Return cached data on error
        return jsonify(cache_manager.get_cached_data('weather_alerts'))

@app.route('/api/public-data/all', methods=['GET'])
def get_all_public_data():
    """Get all public data sources with smart caching (NASA FIRMS + NOAA only for display)"""
    try:
        days = request.args.get('days', default=3, type=int)
        severity = request.args.get('severity', default='Minor', type=str)
        days = min(max(days, 1), 10)  # Allow 1-10 days (NASA FIRMS API limit)

        valid_severities = ['Extreme', 'Severe', 'Moderate', 'Minor', 'Unknown']
        if severity not in valid_severities:
            severity = 'Minor'

        # Get wildfires (uses cache)
        if cache_manager.should_update('wildfires'):
            logger.info("Fetching fresh wildfire data...")
            wildfires = nasa_service.get_us_wildfires(days=days)
            cache_manager.update_cache('wildfires', wildfires)
        else:
            wildfires = cache_manager.get_cached_data('wildfires')

        # Get weather alerts (uses cache)
        if cache_manager.should_update('weather_alerts'):
            logger.info("Fetching fresh weather alerts...")
            alerts = noaa_service.get_us_weather_alerts(severity_threshold=severity)
            cache_manager.update_cache('weather_alerts', alerts)
        else:
            cached_alerts = cache_manager.get_cached_data('weather_alerts')
            # Filter by severity (severity is stored in lowercase)
            severity_order = {'extreme': 4, 'severe': 3, 'moderate': 2, 'minor': 1, 'medium': 1, 'unknown': 0}
            min_severity = severity_order.get(severity.lower(), 0)
            alerts = [
                alert for alert in cached_alerts
                if severity_order.get(alert.get('severity', 'unknown'), 0) >= min_severity
            ]

        # Calculate total count
        total_count = len(wildfires) + len(alerts)

        response = jsonify({
            'wildfires': wildfires,
            'weather_alerts': alerts,
            'total_count': total_count
        })
        # Cache in browser for 5 minutes to reduce Firebase download bandwidth
        response.headers['Cache-Control'] = 'public, max-age=300'
        return response
    except Exception as e:
        logger.error(f"Error in get_all_public_data: {e}")
        # Return cached data on error
        return jsonify({
            'wildfires': cache_manager.get_cached_data('wildfires'),
            'weather_alerts': cache_manager.get_cached_data('weather_alerts'),
            'total_count': 0
        })

# ================================================================================
# PHASE 10: SAFE ROUTE NAVIGATION - SAFE ZONE ENDPOINTS
# ================================================================================

@app.route('/api/safe-zones', methods=['GET'])
@limiter.limit("200 per hour")  # Frequently accessed during evacuations
def get_safe_zones():
    """
    Get nearest safe zones to user location.

    Query Parameters:
        lat (float): User latitude (required)
        lon (float): User longitude (required)
        limit (int): Maximum number of zones to return (default 5)
        max_distance_mi (float): Maximum search distance in miles (default 100)
        type (str): Filter by zone type (optional)

    Returns:
        200: List of safe zones sorted by distance
        400: Invalid parameters
        500: Server error
    """
    try:
        # Validate required parameters
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)

        if lat is None or lon is None:
            return jsonify({'error': 'Missing required parameters: lat, lon'}), 400

        # Optional parameters
        limit = request.args.get('limit', default=5, type=int)
        max_distance_mi = request.args.get('max_distance_mi', default=100.0, type=float)
        zone_type = request.args.get('type', type=str)

        # Validate limit (prevent excessive Firebase reads)
        if limit < 1 or limit > 50:
            return jsonify({'error': 'Limit must be between 1 and 50'}), 400

        # Validate max_distance_mi (prevent performance issues)
        if max_distance_mi < 0.1 or max_distance_mi > 500:
            return jsonify({'error': 'Max distance must be between 0.1 and 500 miles'}), 400

        # Filter by type if provided
        zone_types = [zone_type] if zone_type else None

        # Get nearest safe zones
        safe_zones = safe_zone_service.get_nearest_safe_zones(
            lat, lon,
            limit=limit,
            max_distance_mi=max_distance_mi,
            zone_types=zone_types
        )

        return jsonify(safe_zones), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error in get_safe_zones: {e}")
        return jsonify({'error': 'Failed to fetch safe zones'}), 500


@app.route('/api/safe-zones/<zone_id>', methods=['GET'])
@limiter.limit("200 per hour")  # Details endpoint, higher limit
def get_safe_zone_details(zone_id):
    """
    Get detailed information about a specific safe zone.

    Path Parameters:
        zone_id (str): Safe zone identifier

    Returns:
        200: Safe zone details
        404: Zone not found
        500: Server error
    """
    try:
        zone = safe_zone_service.get_zone_by_id(zone_id)

        if not zone:
            return jsonify({'error': 'Safe zone not found'}), 404

        return jsonify(zone), 200

    except Exception as e:
        logger.error(f"Error in get_safe_zone_details: {e}")
        return jsonify({'error': 'Failed to fetch safe zone details'}), 500


@app.route('/api/safe-zones/<zone_id>/status', methods=['GET'])
@limiter.limit("200 per hour")  # Critical safety check - needs higher limit during evacuations
def check_zone_safety(zone_id):
    """
    Check if a safe zone is currently safe (no nearby disasters).

    Path Parameters:
        zone_id (str): Safe zone identifier

    Query Parameters:
        threat_radius_mi (float): Radius to check for threats in miles (default 5, max 50)

    Returns:
        200: Safety status including nearby threats
        400: Invalid parameters
        404: Zone not found
        500: Server error
    """
    try:
        # Get threat radius parameter with validation
        threat_radius_mi = request.args.get('threat_radius_mi', default=5.0, type=float)

        # Validate threat_radius_mi to prevent performance issues
        if threat_radius_mi < 0.1 or threat_radius_mi > 50:
            return jsonify({'error': 'Threat radius must be between 0.1 and 50 miles'}), 400

        # Get zone details to know its location
        zone = safe_zone_service.get_zone_by_id(zone_id)
        if not zone:
            return jsonify({'error': 'Safe zone not found'}), 404

        zone_lat = zone['location']['latitude']
        zone_lon = zone['location']['longitude']

        # Use existing helper to get all disasters near the zone
        # This includes all 7 data sources with proper structure
        current_disasters = _get_nearby_reports(zone_lat, zone_lon, radius_mi=threat_radius_mi)

        # Filter disasters by time (last 48 hours) to avoid stale threats
        current_time = datetime.now(timezone.utc)
        filtered_disasters = []

        for disaster in current_disasters:
            # Check if disaster has timestamp
            if 'timestamp' in disaster:
                try:
                    age_hours = TimeDecayService.calculate_age_hours(disaster['timestamp'], current_time)
                    # Filter out disasters older than 48 hours (STALE_THRESHOLD)
                    if age_hours < TimeDecayService.STALE_THRESHOLD:
                        filtered_disasters.append(disaster)
                except ValueError:
                    # Include if timestamp invalid (better safe than sorry)
                    filtered_disasters.append(disaster)
            else:
                # Include disasters without timestamp (official sources often lack timestamps)
                filtered_disasters.append(disaster)

        # Check zone safety with time-filtered disasters
        safety_status = safe_zone_service.is_zone_safe(
            zone_id,
            filtered_disasters,
            threat_radius_mi=threat_radius_mi
        )

        if 'error' in safety_status:
            return jsonify({'error': safety_status['error']}), 500

        return jsonify(safety_status), 200

    except Exception as e:
        logger.error(f"Error in check_zone_safety: {e}")
        return jsonify({'error': 'Failed to check zone safety'}), 500


@app.route('/api/safe-zones/seed', methods=['POST'])
@require_admin
@limiter.limit("5 per hour")  # Admin-only, very restrictive
def seed_safe_zones():
    """
    Seed database with default safe zones (admin only).

    Returns:
        200: Number of zones created
        401: Unauthorized
        500: Server error
    """
    try:
        count = safe_zone_service.seed_default_safe_zones()
        return jsonify({
            'message': f'Successfully seeded {count} safe zones',
            'count': count
        }), 200

    except Exception as e:
        logger.error(f"Error seeding safe zones: {e}")
        return jsonify({'error': 'Failed to seed safe zones'}), 500


# ================================================================================
# PHASE 10: SAFE ROUTE NAVIGATION - ROUTE CALCULATION ENDPOINTS
# ================================================================================

@app.route('/api/routes/calculate', methods=['POST'])
@limiter.limit("40 per hour")  # Route calculation is critical for navigation safety
@limiter.limit("10 per minute")  # Allow recalculation when disasters change
def calculate_routes():
    """
    Calculate disaster-aware routes from origin to destination.

    Request Body:
        origin (dict): {"lat": float, "lon": float}
        destination (dict): {"lat": float, "lon": float}
        safe_zone_id (str, optional): Target safe zone ID (instead of destination)
        avoid_disasters (bool, optional): Whether to avoid disaster zones (default: True)
        alternatives (int, optional): Number of alternative routes (1-3, default: 3)

    Returns:
        200: Route calculation results
            {
                routes: List of route objects,
                avoided_disasters: List of disasters that influenced routing,
                fastest_route_index: int,
                safest_route_index: int,
                calculation_metadata: {
                    origin: {lat, lon},
                    destination: {lat, lon},
                    timestamp: ISO string,
                    disasters_considered: int
                }
            }
        400: Invalid parameters
        503: Route service not available
        500: Server error
    """
    try:
        # Check if route service is initialized
        if not route_service:
            return jsonify({
                'error': 'Route calculation service not available. Check ORS_API_KEY configuration.'
            }), 503

        # Parse request body
        data = request.json
        if not data:
            return jsonify({'error': 'Request body is required'}), 400

        # Validate origin coordinates
        origin = data.get('origin')
        if not origin or 'lat' not in origin or 'lon' not in origin:
            return jsonify({'error': 'origin with lat and lon is required'}), 400

        try:
            origin_lat = float(origin['lat'])
            origin_lon = float(origin['lon'])

            if not CoordinateValidator.validate_coordinates(origin_lat, origin_lon):
                return jsonify({'error': 'Invalid origin coordinates: Latitude must be between -90 and 90, Longitude must be between -180 and 180'}), 400

            origin = {'lat': origin_lat, 'lon': origin_lon}
        except (ValueError, TypeError):
            return jsonify({'error': 'Origin lat and lon must be valid numbers'}), 400

        # Handle destination or safe_zone_id
        destination = None
        safe_zone_id = data.get('safe_zone_id')

        if safe_zone_id:
            # Sanitize safe_zone_id: only allow alphanumeric, underscores, and hyphens
            if not re.match(r'^[a-zA-Z0-9_-]+$', safe_zone_id):
                return jsonify({'error': 'Invalid safe zone ID format'}), 400

            # Use safe zone as destination
            if not safe_zone_service:
                return jsonify({'error': 'Safe zone service not available'}), 503

            zone = safe_zone_service.get_zone_by_id(safe_zone_id)
            if not zone:
                return jsonify({'error': f'Safe zone not found: {safe_zone_id}'}), 404

            destination = {
                'lat': zone['location']['latitude'],
                'lon': zone['location']['longitude']
            }
            logger.info(f"Routing to safe zone {safe_zone_id}: {zone['name']}")

        else:
            # Use provided destination coordinates
            destination = data.get('destination')
            if not destination or 'lat' not in destination or 'lon' not in destination:
                return jsonify({'error': 'destination with lat and lon (or safe_zone_id) is required'}), 400

            try:
                dest_lat = float(destination['lat'])
                dest_lon = float(destination['lon'])

                if not CoordinateValidator.validate_coordinates(dest_lat, dest_lon):
                    return jsonify({'error': 'Invalid destination coordinates: Latitude must be between -90 and 90, Longitude must be between -180 and 180'}), 400

                destination = {'lat': dest_lat, 'lon': dest_lon}
            except (ValueError, TypeError):
                return jsonify({'error': 'Destination lat and lon must be valid numbers'}), 400

        # Optional parameters
        avoid_disasters = data.get('avoid_disasters', True)
        alternatives = data.get('alternatives', 3)

        # Validate alternatives (1-3)
        try:
            alternatives = int(alternatives)
            if not (1 <= alternatives <= 3):
                return jsonify({'error': 'alternatives must be between 1 and 3'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'alternatives must be a number'}), 400

        # Calculate routes
        logger.info(f"Calculating {alternatives} routes from {origin} to {destination} (avoid_disasters={avoid_disasters})")

        routes = route_service.calculate_routes(
            origin=origin,
            destination=destination,
            avoid_disasters=avoid_disasters,
            alternatives=alternatives
        )

        if not routes:
            return jsonify({
                'error': 'Unable to find drivable roads near your location. Please try moving to a nearby street or adjust your starting point.',
                'details': 'The routing service could not find a road within 350 meters of your location. This can happen if you are in a park, on private property, or in an area without road data.'
            }), 400

        # Get disaster polygons for response metadata
        disaster_polygons, active_disasters = route_service.get_disaster_polygons(origin, destination)

        # Find fastest and safest route indices
        fastest_route_index = None
        safest_route_index = None

        for idx, route in enumerate(routes):
            if route.get('is_fastest'):
                fastest_route_index = idx
            if route.get('is_safest'):
                safest_route_index = idx

        # Build response
        response = {
            'routes': routes,
            'avoided_disasters': active_disasters,
            'fastest_route_index': fastest_route_index,
            'safest_route_index': safest_route_index,
            'calculation_metadata': {
                'origin': origin,
                'destination': destination,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'disasters_considered': len(active_disasters),
                'avoid_disasters_enabled': avoid_disasters
            }
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error calculating routes: {e}", exc_info=True)
        return jsonify({'error': 'Failed to calculate routes'}), 500


@app.route('/api/routes/<route_id>/details', methods=['GET'])
@limiter.limit("100 per hour")
def get_route_details(route_id):
    """
    Get detailed information about a specific route.

    Path Parameters:
        route_id (str): Route identifier

    Returns:
        200: Route details (future implementation)
        404: Route not found (placeholder)
        501: Not yet implemented

    Note:
        This endpoint is a placeholder for future implementation.
        Route details are currently returned inline with the /calculate response.
    """
    # Placeholder endpoint for future implementation
    # Could be used for:
    # - Retrieving cached route calculations
    # - Getting real-time updates on route safety
    # - Fetching turn-by-turn navigation instructions
    return jsonify({
        'error': 'Route details endpoint not yet implemented',
        'message': 'Route details are currently returned with /api/routes/calculate response'
    }), 501


# ===== ERROR HANDLERS =====

@app.errorhandler(413)
def request_entity_too_large(error):
    """
    Handle requests that exceed MAX_CONTENT_LENGTH.

    Returns:
        413: Payload too large error
    """
    return jsonify({
        'error': 'Request payload too large',
        'max_size': '10 MB',
        'message': 'Please reduce the size of your request. Images should be compressed or uploaded separately.'
    }), 413


@app.errorhandler(400)
def bad_request(error):
    """
    Handle malformed requests.

    Returns:
        400: Bad request error
    """
    return jsonify({
        'error': 'Bad request',
        'message': str(error)
    }), 400


if __name__ == '__main__':
    # Use environment variable to control debug mode (defaults to False for production)
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5001)
