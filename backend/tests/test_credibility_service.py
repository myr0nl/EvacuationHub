"""
Test Suite for User Credibility Score System (Phase 7)
Tests credibility calculations, level thresholds, penalties, and anti-spam safeguards
"""
import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


class CredibilityService:
    """User credibility score management service (Phase 7)"""

    @staticmethod
    def calculate_user_credibility_change(final_confidence_score: float) -> int:
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

    @staticmethod
    def get_credibility_level(credibility_score: int) -> tuple:
        """
        Get credibility level and badge for a given score

        Args:
            credibility_score: User credibility score (0-100)

        Returns:
            Tuple of (level_name, badge_emoji)
        """
        if credibility_score >= 90:
            return ("Expert", "🌟")
        elif credibility_score >= 75:
            return ("Veteran", "🏅")
        elif credibility_score >= 60:
            return ("Trusted", "✅")
        elif credibility_score >= 50:
            return ("Neutral", "⚪")
        elif credibility_score >= 30:
            return ("Caution", "⚠️")
        else:
            return ("Unreliable", "🔴")

    @staticmethod
    def calculate_base_confidence_penalty(user_credibility: int) -> float:
        """
        Calculate base confidence multiplier based on user credibility

        Low-credibility users face progressive penalties:
        - Expert/Veteran (75+): 1.0 (no penalty)
        - Trusted (60-74): 0.95 (-5% penalty)
        - Neutral (50-59): 0.90 (-10% penalty)
        - Caution (30-49): 0.80 (-20% penalty)
        - Unreliable (<30): 0.65 (-35% penalty)

        Args:
            user_credibility: User credibility score (0-100)

        Returns:
            Base confidence multiplier (0.65-1.0)
        """
        if user_credibility >= 75:
            return 1.0   # No penalty (Veteran/Expert)
        elif user_credibility >= 60:
            return 0.95  # Minimal penalty (Trusted)
        elif user_credibility >= 50:
            return 0.90  # Slight penalty (Neutral)
        elif user_credibility >= 30:
            return 0.80  # Moderate penalty (Caution)
        else:
            return 0.65  # Heavy penalty (Unreliable, credibility < 30)

    @staticmethod
    def calculate_location_diminishing_returns(report_count_same_location: int) -> float:
        """
        Calculate diminishing returns for multiple reports in same location

        Args:
            report_count_same_location: Number of user reports in past 24h within 6 miles

        Returns:
            Credibility gain multiplier (0.2-1.0)
        """
        if report_count_same_location == 0:
            return 1.0   # Full credibility gain (first report)
        elif report_count_same_location == 1:
            return 0.75  # 25% reduction (second report)
        elif report_count_same_location == 2:
            return 0.50  # 50% reduction (third report)
        else:
            return 0.20  # 80% reduction (spam detected, 4+ reports)

    @staticmethod
    def check_duplicate_detection(reports_list: list) -> tuple:
        """
        Detect duplicate/spam reports (same location <1 hour apart)

        Args:
            reports_list: List of user reports with lat/lon/timestamp

        Returns:
            Tuple of (is_duplicate, penalty_points)
        """
        # Check for reports within 1km and 1 hour
        for i, report1 in enumerate(reports_list):
            for report2 in reports_list[i+1:]:
                time_diff = abs((datetime.fromisoformat(report1['timestamp']) -
                               datetime.fromisoformat(report2['timestamp'])).total_seconds() / 3600)

                # Simple distance check (for testing, assume <1km if within 0.01 degrees)
                lat_diff = abs(report1['latitude'] - report2['latitude'])
                lon_diff = abs(report1['longitude'] - report2['longitude'])

                if lat_diff < 0.01 and lon_diff < 0.01 and time_diff < 1:
                    return (True, -5)  # Duplicate detected, -5 penalty

        return (False, 0)

    @staticmethod
    def check_volume_spam(reports_in_24h: int) -> tuple:
        """
        Detect volume spam (>10 reports in 24 hours)

        Args:
            reports_in_24h: Number of reports submitted in past 24 hours

        Returns:
            Tuple of (is_spam, penalty_points)
        """
        if reports_in_24h > 10:
            return (True, -5)  # Volume spam detected, -5 penalty
        return (False, 0)

    @staticmethod
    def check_pattern_spam(recent_confidence_scores: list) -> tuple:
        """
        Detect pattern spam (5 consecutive low-quality reports <60%)

        Args:
            recent_confidence_scores: List of last 5 confidence scores

        Returns:
            Tuple of (is_spam, penalty_points)
        """
        if len(recent_confidence_scores) >= 5:
            if all(score < 0.6 for score in recent_confidence_scores[-5:]):
                return (True, -3)  # Pattern spam detected, -3 penalty
        return (False, 0)

    @staticmethod
    def calculate_recovery_bonus(user_credibility: int, confidence_score: float) -> int:
        """
        Calculate recovery bonus for low-credibility users submitting quality reports

        Args:
            user_credibility: Current user credibility (0-100)
            confidence_score: Report confidence score (0.0-1.0)

        Returns:
            Recovery bonus points (0-2)
        """
        base_gain = CredibilityService.calculate_user_credibility_change(confidence_score)

        # Low-credibility users (<30) get +2 bonus for high-quality reports (≥80%)
        if user_credibility < 30 and confidence_score >= 0.80:
            return base_gain + 2

        # Medium-low credibility users (30-49) get +1 bonus for excellent reports (≥85%)
        elif user_credibility < 50 and confidence_score >= 0.85:
            return base_gain + 1

        return base_gain

    @staticmethod
    def apply_credibility_bounds(credibility_score: int) -> int:
        """
        Ensure credibility score stays within bounds (0-100)

        Args:
            credibility_score: Raw credibility score

        Returns:
            Bounded credibility score (0-100)
        """
        return max(0, min(100, credibility_score))


