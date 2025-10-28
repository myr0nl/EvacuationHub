"""
User Credibility Service
Implements Phase 7 user reputation system with role reversal mechanics
"""
from firebase_admin import db
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import logging
import math
from utils.distance import haversine_distance

logger = logging.getLogger(__name__)


class CredibilityService:
    """User credibility scoring and management"""

    # Credibility level thresholds
    CREDIBILITY_LEVELS = [
        {'min': 90, 'max': 100, 'name': 'Expert', 'badge': '🌟', 'multiplier': 1.0},
        {'min': 75, 'max': 89, 'name': 'Veteran', 'badge': '🏅', 'multiplier': 1.0},
        {'min': 60, 'max': 74, 'name': 'Trusted', 'badge': '✅', 'multiplier': 0.95},
        {'min': 50, 'max': 59, 'name': 'Neutral', 'badge': '⚪', 'multiplier': 0.90},
        {'min': 30, 'max': 49, 'name': 'Caution', 'badge': '⚠️', 'multiplier': 0.80},
        {'min': 0, 'max': 29, 'name': 'Unreliable', 'badge': '🔴', 'multiplier': 0.65}
    ]

    def __init__(self):
        """Initialize credibility service"""
        pass

    def get_user_credibility(self, user_id: str) -> int:
        """
        Get current credibility score for user

        Args:
            user_id: Firebase user ID

        Returns:
            Credibility score (0-100), defaults to 50 if user not found
        """
        try:
            user_ref = db.reference(f'users/{user_id}')
            user_data = user_ref.get()

            if not user_data:
                return 50  # Default neutral credibility

            return user_data.get('credibility_score', 50)

        except Exception as e:
            logger.error(f"Error fetching credibility for {user_id}: {e}")
            return 50

    def get_credibility_level(self, credibility_score: int) -> Dict:
        """
        Get credibility level details from score

        Args:
            credibility_score: User's credibility score (0-100)

        Returns:
            Dict with name, badge, multiplier
        """
        for level in self.CREDIBILITY_LEVELS:
            if level['min'] <= credibility_score <= level['max']:
                return {
                    'name': level['name'],
                    'badge': level['badge'],
                    'multiplier': level['multiplier']
                }

        # Fallback to Neutral
        return {
            'name': 'Neutral',
            'badge': '⚪',
            'multiplier': 0.90
        }

    def apply_base_confidence_penalty(self, user_credibility: int) -> float:
        """
        Calculate base confidence multiplier based on user credibility

        Low-credibility users face progressive penalties:
        - Expert/Veteran (75-100): 1.0 (no penalty)
        - Trusted (60-74): 0.95 (-5%)
        - Neutral (50-59): 0.90 (-10%)
        - Caution (30-49): 0.80 (-20%)
        - Unreliable (0-29): 0.65 (-35%)

        Args:
            user_credibility: User's credibility score (0-100)

        Returns:
            Multiplier to apply to heuristic confidence score (0.65-1.0)
        """
        level = self.get_credibility_level(user_credibility)
        return level['multiplier']

    def calculate_user_credibility_change(self, final_confidence_score: float) -> int:
        """
        Calculate credibility change based on report's final confidence score

        Args:
            final_confidence_score: Final confidence score (0.0-1.0)

        Returns:
            Credibility delta (-3 to +5 points)
        """
        if final_confidence_score >= 0.90:
            return +5  # Exceptional report (90%+ confidence)
        elif final_confidence_score >= 0.80:
            return +3  # High confidence report
        elif final_confidence_score >= 0.70:
            return +2  # Good confidence report
        elif final_confidence_score >= 0.60:
            return +1  # Medium confidence report
        elif final_confidence_score >= 0.50:
            return 0   # Neutral (no change)
        elif final_confidence_score >= 0.40:
            return -1  # Low confidence report
        elif final_confidence_score >= 0.30:
            return -2  # Very low confidence report
        else:
            return -3  # Extremely low confidence report

    def update_user_credibility(self, user_id: str, report_confidence: float,
                                report_lat: float, report_lon: float) -> Dict:
        """
        Update user credibility after report submission

        Applies:
        - Base credibility change based on confidence score
        - Recovery bonuses for low-credibility users
        - Diminishing returns for location farming
        - Spam detection penalties

        Args:
            user_id: Firebase user ID
            report_confidence: Final confidence score (0.0-1.0)
            report_lat: Report latitude (for spam detection)
            report_lon: Report longitude (for spam detection)

        Returns:
            Dict with old_credibility, new_credibility, delta, reason
        """
        try:
            user_ref = db.reference(f'users/{user_id}')
            user_data = user_ref.get()

            if not user_data:
                logger.warning(f"User {user_id} not found, cannot update credibility")
                return {'old_credibility': 50, 'new_credibility': 50, 'delta': 0, 'reason': 'User not found'}

            old_credibility = user_data.get('credibility_score', 50)

            # Calculate base credibility change
            base_change = self.calculate_user_credibility_change(report_confidence)

            # Check for spam patterns (returns penalty if spam detected)
            spam_check = self._check_spam_pattern(user_id, report_lat, report_lon)
            if spam_check['is_spam']:
                # Apply spam penalty immediately
                spam_penalty = spam_check['penalty']
                new_credibility = max(0, min(100, old_credibility + spam_penalty))

                # Update database
                user_ref.update({
                    'credibility_score': new_credibility,
                    'credibility_level': self.get_credibility_level(new_credibility)['name'],
                    'last_report_timestamp': datetime.now(timezone.utc).isoformat()
                })

                # Log credibility change
                self._log_credibility_change(user_id, old_credibility, new_credibility,
                                             spam_penalty, spam_check['reason'])

                return {
                    'old_credibility': old_credibility,
                    'new_credibility': new_credibility,
                    'delta': spam_penalty,
                    'reason': spam_check['reason']
                }

            # Apply recovery bonus for low-credibility users
            if old_credibility < 30 and report_confidence >= 0.80:
                recovery_bonus = 2  # Extra +2 points for high-quality recovery
                final_change = base_change + recovery_bonus
                reason = f"High confidence report ({report_confidence:.0%}) + recovery bonus"
            elif old_credibility < 50 and report_confidence >= 0.85:
                recovery_bonus = 1  # Extra +1 point for quality improvement
                final_change = base_change + recovery_bonus
                reason = f"High confidence report ({report_confidence:.0%}) + recovery bonus"
            else:
                # Apply diminishing returns for location farming
                diminishing = self._calculate_location_diminishing_returns(user_id, report_lat, report_lon)
                final_change = int(base_change * diminishing)

                if diminishing < 1.0:
                    reason = f"Report confidence {report_confidence:.0%} (diminishing returns: {diminishing:.0%})"
                else:
                    confidence_desc = self._get_confidence_description(report_confidence)
                    reason = f"{confidence_desc} ({report_confidence:.0%})"

            # Update credibility score (clamp to 0-100)
            new_credibility = max(0, min(100, old_credibility + final_change))

            # Update database
            user_ref.update({
                'credibility_score': new_credibility,
                'credibility_level': self.get_credibility_level(new_credibility)['name'],
                'total_reports': user_data.get('total_reports', 0) + 1,
                'last_report_timestamp': datetime.now(timezone.utc).isoformat()
            })

            # Log credibility change
            self._log_credibility_change(user_id, old_credibility, new_credibility, final_change, reason)

            return {
                'old_credibility': old_credibility,
                'new_credibility': new_credibility,
                'delta': final_change,
                'reason': reason
            }

        except Exception as e:
            logger.error(f"Error updating credibility for {user_id}: {e}")
            return {'old_credibility': 50, 'new_credibility': 50, 'delta': 0, 'reason': 'Error updating'}

    def _calculate_location_diminishing_returns(self, user_id: str, lat: float, lon: float) -> float:
        """
        Reduce credibility gains for multiple reports in same area (anti-farming)

        Args:
            user_id: Firebase user ID
            lat: Report latitude
            lon: Report longitude

        Returns:
            Credibility gain multiplier (1.0 to 0.2)
        """
        try:
            # Get user's reports in past 24 hours
            reports_ref = db.reference(f'user_reports/{user_id}/reports')
            all_reports = reports_ref.get() or {}

            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

            # Count reports within 10km radius in last 24 hours
            recent_nearby_count = 0
            for report_data in all_reports.values():
                report_time_str = report_data.get('timestamp')
                report_lat = report_data.get('latitude')
                report_lon = report_data.get('longitude')

                if not report_time_str or report_lat is None or report_lon is None:
                    continue

                report_time = datetime.fromisoformat(report_time_str.replace('Z', '+00:00'))
                if report_time.tzinfo is None:
                    report_time = report_time.replace(tzinfo=timezone.utc)

                if report_time < cutoff_time:
                    continue

                # Calculate distance
                distance_mi = haversine_distance(lat, lon, report_lat, report_lon)

                if distance_mi <= 10:  # Within 10 miles
                    recent_nearby_count += 1

            # Apply diminishing returns
            if recent_nearby_count == 0:
                return 1.0   # Full credibility gain
            elif recent_nearby_count == 1:
                return 0.75  # 25% reduction (2nd report in same area)
            elif recent_nearby_count == 2:
                return 0.50  # 50% reduction (3rd report)
            else:
                return 0.20  # 80% reduction (4+ reports, spam detected)

        except Exception as e:
            logger.error(f"Error calculating diminishing returns: {e}")
            return 1.0

    def _check_spam_pattern(self, user_id: str, lat: float, lon: float) -> Dict:
        """
        Detect suspicious reporting patterns

        Checks:
        - Duplicate location spam (<1 hour, <1km distance)
        - Volume spam (>10 reports in 24 hours)
        - Low-quality streak (5 consecutive reports <60% confidence)

        Args:
            user_id: Firebase user ID
            lat: Report latitude
            lon: Report longitude

        Returns:
            Dict with is_spam, penalty, reason
        """
        try:
            reports_ref = db.reference(f'user_reports/{user_id}/reports')
            all_reports = reports_ref.get() or {}

            cutoff_time_24h = datetime.now(timezone.utc) - timedelta(hours=24)
            cutoff_time_1h = datetime.now(timezone.utc) - timedelta(hours=1)

            recent_reports = []
            very_recent_reports = []

            for report_data in all_reports.values():
                report_time_str = report_data.get('timestamp')
                if not report_time_str:
                    continue

                report_time = datetime.fromisoformat(report_time_str.replace('Z', '+00:00'))
                if report_time.tzinfo is None:
                    report_time = report_time.replace(tzinfo=timezone.utc)

                if report_time >= cutoff_time_24h:
                    recent_reports.append(report_data)
                if report_time >= cutoff_time_1h:
                    very_recent_reports.append(report_data)

            # Check 1: Volume spam (>10 reports in 24 hours)
            if len(recent_reports) > 10:
                return {
                    'is_spam': True,
                    'penalty': -5,
                    'reason': 'Spam detected: Excessive reporting (>10 reports/day)'
                }

            # Check 2: Duplicate location spam
            for report in very_recent_reports:
                report_lat = report.get('latitude')
                report_lon = report.get('longitude')

                if report_lat is None or report_lon is None:
                    continue

                distance_mi = haversine_distance(lat, lon, report_lat, report_lon)

                if distance_mi < 1:  # Same location (<1 mile)
                    return {
                        'is_spam': True,
                        'penalty': -5,
                        'reason': 'Spam detected: Duplicate location (<1 hour, <1 mile)'
                    }

            # Check 3: Low-quality streak (last 5 reports all <60% confidence)
            sorted_reports = sorted(recent_reports, key=lambda x: x.get('timestamp', ''), reverse=True)
            last_5_reports = sorted_reports[:5]

            if len(last_5_reports) >= 5:
                low_quality_count = sum(1 for r in last_5_reports if r.get('confidence_score', 1.0) < 0.6)
                if low_quality_count >= 5:
                    return {
                        'is_spam': True,
                        'penalty': -3,
                        'reason': 'Spam detected: Consistent low-quality reporting'
                    }

            return {'is_spam': False, 'penalty': 0, 'reason': ''}

        except Exception as e:
            logger.error(f"Error checking spam pattern: {e}")
            return {'is_spam': False, 'penalty': 0, 'reason': ''}

    def _log_credibility_change(self, user_id: str, old_score: int, new_score: int,
                               delta: int, reason: str):
        """
        Log credibility change to user's history

        Args:
            user_id: Firebase user ID
            old_score: Old credibility score
            new_score: New credibility score
            delta: Change amount
            reason: Reason for change
        """
        try:
            history_ref = db.reference(f'users/{user_id}/credibility_history')
            timestamp = datetime.now(timezone.utc).isoformat()

            history_ref.push({
                'timestamp': timestamp,
                'old_score': old_score,
                'new_score': new_score,
                'delta': delta,
                'reason': reason
            })

        except Exception as e:
            logger.error(f"Error logging credibility change: {e}")

    def _get_confidence_description(self, confidence_score: float) -> str:
        """Get human-readable description of confidence level"""
        if confidence_score >= 0.90:
            return "Exceptional report"
        elif confidence_score >= 0.80:
            return "High confidence report"
        elif confidence_score >= 0.70:
            return "Good confidence report"
        elif confidence_score >= 0.60:
            return "Medium confidence report"
        elif confidence_score >= 0.50:
            return "Neutral report"
        elif confidence_score >= 0.40:
            return "Low confidence report"
        elif confidence_score >= 0.30:
            return "Very low confidence report"
        else:
            return "Extremely low confidence report"

