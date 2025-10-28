"""
Confidence Scoring System for Disaster Reports
Hybrid approach: Fast heuristics + AI enhancement with rate limiting
Supports OpenAI (GPT-4o-mini) with Gemini (gemini-2.0-flash-exp) fallback
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import os
from openai import OpenAI
import json
import hashlib
from firebase_admin import db
import logging
import math
from utils.distance import haversine_distance
from utils.validators import DisasterValidator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lazy import for Gemini (only if needed)
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.info("google-genai not installed - Gemini fallback disabled")


class ConfidenceScorer:
    """Calculate confidence scores for disaster reports using multi-stage approach"""

    # AI rate limiting configuration
    AI_REQUESTS_PER_HOUR = 50  # Limit OpenAI API calls
    AI_CACHE_DURATION_HOURS = 24  # Cache AI results for 24 hours

    def __init__(self, geocoding_service=None):
        """
        Initialize confidence scorer with OpenAI client and Gemini fallback

        Args:
            geocoding_service: Optional GeocodingService instance for location enrichment
        """
        # Initialize OpenAI (primary)
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_client = OpenAI(api_key=self.openai_api_key) if self.openai_api_key else None

        # Initialize Gemini (fallback)
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.gemini_client = None
        if GEMINI_AVAILABLE and self.gemini_api_key:
            try:
                self.gemini_client = genai.Client(api_key=self.gemini_api_key)
                logger.info("Gemini client initialized successfully (fallback enabled)")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client: {e}")

        self.geocoding_service = geocoding_service

        # Log AI status
        if self.openai_client:
            logger.info("OpenAI client initialized (primary AI provider)")
        elif self.gemini_client:
            logger.info("Only Gemini available - using as primary AI provider")
        else:
            logger.warning("No AI providers available - AI enhancement disabled")

        # Maintain backward compatibility
        self.client = self.openai_client or self.gemini_client

    def calculate_confidence(self, report: Dict, nearby_reports: List[Dict] = None, skip_ai: bool = False) -> Dict:
        """
        Calculate confidence score for a disaster report

        Args:
            report: Disaster report with source, location, timestamp, etc.
            nearby_reports: Optional list of nearby reports for corroboration
            skip_ai: If True, skip AI analysis (for fast initial submission)

        Returns:
            Dict with confidence_score (0-1), confidence_level (Low/Medium/High),
            and breakdown of scoring components
        """
        # Check if this is an official source - use simplified scoring
        source = report.get('source', 'unknown')
        if source in ['nasa_firms', 'noaa', 'usgs']:
            return self.calculate_official_source_confidence(report, source)

        # Stage 1: Fast heuristic scoring (always runs)
        heuristic_score, breakdown = self._calculate_heuristic_score(report)

        # Stage 2: Spatial corroboration (if nearby reports provided)
        if nearby_reports:
            corroboration_boost, corr_detail = self._calculate_corroboration(report, nearby_reports)
            heuristic_score = min(heuristic_score + corroboration_boost, 1.0)
            breakdown['corroboration'] = corr_detail

        # Stage 3: AI enhancement (async, rate-limited, user reports only)
        ai_result = None
        if not skip_ai and report.get('source') in ['user_report', 'user_report_authenticated'] and self._should_use_ai(report):
            ai_result = self._get_ai_enhancement(report, nearby_reports)
            if ai_result:
                # Blend heuristic and AI scores (70% heuristic, 30% AI)
                final_score = (heuristic_score * 0.7) + (ai_result['score'] * 0.3)
                breakdown['ai_enhancement'] = {
                    'score': ai_result['score'],
                    'reasoning': ai_result['reasoning']
                }
            else:
                final_score = heuristic_score
        else:
            final_score = heuristic_score

        # Determine confidence level
        if final_score >= 0.8:
            level = "High"
        elif final_score >= 0.6:
            level = "Medium"
        else:
            level = "Low"

        return {
            'confidence_score': round(final_score, 3),
            'confidence_level': level,
            'breakdown': breakdown
        }

    def calculate_confidence_with_user_credibility(self, report: Dict, user_credibility: int,
                                                   nearby_reports: List[Dict] = None, skip_ai: bool = False) -> Dict:
        """
        Calculate confidence score with user credibility penalty applied (Phase 7)

        Low-credibility users face base confidence penalties:
        - Expert/Veteran (75-100): 1.0 (no penalty)
        - Trusted (60-74): 0.95 (-5%)
        - Neutral (50-59): 0.90 (-10%)
        - Caution (30-49): 0.80 (-20%)
        - Unreliable (0-29): 0.65 (-35%)

        Args:
            report: Disaster report with source, location, timestamp, etc.
            user_credibility: User's credibility score (0-100)
            nearby_reports: Optional list of nearby reports for corroboration

        Returns:
            Dict with confidence_score (0-1), confidence_level (Low/Medium/High),
            and breakdown of scoring components
        """
        # Stage 1: Calculate heuristic score (without source credibility)
        heuristic_score, breakdown = self._calculate_heuristic_score(report)

        # Stage 2: Apply user credibility penalty to heuristic score
        base_multiplier = self._get_credibility_multiplier(user_credibility)
        penalized_score = heuristic_score * base_multiplier

        # Add credibility penalty to breakdown
        breakdown['user_credibility_penalty'] = {
            'user_credibility': user_credibility,
            'base_multiplier': base_multiplier,
            'original_heuristic': round(heuristic_score, 3),
            'after_penalty': round(penalized_score, 3)
        }

        # Stage 3: Spatial corroboration (applied after penalty)
        if nearby_reports:
            corroboration_boost, corr_detail = self._calculate_corroboration(report, nearby_reports)
            penalized_score = min(penalized_score + corroboration_boost, 1.0)
            breakdown['corroboration'] = corr_detail

        # Stage 4: AI enhancement (async, rate-limited)
        ai_result = None
        if not skip_ai and report.get('source') in ['user_report', 'user_report_authenticated'] and self._should_use_ai(report):
            ai_result = self._get_ai_enhancement(report, nearby_reports)
            if ai_result:
                # Blend penalized heuristic and AI scores (70% heuristic, 30% AI)
                final_score = (penalized_score * 0.7) + (ai_result['score'] * 0.3)
                breakdown['ai_enhancement'] = {
                    'score': ai_result['score'],
                    'reasoning': ai_result['reasoning']
                }
            else:
                final_score = penalized_score
        else:
            final_score = penalized_score

        # Determine confidence level
        if final_score >= 0.8:
            level = "High"
        elif final_score >= 0.6:
            level = "Medium"
        else:
            level = "Low"

        return {
            'confidence_score': round(final_score, 3),
            'confidence_level': level,
            'breakdown': breakdown
        }

    def _get_credibility_multiplier(self, user_credibility: int) -> float:
        """
        Get base confidence multiplier based on user credibility

        Args:
            user_credibility: User's credibility score (0-100)

        Returns:
            Multiplier to apply to heuristic score (0.65-1.0)
        """
        if user_credibility >= 75:
            return 1.0   # No penalty (Veteran/Expert)
        elif user_credibility >= 60:
            return 0.95  # -5% penalty (Trusted)
        elif user_credibility >= 50:
            return 0.90  # -10% penalty (Neutral)
        elif user_credibility >= 30:
            return 0.80  # -20% penalty (Caution)
        else:
            return 0.65  # -35% penalty (Unreliable)

    def calculate_official_source_confidence(self, report: Dict, source_type: str) -> Dict:
        """
        Calculate simplified confidence score for official sources (NASA FIRMS, NOAA)

        Official sources get high base scores (90-95%) with minor adjustments for:
        - Recency: +0-5% (fresher data = higher confidence)
        - Data completeness: +0-3% (all fields present = higher confidence)
        - Intensity/severity: +0-2% (higher severity/intensity = more validated)

        Final range: 90-100% (always High confidence)

        Args:
            report: Official disaster report data
            source_type: 'nasa_firms', 'noaa', or 'usgs'

        Returns:
            Dict with confidence_score (0.90-1.0), confidence_level ('High'),
            and breakdown of scoring components
        """
        # Base score for official sources
        if source_type == 'nasa_firms':
            base_score = 0.92
        elif source_type == 'usgs':
            base_score = 0.98  # USGS seismometer data is highly accurate
        else:  # noaa
            base_score = 0.90
        breakdown = {'source_credibility': base_score}

        # 1. Recency adjustment (+0-5%)
        timestamp = report.get('timestamp')
        recency_bonus = 0.0
        if timestamp:
            try:
                report_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                age_minutes = (now - report_time).total_seconds() / 60

                if age_minutes < 60:  # Within 1 hour
                    recency_bonus = 0.05
                elif age_minutes < 360:  # Within 6 hours
                    recency_bonus = 0.03
                elif age_minutes < 1440:  # Within 24 hours
                    recency_bonus = 0.01

                breakdown['recency_bonus'] = recency_bonus
            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to parse timestamp for official source: {e}")
                breakdown['recency_bonus'] = 0.0

        # 2. Data completeness adjustment (+0-3%)
        completeness_bonus = 0.0
        if source_type == 'nasa_firms':
            # Check for key NASA FIRMS fields
            required_fields = ['latitude', 'longitude', 'brightness', 'frp', 'confidence']
            present_count = sum(1 for f in required_fields if report.get(f) is not None)
            completeness_bonus = (present_count / len(required_fields)) * 0.03
        elif source_type == 'noaa':
            # Check for key NOAA fields
            required_fields = ['latitude', 'longitude', 'severity', 'urgency', 'certainty']
            present_count = sum(1 for f in required_fields if report.get(f) is not None)
            completeness_bonus = (present_count / len(required_fields)) * 0.03
        elif source_type == 'usgs':
            # Check for key USGS fields
            required_fields = ['latitude', 'longitude', 'magnitude', 'depth_km', 'place']
            present_count = sum(1 for f in required_fields if report.get(f) is not None)
            completeness_bonus = (present_count / len(required_fields)) * 0.03

        breakdown['completeness_bonus'] = round(completeness_bonus, 3)

        # 3. Intensity/severity validation (+0-2%)
        intensity_bonus = 0.0
        if source_type == 'nasa_firms':
            # High brightness/FRP indicates validated wildfire
            brightness = report.get('brightness', 0)
            frp = report.get('frp', 0)
            if brightness > 360 or frp > 100:
                intensity_bonus = 0.02
            elif brightness > 340 or frp > 50:
                intensity_bonus = 0.015
            elif brightness > 320 or frp > 20:
                intensity_bonus = 0.01
        elif source_type == 'noaa':
            # High severity/urgency indicates validated alert
            severity = report.get('severity', '').lower()
            urgency = report.get('urgency', '').lower()
            if severity == 'extreme' or urgency == 'immediate':
                intensity_bonus = 0.02
            elif severity == 'severe' or urgency == 'expected':
                intensity_bonus = 0.015
            elif severity == 'moderate':
                intensity_bonus = 0.01
        elif source_type == 'usgs':
            # Higher magnitude earthquakes are more significant
            magnitude = report.get('magnitude', 0)
            if magnitude >= 7.0:
                intensity_bonus = 0.02  # Major/Great earthquake
            elif magnitude >= 6.0:
                intensity_bonus = 0.015  # Strong earthquake
            elif magnitude >= 5.0:
                intensity_bonus = 0.01  # Moderate earthquake

        breakdown['intensity_bonus'] = round(intensity_bonus, 3)

        # Calculate final score (capped at 1.0)
        final_score = min(base_score + recency_bonus + completeness_bonus + intensity_bonus, 1.0)

        return {
            'confidence_score': round(final_score, 3),
            'confidence_level': 'High',  # Official sources always High
            'breakdown': breakdown
        }

    def _calculate_heuristic_score(self, report: Dict) -> tuple:
        """
        Fast heuristic confidence calculation

        Returns:
            (score, breakdown_dict)
        """
        score = 0.0  # Start with zero, weights should sum to 1.0
        breakdown = {}

        # 1. Source Credibility (40% weight)
        source = report.get('source', 'unknown')
        if source == 'nasa_firms':
            source_score = 0.95
        elif source == 'noaa':
            source_score = 0.95
        elif source == 'usgs':
            source_score = 0.98  # USGS seismometer data is highly accurate
        elif source in ['user_report', 'user_report_authenticated']:
            # User credibility based on reCAPTCHA if available
            # More tolerant: 0.5 to 0.85 range (users are trustworthy in emergencies)
            recaptcha_score = report.get('recaptcha_score', 0.7)  # Default to 0.7 instead of 0.5
            source_score = 0.5 + (recaptcha_score * 0.35)
        else:
            source_score = 0.5

        breakdown['source_credibility'] = source_score
        score += source_score * 0.4

        # 2. Temporal Recency (20% weight)
        # Always include recency in breakdown for score comparability
        timestamp = report.get('timestamp')
        if timestamp:
            recency_score = self._calculate_recency_score(timestamp)
        else:
            recency_score = 0.5  # Default to neutral score if no timestamp
        breakdown['recency'] = recency_score
        score += recency_score * 0.2

        # 3. Spatial Validation (20% weight) - for user reports
        if source in ['user_report', 'user_report_authenticated']:
            spatial_score = self._calculate_spatial_score(report)
            breakdown['spatial_validation'] = spatial_score
            score += spatial_score * 0.2
        else:
            # Official sources automatically get full spatial score
            breakdown['spatial_validation'] = 1.0
            score += 0.2

        # 4. Data Completeness (10% weight)
        completeness = self._calculate_completeness(report)
        breakdown['completeness'] = completeness
        score += completeness * 0.1

        # 5. Type-specific validation (10% weight)
        type_score = self._calculate_type_validation(report)
        breakdown['type_validation'] = type_score
        score += type_score * 0.1

        return min(score, 1.0), breakdown

    def _calculate_recency_score(self, timestamp_str: str) -> float:
        """Calculate score based on how recent the report is"""
        try:
            # Parse timestamp with timezone awareness
            report_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

            # Use timezone-aware datetime for comparison
            now = datetime.now(timezone.utc)

            # Calculate age using timezone-aware datetimes
            age_minutes = (now - report_time).total_seconds() / 60

            # More tolerant decay for emergency situations
            if age_minutes < 15:
                return 1.0
            elif age_minutes < 60:
                return 0.9
            elif age_minutes < 360:  # 6 hours
                return 0.8
            elif age_minutes < 1440:  # 24 hours
                return 0.7
            else:
                # Slower decay after 24 hours
                return max(0.5, 0.7 * (0.97 ** (age_minutes / 1440)))
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
            return 0.5

    def _calculate_spatial_score(self, report: Dict) -> float:
        """Validate spatial aspects of user reports"""
        score = 0.5

        # User distance from incident (if provided)
        user_distance = report.get('user_distance_mi')
        if user_distance is not None:
            if user_distance < 1:
                score = 1.0  # Very close
            elif user_distance < 5:
                score = 0.9
            elif user_distance < 10:
                score = 0.7
            elif user_distance < 50:
                score = 0.5
            else:
                score = 0.3  # Far away, less credible

        return score

    def _calculate_completeness(self, report: Dict) -> float:
        """Score based on how complete the report data is"""
        # Core fields: location and type are essential
        core_fields = ['latitude', 'longitude', 'type']
        # Nice to have: description helps but not required for emergencies
        bonus_fields = ['description', 'severity', 'affected_population']

        core_present = sum(1 for f in core_fields if report.get(f))
        bonus_present = sum(1 for f in bonus_fields if report.get(f))

        # Core fields are 80% of score, bonus fields are 20%
        core_score = core_present / len(core_fields)
        bonus_score = bonus_present / len(bonus_fields)

        return (core_score * 0.8) + (bonus_score * 0.2)

    def _calculate_type_validation(self, report: Dict) -> float:
        """
        Validate disaster type makes sense.

        Uses centralized DisasterValidator for consistency.
        """
        disaster_type = report.get('type') or report.get('disaster_type')

        if not disaster_type:
            return 0.3  # No type specified

        if DisasterValidator.validate_disaster_type(disaster_type):
            return 1.0
        else:
            return 0.5  # Has a type but not in our list

    def _calculate_corroboration(self, report: Dict, nearby_reports: List[Dict]) -> tuple:
        """
        Calculate confidence boost from nearby corroborating reports

        Considers:
        - Distance (closer = higher weight)
        - Source credibility (official sources worth more)
        - Severity/intensity matching (similar severity = higher boost)
        - Recency (within 24 hours)

        Returns:
            (boost_amount, detail_dict)
        """
        if not nearby_reports:
            return 0.0, {'nearby_count': 0, 'boost': 0.0, 'sources': {}}

        report_type = report.get('type') or report.get('disaster_type')
        report_lat = report.get('latitude')
        report_lon = report.get('longitude')
        report_severity = report.get('severity', 'medium')
        report_time = report.get('timestamp')

        if not report_lat or not report_lon:
            return 0.0, {'nearby_count': 0, 'boost': 0.0, 'sources': {}}

        # Score each nearby report
        corroboration_scores = []
        source_counts = {'user_report': 0, 'nasa_firms': 0, 'noaa': 0, 'usgs': 0, 'other': 0}

        for nearby in nearby_reports:
            nearby_type = nearby.get('type') or nearby.get('disaster_type')
            nearby_lat = nearby.get('latitude')
            nearby_lon = nearby.get('longitude')
            nearby_source = nearby.get('source', 'unknown')

            # Skip if different disaster type or missing coordinates
            if nearby_type != report_type or not nearby_lat or not nearby_lon:
                continue

            # Skip if same report (comparing IDs)
            if report.get('id') and nearby.get('id') and report['id'] == nearby['id']:
                continue

            # Calculate distance
            distance_mi = haversine_distance(
                report_lat, report_lon, nearby_lat, nearby_lon
            )

            # Skip if too far away (> 50 miles)
            if distance_mi > 50:
                continue

            # Check recency (within 24 hours)
            if report_time and nearby.get('timestamp'):
                time_diff = self._time_difference_hours(report_time, nearby.get('timestamp'))
                if abs(time_diff) > 24:
                    continue

            # Distance score (closer = higher, exponential decay)
            # 0-5 mi = 1.0, 5-15 mi = 0.8, 15-30 mi = 0.5, 30-50 mi = 0.2
            if distance_mi <= 5:
                distance_score = 1.0
            elif distance_mi <= 15:
                distance_score = 0.8
            elif distance_mi <= 30:
                distance_score = 0.5
            else:
                distance_score = 0.2

            # Source weight (official sources more credible)
            if nearby_source in ['nasa_firms', 'noaa', 'usgs']:
                source_weight = 1.5  # Official sources worth 1.5x
                source_counts[nearby_source] = source_counts.get(nearby_source, 0) + 1
            elif nearby_source in ['user_report', 'user_report_authenticated']:
                source_weight = 1.0
                source_counts['user_report'] += 1
            else:
                source_weight = 0.8
                source_counts['other'] += 1

            # Severity matching (optional, intensity for wildfires/weather)
            severity_match = 1.0
            if report_severity and nearby.get('severity'):
                nearby_severity = nearby.get('severity', 'medium')
                if report_severity == nearby_severity:
                    severity_match = 1.2  # Exact match bonus
                elif self._severity_adjacent(report_severity, nearby_severity):
                    severity_match = 1.0  # Adjacent severity OK
                else:
                    severity_match = 0.8  # Different severity, slight penalty

            # For wildfires, check brightness/FRP intensity
            if report_type == 'wildfire' and nearby.get('brightness'):
                nearby_brightness = nearby.get('brightness', 0)
                if nearby_brightness > 350:  # High intensity fire
                    severity_match = max(severity_match, 1.2)
                elif nearby_brightness > 320:
                    severity_match = max(severity_match, 1.0)

            # Calculate corroboration score for this report
            score = distance_score * source_weight * severity_match
            corroboration_scores.append({
                'id': nearby.get('id'),
                'source': nearby_source,
                'distance_mi': round(distance_mi, 2),
                'score': score
            })

        # Calculate total boost based on weighted scores
        if not corroboration_scores:
            return 0.0, {'nearby_count': 0, 'boost': 0.0, 'sources': source_counts}

        # Sort by score (highest first)
        corroboration_scores.sort(key=lambda x: x['score'], reverse=True)

        # Sum top scores with diminishing returns
        total_score = 0.0
        for i, item in enumerate(corroboration_scores[:5]):  # Cap at 5 reports
            weight = 1.0 / (i + 1)  # Diminishing returns: 1.0, 0.5, 0.33, 0.25, 0.2
            total_score += item['score'] * weight

        # Convert to boost (max 0.35 = 35%)
        # Scale: 0-1 score → 0%, 1-2 → 10%, 2-3 → 20%, 3-4 → 30%, 4+ → 35%
        if total_score >= 4.0:
            boost = 0.35
        elif total_score >= 3.0:
            boost = 0.30
        elif total_score >= 2.0:
            boost = 0.20
        elif total_score >= 1.0:
            boost = 0.10
        else:
            boost = 0.05

        return boost, {
            'nearby_count': len(corroboration_scores),
            'boost': boost,
            'total_score': round(total_score, 2),
            'sources': source_counts,
            'top_matches': corroboration_scores[:3]  # Top 3 for debugging
        }

    def _should_use_ai(self, report: Dict) -> bool:
        """Determine if AI enhancement should be used (rate limiting)"""
        if not self.client:
            return False

        # Check rate limit
        if not self._check_rate_limit():
            logger.warning("AI rate limit reached, using heuristic only")
            return False

        # Check cache - avoid re-analyzing same content
        if self._has_cached_ai_result(report):
            return False

        # Only use AI for reports with description or image
        has_content = report.get('description') or report.get('image_url')

        return bool(has_content)

    def _check_rate_limit_readonly(self) -> bool:
        """Check if we're within AI API rate limits (read-only, doesn't increment)"""
        try:
            ref = db.reference('ai_usage_tracking/hourly')
            current_hour = datetime.now(timezone.utc).strftime('%Y-%m-%d-%H')
            usage = ref.child(current_hour).get() or 0
            return usage < self.AI_REQUESTS_PER_HOUR
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False

    def _check_rate_limit(self) -> bool:
        """Check if we're within AI API rate limits and increment counter"""
        try:
            ref = db.reference('ai_usage_tracking/hourly')
            current_hour = datetime.now(timezone.utc).strftime('%Y-%m-%d-%H')

            usage = ref.child(current_hour).get() or 0

            if usage >= self.AI_REQUESTS_PER_HOUR:
                return False

            # Increment counter
            ref.child(current_hour).set(usage + 1)

            # Clean up old tracking data (keep only last 24 hours)
            self._cleanup_old_tracking()

            return True
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False

    def _cleanup_old_tracking(self):
        """Remove tracking data older than 24 hours"""
        try:
            ref = db.reference('ai_usage_tracking/hourly')
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

            all_tracking = ref.get() or {}
            for hour_key in list(all_tracking.keys()):
                try:
                    hour_time = datetime.strptime(hour_key, '%Y-%m-%d-%H')
                    # Make cutoff timezone-naive for comparison
                    if hour_time < cutoff.replace(tzinfo=None):
                        ref.child(hour_key).delete()
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Failed to parse tracking key '{hour_key}': {e}")
                    continue
        except Exception as e:
            logger.error(f"Error cleaning up tracking: {e}")

    def _has_cached_ai_result(self, report: Dict) -> bool:
        """Check if we have a recent AI analysis cached for this content"""
        try:
            # Create hash of content for cache key (using SHA-256 for better collision resistance)
            content = f"{report.get('description', '')}{report.get('image_url', '')}"
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            ref = db.reference(f'ai_analysis_cache/{content_hash}')
            cached = ref.get()

            if cached and 'timestamp' in cached:
                cached_time = datetime.fromisoformat(cached['timestamp'])
                now = datetime.now(timezone.utc)
                # Ensure both are timezone-aware for comparison
                if cached_time.tzinfo is None:
                    cached_time = cached_time.replace(tzinfo=timezone.utc)
                age_hours = (now - cached_time).total_seconds() / 3600

                if age_hours < self.AI_CACHE_DURATION_HOURS:
                    return True

            return False
        except (ValueError, AttributeError, KeyError) as e:
            logger.warning(f"Error checking AI cache: {e}")
            return False

    def _get_ai_enhancement(self, report: Dict, nearby_reports: List[Dict] = None) -> Optional[Dict]:
        """
        Use AI (OpenAI or Gemini) to analyze report credibility with nearby context
        Tries OpenAI first, falls back to Gemini if OpenAI fails

        Args:
            report: Disaster report to analyze
            nearby_reports: Optional list of nearby reports for corroboration context

        Returns:
            Dict with 'score', 'reasoning', and 'provider' or None if unavailable
        """
        if not self.client:
            return None

        # Build analysis prompt with nearby context
        prompt = self._build_ai_prompt(report, nearby_reports)
        system_prompt = "You are an expert at analyzing disaster reports for credibility during emergency situations. Be lenient with brief descriptions - people in crisis prioritize speed over detail. Focus on plausibility and corroboration from nearby sources. Respond with a JSON object containing a 'confidence_score' (0.0-1.0) and 'reasoning' (brief explanation)."

        # Try OpenAI first (primary)
        if self.openai_client:
            try:
                logger.debug("Attempting AI analysis with OpenAI GPT-4o-mini")
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,
                    max_tokens=200
                )

                # Parse response
                result = json.loads(response.choices[0].message.content)
                score = result.get('confidence_score', 0.5)
                reasoning = result.get('reasoning', '')

                # Cache the result
                self._cache_ai_result(report, score, reasoning)

                logger.info("AI analysis completed successfully with OpenAI")
                return {
                    'score': min(max(score, 0.0), 1.0),
                    'reasoning': reasoning,
                    'provider': 'openai'
                }

            except Exception as e:
                logger.warning(f"OpenAI API failed: {e}. Falling back to Gemini...")

        # Fallback to Gemini if OpenAI failed or not available
        if self.gemini_client:
            try:
                logger.debug("Attempting AI analysis with Gemini 2.0 Flash")

                # Combine system prompt and user prompt for Gemini
                full_prompt = f"{system_prompt}\n\n{prompt}"

                response = self.gemini_client.models.generate_content(
                    model='gemini-2.0-flash-exp',
                    contents=full_prompt,
                    config={
                        'response_mime_type': 'application/json',
                        'response_schema': {
                            'type': 'OBJECT',
                            'required': ['confidence_score', 'reasoning'],
                            'properties': {
                                'confidence_score': {
                                    'type': 'NUMBER',
                                    'description': 'Confidence score between 0.0 and 1.0'
                                },
                                'reasoning': {
                                    'type': 'STRING',
                                    'description': 'Brief explanation of the confidence score'
                                }
                            }
                        },
                        'temperature': 0.3,
                        'max_output_tokens': 200
                    }
                )

                # Parse response
                result = json.loads(response.text)
                score = result.get('confidence_score', 0.5)
                reasoning = result.get('reasoning', '')

                # Cache the result
                self._cache_ai_result(report, score, reasoning)

                logger.info("AI analysis completed successfully with Gemini")
                return {
                    'score': min(max(score, 0.0), 1.0),
                    'reasoning': reasoning,
                    'provider': 'gemini'
                }

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini response as JSON: {e}")
            except Exception as e:
                logger.error(f"Gemini API failed: {e}")

        # Both providers failed
        logger.error("All AI providers failed - returning None")
        return None

    def _build_ai_prompt(self, report: Dict, nearby_reports: List[Dict] = None) -> str:
        """Build enhanced prompt for AI analysis with nearby context"""
        disaster_type = report.get('type') or report.get('disaster_type', 'unknown')
        description = report.get('description', 'No description provided')
        severity = report.get('severity', 'unknown')

        # NEW: Get human-readable location (Phase 5 enhancement)
        latitude = report.get('latitude')
        longitude = report.get('longitude')

        if self.geocoding_service and latitude is not None and longitude is not None:
            location = self.geocoding_service.format_location_for_ai(latitude, longitude)
        else:
            location = f"({latitude}, {longitude})"

        # Calculate nearby report statistics
        nearby_stats = self._calculate_nearby_stats(report, nearby_reports)

        # Calculate distance to nearest official source
        distance_to_official = self._get_distance_to_nearest_official(report, nearby_reports)

        prompt = f"""Analyze this disaster report for credibility:

**Report Details:**
- Type: {disaster_type}
- Severity: {severity}
- Location: {location}
- Description: {description}

**Corroboration Context:**
- Nearby user reports (same type, within 50 miles): {nearby_stats['user_reports_count']}
- Nearby official sources (NASA/NOAA, within 50 miles): {nearby_stats['official_reports_count']}
- Distance to nearest official disaster: {distance_to_official}

**Assessment Criteria:**
1. Text coherence - Is the description clear and logical?
   - NOTE: During emergencies, people may write brief, terse descriptions. This is ACCEPTABLE.
   - Focus on plausibility, not comprehensiveness.
   - A short report like "Fire on hillside, smoke visible" is credible if coherent.

2. Plausibility - Does the disaster type make sense for this description AND location?
   - Consider the nearby official sources and user reports.
   - Consider if the disaster type is plausible for the geographic location.
   - Example: Wildfires in California forests = plausible. Hurricanes in Nevada desert = implausible.
   - Proximity to official disasters increases credibility.

3. Specificity - Are details specific or vague?
   - Specific details (landmarks, times, observations) = higher confidence
   - Generic descriptions = lower confidence
   - But brevity ≠ vagueness in emergency situations

**Corroboration Weight:**
- If nearby official sources exist at similar location → HIGH confidence boost
- If multiple user reports nearby → MEDIUM confidence boost
- If isolated report with no nearby sources → evaluate on description alone

**Return JSON:**
{{
  "confidence_score": 0.0-1.0,
  "reasoning": "Brief explanation (1-2 sentences) focusing on plausibility and corroboration"
}}

**Remember:** In disaster situations, people prioritize speed over detail. Do not penalize brief but coherent reports."""

        return prompt

    def _cache_ai_result(self, report: Dict, score: float, reasoning: str):
        """Cache AI analysis results"""
        try:
            content = f"{report.get('description', '')}{report.get('image_url', '')}"
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            ref = db.reference(f'ai_analysis_cache/{content_hash}')
            ref.set({
                'score': score,
                'reasoning': reasoning,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.error(f"Error caching AI result: {e}")

    def _time_difference_hours(self, time1_str: str, time2_str: str) -> float:
        """
        Calculate time difference between two ISO timestamp strings

        Returns:
            Time difference in hours (positive if time2 is after time1)
        """
        try:
            # Handle both timezone-aware and naive timestamps
            time1 = datetime.fromisoformat(time1_str.replace('Z', '+00:00'))
            time2 = datetime.fromisoformat(time2_str.replace('Z', '+00:00'))

            # Make both timezone-aware if either is naive
            if time1.tzinfo is None:
                time1 = time1.replace(tzinfo=timezone.utc)
            if time2.tzinfo is None:
                time2 = time2.replace(tzinfo=timezone.utc)

            diff = (time2 - time1).total_seconds() / 3600
            return diff
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse timestamps: {e}")
            return 0.0

    def _severity_adjacent(self, sev1: str, sev2: str) -> bool:
        """
        Check if two severity levels are adjacent (within 1 step)

        Severity order: low < medium < high < critical
        """
        severity_order = ['low', 'medium', 'high', 'critical']

        try:
            idx1 = severity_order.index(sev1.lower())
            idx2 = severity_order.index(sev2.lower())
            return abs(idx1 - idx2) == 1
        except (ValueError, AttributeError):
            return False

    def _calculate_nearby_stats(self, report: Dict, nearby_reports: List[Dict]) -> Dict:
        """Calculate statistics about nearby reports for AI context"""
        if not nearby_reports:
            return {
                'user_reports_count': 0,
                'official_reports_count': 0,
                'total_count': 0
            }

        report_type = report.get('type') or report.get('disaster_type')
        user_count = 0
        official_count = 0

        for nearby in nearby_reports:
            nearby_type = nearby.get('type') or nearby.get('disaster_type')
            nearby_source = nearby.get('source', 'unknown')

            # Only count same disaster type
            if nearby_type != report_type:
                continue

            # Skip self
            if report.get('id') and nearby.get('id') and report['id'] == nearby['id']:
                continue

            if nearby_source in ['nasa_firms', 'noaa', 'usgs']:
                official_count += 1
            elif nearby_source in ['user_report', 'user_report_authenticated']:
                user_count += 1

        return {
            'user_reports_count': user_count,
            'official_reports_count': official_count,
            'total_count': user_count + official_count
        }

    def _get_distance_to_nearest_official(self, report: Dict, nearby_reports: List[Dict]) -> str:
        """Find distance to nearest official disaster source"""
        if not nearby_reports:
            return "No official sources found within 50 miles"

        report_lat = report.get('latitude')
        report_lon = report.get('longitude')
        report_type = report.get('type') or report.get('disaster_type')

        if not report_lat or not report_lon:
            return "Unknown (coordinates missing)"

        min_distance = float('inf')
        nearest_source = None

        for nearby in nearby_reports:
            nearby_source = nearby.get('source', 'unknown')
            nearby_type = nearby.get('type') or nearby.get('disaster_type')
            nearby_lat = nearby.get('latitude')
            nearby_lon = nearby.get('longitude')

            # Only check official sources of same type
            if nearby_source not in ['nasa_firms', 'noaa', 'usgs']:
                continue
            if nearby_type != report_type:
                continue
            if not nearby_lat or not nearby_lon:
                continue

            distance = haversine_distance(report_lat, report_lon, nearby_lat, nearby_lon)
            if distance < min_distance:
                min_distance = distance
                nearest_source = nearby_source

        if min_distance == float('inf'):
            return "No official sources found within 50 miles"
        elif min_distance < 1:
            return f"<1 mile (from {nearest_source})"
        elif min_distance < 5:
            return f"~{round(min_distance)} miles (from {nearest_source})"
        else:
            return f"~{round(min_distance)} miles (from {nearest_source})"