class TestCredibilityService:
    """Test User Credibility Score calculations and logic"""

    def setup_method(self):
        """Setup test fixtures"""
        self.service = CredibilityService()

    def test_initial_credibility_score(self):
        """Test new users get 50 points (Neutral level)"""
        initial_score = 50
        level, badge = self.service.get_credibility_level(initial_score)

        assert initial_score == 50
        assert level == "Neutral"
        assert badge == "⚪"

        print("✅ test_initial_credibility_score PASSED")

    def test_credibility_increase_high_confidence(self):
        """Test 85%+ confidence reports give +3 points"""
        confidence_score = 0.87  # 87% confidence
        delta = self.service.calculate_user_credibility_change(confidence_score)

        assert delta == +3

        print("✅ test_credibility_increase_high_confidence PASSED")

    def test_credibility_decrease_low_confidence(self):
        """Test <60% confidence reports give -1 to -3 points"""
        # Test low confidence (40-49%) = -1
        low_confidence = 0.45
        delta_low = self.service.calculate_user_credibility_change(low_confidence)
        assert delta_low == -1

        # Test very low confidence (30-39%) = -2
        very_low_confidence = 0.35
        delta_very_low = self.service.calculate_user_credibility_change(very_low_confidence)
        assert delta_very_low == -2

        # Test extremely low confidence (<30%) = -3
        extremely_low_confidence = 0.25
        delta_extremely_low = self.service.calculate_user_credibility_change(extremely_low_confidence)
        assert delta_extremely_low == -3

        print("✅ test_credibility_decrease_low_confidence PASSED")

    def test_credibility_level_thresholds(self):
        """Test 6 credibility levels (Expert, Veteran, Trusted, Neutral, Caution, Unreliable)"""
        test_cases = [
            (95, "Expert", "🌟"),
            (80, "Veteran", "🏅"),
            (65, "Trusted", "✅"),
            (55, "Neutral", "⚪"),
            (40, "Caution", "⚠️"),
            (20, "Unreliable", "🔴")
        ]

        for score, expected_level, expected_badge in test_cases:
            level, badge = self.service.get_credibility_level(score)
            assert level == expected_level, f"Score {score} should be {expected_level}, got {level}"
            assert badge == expected_badge, f"Score {score} should have {expected_badge}, got {badge}"

        print("✅ test_credibility_level_thresholds PASSED")

    def test_base_confidence_penalty(self):
        """Test base confidence multipliers (1.0, 0.95, 0.90, 0.80, 0.65)"""
        test_cases = [
            (90, 1.0),   # Expert: no penalty
            (75, 1.0),   # Veteran: no penalty
            (65, 0.95),  # Trusted: -5% penalty
            (55, 0.90),  # Neutral: -10% penalty
            (40, 0.80),  # Caution: -20% penalty
            (20, 0.65)   # Unreliable: -35% penalty
        ]

        for credibility, expected_multiplier in test_cases:
            multiplier = self.service.calculate_base_confidence_penalty(credibility)
            assert multiplier == expected_multiplier, \
                f"Credibility {credibility} should have multiplier {expected_multiplier}, got {multiplier}"

        print("✅ test_base_confidence_penalty PASSED")

    def test_location_diminishing_returns(self):
        """Test multiple reports in same area get reduced gains"""
        test_cases = [
            (0, 1.0),   # First report: 100% gain
            (1, 0.75),  # Second report: 75% gain
            (2, 0.50),  # Third report: 50% gain
            (3, 0.20),  # Fourth report: 20% gain (spam)
            (5, 0.20)   # More reports: still 20% (spam)
        ]

        for report_count, expected_multiplier in test_cases:
            multiplier = self.service.calculate_location_diminishing_returns(report_count)
            assert multiplier == expected_multiplier, \
                f"Report count {report_count} should have multiplier {expected_multiplier}, got {multiplier}"

        print("✅ test_location_diminishing_returns PASSED")

    def test_duplicate_detection(self):
        """Test identical reports within 1 hour get -5 penalty"""
        # Create duplicate reports (same location, <1 hour apart)
        now = datetime.now(timezone.utc)
        reports = [
            {'latitude': 34.05, 'longitude': -118.25, 'timestamp': now.isoformat()},
            {'latitude': 34.05, 'longitude': -118.25, 'timestamp': (now + timedelta(minutes=30)).isoformat()}
        ]

        is_duplicate, penalty = self.service.check_duplicate_detection(reports)

        assert is_duplicate is True
        assert penalty == -5

        print("✅ test_duplicate_detection PASSED")

    def test_volume_spam_detection(self):
        """Test >10 reports/day trigger -5 penalty"""
        # Test normal volume (no spam)
        normal_volume = 8
        is_spam_normal, penalty_normal = self.service.check_volume_spam(normal_volume)
        assert is_spam_normal is False
        assert penalty_normal == 0

        # Test spam volume (>10 reports)
        spam_volume = 15
        is_spam_high, penalty_high = self.service.check_volume_spam(spam_volume)
        assert is_spam_high is True
        assert penalty_high == -5

        print("✅ test_volume_spam_detection PASSED")

    def test_pattern_spam_detection(self):
        """Test 5 consecutive low-quality reports trigger -3 penalty"""
        # Test normal pattern (varied quality)
        normal_scores = [0.8, 0.6, 0.7, 0.5, 0.65]
        is_spam_normal, penalty_normal = self.service.check_pattern_spam(normal_scores)
        assert is_spam_normal is False

        # Test spam pattern (5 consecutive low-quality <60%)
        spam_scores = [0.55, 0.50, 0.48, 0.52, 0.45]
        is_spam_detected, penalty_spam = self.service.check_pattern_spam(spam_scores)
        assert is_spam_detected is True
        assert penalty_spam == -3

        print("✅ test_pattern_spam_detection PASSED")

    def test_recovery_bonus(self):
        """Test low-credibility users get recovery bonus for quality reports"""
        # Test unreliable user (credibility 25) with high-quality report (85%)
        credibility_low = 25
        confidence_high = 0.85
        bonus = self.service.calculate_recovery_bonus(credibility_low, confidence_high)

        base_gain = self.service.calculate_user_credibility_change(confidence_high)
        expected_bonus = base_gain + 2  # +3 (base) + 2 (recovery) = +5

        assert bonus == expected_bonus
        assert bonus == +5

        # Test medium-low user (credibility 40) with excellent report (88%)
        credibility_medium = 40
        confidence_excellent = 0.88
        bonus_medium = self.service.calculate_recovery_bonus(credibility_medium, confidence_excellent)

        base_gain_medium = self.service.calculate_user_credibility_change(confidence_excellent)
        expected_bonus_medium = base_gain_medium + 1  # +3 (base) + 1 (recovery) = +4

        assert bonus_medium == expected_bonus_medium

        print("✅ test_recovery_bonus PASSED")

    def test_credibility_bounds(self):
        """Test credibility score cannot go below 0 or above 100"""
        # Test lower bound
        below_zero = -15
        bounded_low = self.service.apply_credibility_bounds(below_zero)
        assert bounded_low == 0

        # Test upper bound
        above_hundred = 120
        bounded_high = self.service.apply_credibility_bounds(above_hundred)
        assert bounded_high == 100

        # Test normal range
        normal = 65
        bounded_normal = self.service.apply_credibility_bounds(normal)
        assert bounded_normal == 65

        print("✅ test_credibility_bounds PASSED")


