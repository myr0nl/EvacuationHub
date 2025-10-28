"""
Unit tests for official source confidence scoring (Phase 1)
Tests NASA FIRMS and NOAA confidence scoring with simplified logic
"""
import pytest
from datetime import datetime, timezone, timedelta
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.confidence_scorer import ConfidenceScorer


class TestOfficialSourceConfidenceScoring:
    """Test suite for official source confidence scoring"""

    def setup_method(self):
        """Setup test fixtures"""
        self.scorer = ConfidenceScorer()

    def test_nasa_firms_base_score(self):
        """Test that NASA FIRMS wildfires get 92% base score"""
        wildfire = {
            'source': 'nasa_firms',
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'brightness': 330,
            'frp': 30,
            'confidence': 'h',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        result = self.scorer.calculate_confidence(wildfire)

        assert result['confidence_level'] == 'High'
        assert result['confidence_score'] >= 0.90
        assert 'source_credibility' in result['breakdown']
        assert result['breakdown']['source_credibility'] == 0.92

    def test_noaa_base_score(self):
        """Test that NOAA alerts get 90% base score"""
        alert = {
            'source': 'noaa',
            'type': 'weather_alert',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'severity': 'moderate',
            'urgency': 'expected',
            'certainty': 'likely',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        result = self.scorer.calculate_confidence(alert)

        assert result['confidence_level'] == 'High'
        assert result['confidence_score'] >= 0.90
        assert 'source_credibility' in result['breakdown']
        assert result['breakdown']['source_credibility'] == 0.90

    def test_recency_bonus_within_1_hour(self):
        """Test +5% recency bonus for data within 1 hour"""
        now = datetime.now(timezone.utc)
        wildfire = {
            'source': 'nasa_firms',
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'brightness': 330,
            'frp': 30,
            'timestamp': now.isoformat()
        }

        result = self.scorer.calculate_confidence(wildfire)

        assert 'recency_bonus' in result['breakdown']
        assert result['breakdown']['recency_bonus'] == 0.05
        # Base (0.92) + recency (0.05) = 0.97 (before other bonuses)
        assert result['confidence_score'] >= 0.95

    def test_recency_bonus_within_6_hours(self):
        """Test +3% recency bonus for data within 6 hours"""
        three_hours_ago = datetime.now(timezone.utc) - timedelta(hours=3)
        wildfire = {
            'source': 'nasa_firms',
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'brightness': 320,
            'frp': 15,
            'timestamp': three_hours_ago.isoformat()
        }

        result = self.scorer.calculate_confidence(wildfire)

        assert 'recency_bonus' in result['breakdown']
        assert result['breakdown']['recency_bonus'] == 0.03

    def test_recency_bonus_within_24_hours(self):
        """Test +1% recency bonus for data within 24 hours"""
        twelve_hours_ago = datetime.now(timezone.utc) - timedelta(hours=12)
        alert = {
            'source': 'noaa',
            'type': 'weather_alert',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'severity': 'minor',
            'timestamp': twelve_hours_ago.isoformat()
        }

        result = self.scorer.calculate_confidence(alert)

        assert 'recency_bonus' in result['breakdown']
        assert result['breakdown']['recency_bonus'] == 0.01

    def test_no_recency_bonus_old_data(self):
        """Test no recency bonus for data older than 24 hours"""
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        wildfire = {
            'source': 'nasa_firms',
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'brightness': 320,
            'frp': 15,
            'timestamp': two_days_ago.isoformat()
        }

        result = self.scorer.calculate_confidence(wildfire)

        # Recency bonus should be 0 for old data
        assert result['breakdown'].get('recency_bonus', 0) == 0

    def test_completeness_bonus_all_fields_nasa(self):
        """Test +3% completeness bonus for NASA FIRMS with all fields"""
        wildfire = {
            'source': 'nasa_firms',
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'brightness': 350,
            'frp': 60,
            'confidence': 'h',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        result = self.scorer.calculate_confidence(wildfire)

        assert 'completeness_bonus' in result['breakdown']
        assert result['breakdown']['completeness_bonus'] == 0.03

    def test_completeness_bonus_partial_fields_nasa(self):
        """Test partial completeness bonus for NASA FIRMS with some missing fields"""
        wildfire = {
            'source': 'nasa_firms',
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'brightness': 350,
            # Missing frp and confidence
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        result = self.scorer.calculate_confidence(wildfire)

        assert 'completeness_bonus' in result['breakdown']
        # 3 out of 5 fields = 60% of 0.03 = 0.018
        assert 0.015 <= result['breakdown']['completeness_bonus'] <= 0.02

    def test_completeness_bonus_all_fields_noaa(self):
        """Test +3% completeness bonus for NOAA with all fields"""
        alert = {
            'source': 'noaa',
            'type': 'weather_alert',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'severity': 'severe',
            'urgency': 'immediate',
            'certainty': 'observed',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        result = self.scorer.calculate_confidence(alert)

        assert 'completeness_bonus' in result['breakdown']
        assert result['breakdown']['completeness_bonus'] == 0.03

    def test_intensity_bonus_critical_wildfire(self):
        """Test +2% intensity bonus for critical wildfire"""
        wildfire = {
            'source': 'nasa_firms',
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'brightness': 370,  # > 360 = critical
            'frp': 120,  # > 100 = critical
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        result = self.scorer.calculate_confidence(wildfire)

        assert 'intensity_bonus' in result['breakdown']
        assert result['breakdown']['intensity_bonus'] == 0.02

    def test_intensity_bonus_high_wildfire(self):
        """Test +1.5% intensity bonus for high severity wildfire"""
        wildfire = {
            'source': 'nasa_firms',
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'brightness': 350,  # > 340 = high
            'frp': 60,  # > 50 = high
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        result = self.scorer.calculate_confidence(wildfire)

        assert 'intensity_bonus' in result['breakdown']
        assert result['breakdown']['intensity_bonus'] == 0.015

    def test_intensity_bonus_extreme_weather(self):
        """Test +2% intensity bonus for extreme weather alert"""
        alert = {
            'source': 'noaa',
            'type': 'weather_alert',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'severity': 'extreme',
            'urgency': 'immediate',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        result = self.scorer.calculate_confidence(alert)

        assert 'intensity_bonus' in result['breakdown']
        assert result['breakdown']['intensity_bonus'] == 0.02

    def test_intensity_bonus_severe_weather(self):
        """Test +1.5% intensity bonus for severe weather alert"""
        alert = {
            'source': 'noaa',
            'type': 'weather_alert',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'severity': 'severe',
            'urgency': 'expected',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        result = self.scorer.calculate_confidence(alert)

        assert 'intensity_bonus' in result['breakdown']
        assert result['breakdown']['intensity_bonus'] == 0.015

    def test_max_confidence_capped_at_100(self):
        """Test that confidence is capped at 1.0 (100%)"""
        # Create perfect conditions: base + all bonuses
        wildfire = {
            'source': 'nasa_firms',
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'brightness': 370,  # +2% intensity
            'frp': 120,
            'confidence': 'h',
            'timestamp': datetime.now(timezone.utc).isoformat()  # +5% recency
        }

        result = self.scorer.calculate_confidence(wildfire)

        # Even with all bonuses, should not exceed 1.0
        assert result['confidence_score'] <= 1.0
        assert result['confidence_level'] == 'High'

    def test_official_source_always_high_confidence(self):
        """Test that official sources always get 'High' confidence level"""
        # Test with minimal data
        minimal_wildfire = {
            'source': 'nasa_firms',
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'timestamp': (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        }

        result = self.scorer.calculate_confidence(minimal_wildfire)

        assert result['confidence_level'] == 'High'
        assert result['confidence_score'] >= 0.90

    def test_official_source_no_ai_enhancement(self):
        """Test that official sources do not trigger AI enhancement"""
        wildfire = {
            'source': 'nasa_firms',
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'brightness': 330,
            'frp': 30,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'description': 'This should NOT trigger AI analysis'
        }

        result = self.scorer.calculate_confidence(wildfire)

        # Should not have AI enhancement in breakdown
        assert 'ai_enhancement' not in result['breakdown']
        assert result['confidence_level'] == 'High'

    def test_score_range_90_to_100_percent(self):
        """Test that all official sources score between 90-100%"""
        test_cases = [
            {
                'source': 'nasa_firms',
                'type': 'wildfire',
                'latitude': 37.7749,
                'longitude': -122.4194,
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            {
                'source': 'noaa',
                'type': 'weather_alert',
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        ]

        for test_case in test_cases:
            result = self.scorer.calculate_confidence(test_case)
            assert 0.90 <= result['confidence_score'] <= 1.0, \
                f"Source {test_case['source']} scored {result['confidence_score']}, expected 0.90-1.0"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