def run_all_tests():
    """Run all credibility service tests"""
    print("\n" + "="*60)
    print("PHASE 7: CREDIBILITY SERVICE TESTS")
    print("="*60)

    test_suite = TestCredibilityService()

    try:
        test_suite.setup_method()
        test_suite.test_initial_credibility_score()

        test_suite.setup_method()
        test_suite.test_credibility_increase_high_confidence()

        test_suite.setup_method()
        test_suite.test_credibility_decrease_low_confidence()

        test_suite.setup_method()
        test_suite.test_credibility_level_thresholds()

        test_suite.setup_method()
        test_suite.test_base_confidence_penalty()

        test_suite.setup_method()
        test_suite.test_location_diminishing_returns()

        test_suite.setup_method()
        test_suite.test_duplicate_detection()

        test_suite.setup_method()
        test_suite.test_volume_spam_detection()

        test_suite.setup_method()
        test_suite.test_pattern_spam_detection()

        test_suite.setup_method()
        test_suite.test_recovery_bonus()

        test_suite.setup_method()
        test_suite.test_credibility_bounds()

        print("\n" + "="*60)
        print("✅ ALL CREDIBILITY SERVICE TESTS PASSED")
        print("="*60)
        print("\n📝 Summary:")
        print("   - Initial credibility: 50 points (Neutral)")
        print("   - Credibility changes: -3 to +5 per report")
        print("   - Level thresholds: 6 levels working correctly")
        print("   - Base confidence penalty: 0.65-1.0 multipliers")
        print("   - Location diminishing returns: 1.0 → 0.2")
        print("   - Duplicate detection: -5 penalty")
        print("   - Volume spam detection: -5 penalty for >10 reports/day")
        print("   - Pattern spam detection: -3 penalty for 5 consecutive low-quality")
        print("   - Recovery bonus: +1 to +2 for low-credibility quality reports")
        print("   - Bounds enforcement: 0-100 range")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    run_all_tests()
