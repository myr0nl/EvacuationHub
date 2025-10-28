"""
Tests for Time Decay Service

Tests time decay calculations, age categorization, and filtering logic.
"""
import pytest
from datetime import datetime, timedelta, timezone
from services.time_decay import TimeDecayService


class TestTimeDecayCalculations:
    """Test time decay calculations and age categorization"""

    def test_calculate_age_hours_fresh(self):
        """Test age calculation for fresh reports (<1 hour)"""
        # 30 minutes ago
        timestamp = datetime.now(timezone.utc) - timedelta(minutes=30)
        age_hours = TimeDecayService.calculate_age_hours(timestamp.isoformat())

        assert 0.4 <= age_hours <= 0.6  # ~0.5 hours
        assert age_hours >= 0

    def test_calculate_age_hours_recent(self):
        """Test age calculation for recent reports (1-6 hours)"""
        # 3 hours ago
        timestamp = datetime.now(timezone.utc) - timedelta(hours=3)
        age_hours = TimeDecayService.calculate_age_hours(timestamp.isoformat())

        assert 2.9 <= age_hours <= 3.1  # ~3 hours

    def test_calculate_age_hours_old(self):
        """Test age calculation for old reports (6-24 hours)"""
        # 12 hours ago
        timestamp = datetime.now(timezone.utc) - timedelta(hours=12)
        age_hours = TimeDecayService.calculate_age_hours(timestamp.isoformat())

        assert 11.9 <= age_hours <= 12.1  # ~12 hours

    def test_calculate_age_hours_stale(self):
        """Test age calculation for stale reports (24-48 hours)"""
        # 36 hours ago
        timestamp = datetime.now(timezone.utc) - timedelta(hours=36)
        age_hours = TimeDecayService.calculate_age_hours(timestamp.isoformat())

        assert 35.9 <= age_hours <= 36.1  # ~36 hours

    def test_calculate_age_hours_very_stale(self):
        """Test age calculation for very stale reports (>48 hours)"""
        # 72 hours (3 days) ago
        timestamp = datetime.now(timezone.utc) - timedelta(hours=72)
        age_hours = TimeDecayService.calculate_age_hours(timestamp.isoformat())

        assert 71.9 <= age_hours <= 72.1  # ~72 hours

    def test_calculate_age_hours_with_reference_time(self):
        """Test age calculation with explicit reference time"""
        report_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        reference_time = datetime(2025, 1, 15, 13, 30, 0, tzinfo=timezone.utc)

        age_hours = TimeDecayService.calculate_age_hours(
            report_time.isoformat(),
            reference_time
        )

        assert age_hours == 3.5  # Exactly 3.5 hours

    def test_calculate_age_hours_negative_prevented(self):
        """Test that future timestamps return 0 age (not negative)"""
        # 1 hour in the future
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        age_hours = TimeDecayService.calculate_age_hours(future_time.isoformat())

        assert age_hours == 0.0  # Should be clamped to 0

    def test_calculate_age_hours_iso_formats(self):
        """Test various ISO 8601 timestamp formats"""
        base_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        reference_time = datetime(2025, 1, 15, 11, 0, 0, tzinfo=timezone.utc)

        # Format with +00:00
        age1 = TimeDecayService.calculate_age_hours(
            "2025-01-15T10:00:00+00:00",
            reference_time
        )
        assert age1 == 1.0

        # Format with Z
        age2 = TimeDecayService.calculate_age_hours(
            "2025-01-15T10:00:00Z",
            reference_time
        )
        assert age2 == 1.0

        # Format without timezone (assumed UTC)
        age3 = TimeDecayService.calculate_age_hours(
            "2025-01-15T10:00:00",
            reference_time
        )
        assert age3 == 1.0

    def test_calculate_age_hours_invalid_timestamp(self):
        """Test error handling for invalid timestamps"""
        with pytest.raises(ValueError):
            TimeDecayService.calculate_age_hours("not-a-timestamp")

        with pytest.raises(ValueError):
            TimeDecayService.calculate_age_hours("2025-13-99T99:99:99")

        with pytest.raises(ValueError):
            TimeDecayService.calculate_age_hours(None)


class TestAgeCategorization:
    """Test age category assignment"""

    def test_age_category_fresh(self):
        """Test fresh category (<1 hour)"""
        assert TimeDecayService.get_age_category(0.0) == "fresh"
        assert TimeDecayService.get_age_category(0.5) == "fresh"
        assert TimeDecayService.get_age_category(0.99) == "fresh"

    def test_age_category_recent(self):
        """Test recent category (1-6 hours)"""
        assert TimeDecayService.get_age_category(1.0) == "recent"
        assert TimeDecayService.get_age_category(3.0) == "recent"
        assert TimeDecayService.get_age_category(5.99) == "recent"

    def test_age_category_old(self):
        """Test old category (6-24 hours)"""
        assert TimeDecayService.get_age_category(6.0) == "old"
        assert TimeDecayService.get_age_category(12.0) == "old"
        assert TimeDecayService.get_age_category(23.99) == "old"

    def test_age_category_stale(self):
        """Test stale category (24-48 hours)"""
        assert TimeDecayService.get_age_category(24.0) == "stale"
        assert TimeDecayService.get_age_category(36.0) == "stale"
        assert TimeDecayService.get_age_category(47.99) == "stale"

    def test_age_category_very_stale(self):
        """Test very stale category (>48 hours)"""
        assert TimeDecayService.get_age_category(48.0) == "very_stale"
        assert TimeDecayService.get_age_category(72.0) == "very_stale"
        assert TimeDecayService.get_age_category(168.0) == "very_stale"  # 1 week


class TestDecayScores:
    """Test decay score calculations"""

    def test_decay_score_fresh(self):
        """Test fresh decay score (100% opacity)"""
        assert TimeDecayService.get_decay_score(0.0) == 1.0
        assert TimeDecayService.get_decay_score(0.5) == 1.0
        assert TimeDecayService.get_decay_score(0.99) == 1.0

    def test_decay_score_recent(self):
        """Test recent decay score (80% opacity)"""
        assert TimeDecayService.get_decay_score(1.0) == 0.8
        assert TimeDecayService.get_decay_score(3.0) == 0.8
        assert TimeDecayService.get_decay_score(5.99) == 0.8

    def test_decay_score_old(self):
        """Test old decay score (60% opacity)"""
        assert TimeDecayService.get_decay_score(6.0) == 0.6
        assert TimeDecayService.get_decay_score(12.0) == 0.6
        assert TimeDecayService.get_decay_score(23.99) == 0.6

    def test_decay_score_stale(self):
        """Test stale decay score (40% opacity)"""
        assert TimeDecayService.get_decay_score(24.0) == 0.4
        assert TimeDecayService.get_decay_score(36.0) == 0.4
        assert TimeDecayService.get_decay_score(47.99) == 0.4

    def test_decay_score_very_stale(self):
        """Test very stale decay score (20% opacity)"""
        assert TimeDecayService.get_decay_score(48.0) == 0.2
        assert TimeDecayService.get_decay_score(72.0) == 0.2
        assert TimeDecayService.get_decay_score(168.0) == 0.2


class TestCompleteTimeDecay:
    """Test complete time decay calculation"""

    def test_calculate_time_decay_fresh(self):
        """Test complete metadata for fresh report"""
        timestamp = datetime.now(timezone.utc) - timedelta(minutes=30)
        result = TimeDecayService.calculate_time_decay(timestamp.isoformat())

        assert 'age_hours' in result
        assert 'age_category' in result
        assert 'decay_score' in result

        assert 0.4 <= result['age_hours'] <= 0.6
        assert result['age_category'] == 'fresh'
        assert result['decay_score'] == 1.0

    def test_calculate_time_decay_recent(self):
        """Test complete metadata for recent report"""
        timestamp = datetime.now(timezone.utc) - timedelta(hours=3)
        result = TimeDecayService.calculate_time_decay(timestamp.isoformat())

        assert 2.9 <= result['age_hours'] <= 3.1
        assert result['age_category'] == 'recent'
        assert result['decay_score'] == 0.8

    def test_calculate_time_decay_old(self):
        """Test complete metadata for old report"""
        timestamp = datetime.now(timezone.utc) - timedelta(hours=12)
        result = TimeDecayService.calculate_time_decay(timestamp.isoformat())

        assert 11.9 <= result['age_hours'] <= 12.1
        assert result['age_category'] == 'old'
        assert result['decay_score'] == 0.6

    def test_calculate_time_decay_stale(self):
        """Test complete metadata for stale report"""
        timestamp = datetime.now(timezone.utc) - timedelta(hours=36)
        result = TimeDecayService.calculate_time_decay(timestamp.isoformat())

        assert 35.9 <= result['age_hours'] <= 36.1
        assert result['age_category'] == 'stale'
        assert result['decay_score'] == 0.4

    def test_calculate_time_decay_very_stale(self):
        """Test complete metadata for very stale report"""
        timestamp = datetime.now(timezone.utc) - timedelta(hours=72)
        result = TimeDecayService.calculate_time_decay(timestamp.isoformat())

        assert 71.9 <= result['age_hours'] <= 72.1
        assert result['age_category'] == 'very_stale'
        assert result['decay_score'] == 0.2

    def test_calculate_time_decay_invalid_timestamp(self):
        """Test graceful degradation for invalid timestamps"""
        result = TimeDecayService.calculate_time_decay("invalid")

        assert result['age_hours'] is None
        assert result['age_category'] == 'unknown'
        assert result['decay_score'] == 0.5  # Default medium visibility

    def test_calculate_time_decay_rounding(self):
        """Test that age_hours is rounded to 2 decimal places"""
        # 3 hours, 20 minutes, 30 seconds = 3.341666... hours
        timestamp = datetime.now(timezone.utc) - timedelta(hours=3, minutes=20, seconds=30)
        result = TimeDecayService.calculate_time_decay(timestamp.isoformat())

        assert isinstance(result['age_hours'], float)
        # Check it's rounded to 2 decimals (should be ~3.34)
        assert 3.33 <= result['age_hours'] <= 3.35


class TestAgeFiltering:
    """Test age-based filtering logic"""

    def test_should_filter_no_max_age(self):
        """Test that no filtering occurs when max_age_hours is None"""
        assert TimeDecayService.should_filter_by_age(0.5, None) is False
        assert TimeDecayService.should_filter_by_age(100, None) is False

    def test_should_filter_unknown_age(self):
        """Test that reports with unknown age are not filtered"""
        assert TimeDecayService.should_filter_by_age(None, 48) is False

    def test_should_filter_within_threshold(self):
        """Test that reports within threshold are not filtered"""
        assert TimeDecayService.should_filter_by_age(1.0, 48) is False
        assert TimeDecayService.should_filter_by_age(24.0, 48) is False
        assert TimeDecayService.should_filter_by_age(47.99, 48) is False
        assert TimeDecayService.should_filter_by_age(48.0, 48) is False

    def test_should_filter_beyond_threshold(self):
        """Test that reports beyond threshold are filtered"""
        assert TimeDecayService.should_filter_by_age(48.01, 48) is True
        assert TimeDecayService.should_filter_by_age(72.0, 48) is True
        assert TimeDecayService.should_filter_by_age(100.0, 24) is True

    def test_should_filter_exact_threshold(self):
        """Test filtering at exact threshold (should NOT filter)"""
        assert TimeDecayService.should_filter_by_age(24.0, 24) is False
        assert TimeDecayService.should_filter_by_age(48.0, 48) is False

    def test_should_filter_edge_cases(self):
        """Test edge cases for filtering"""
        # Zero age
        assert TimeDecayService.should_filter_by_age(0.0, 48) is False

        # Very small threshold
        assert TimeDecayService.should_filter_by_age(0.1, 0.05) is True
        assert TimeDecayService.should_filter_by_age(0.04, 0.05) is False


class TestCategoryMetadata:
    """Test category metadata retrieval"""

    def test_get_category_metadata_structure(self):
        """Test that category metadata has correct structure"""
        metadata = TimeDecayService.get_category_metadata()

        assert isinstance(metadata, dict)
        assert 'fresh' in metadata
        assert 'recent' in metadata
        assert 'old' in metadata
        assert 'stale' in metadata
        assert 'very_stale' in metadata

    def test_get_category_metadata_fresh(self):
        """Test fresh category metadata"""
        metadata = TimeDecayService.get_category_metadata()['fresh']

        assert metadata['threshold_hours'] == 1.0
        assert metadata['decay_score'] == 1.0
        assert metadata['color'] == 'green'
        assert 'label' in metadata
        assert 'description' in metadata

    def test_get_category_metadata_recent(self):
        """Test recent category metadata"""
        metadata = TimeDecayService.get_category_metadata()['recent']

        assert metadata['threshold_hours'] == 6.0
        assert metadata['decay_score'] == 0.8
        assert metadata['color'] == 'yellow'

    def test_get_category_metadata_old(self):
        """Test old category metadata"""
        metadata = TimeDecayService.get_category_metadata()['old']

        assert metadata['threshold_hours'] == 24.0
        assert metadata['decay_score'] == 0.6
        assert metadata['color'] == 'orange'

    def test_get_category_metadata_stale(self):
        """Test stale category metadata"""
        metadata = TimeDecayService.get_category_metadata()['stale']

        assert metadata['threshold_hours'] == 48.0
        assert metadata['decay_score'] == 0.4
        assert metadata['color'] == 'red'

    def test_get_category_metadata_very_stale(self):
        """Test very stale category metadata"""
        metadata = TimeDecayService.get_category_metadata()['very_stale']

        assert metadata['threshold_hours'] == float('inf')
        assert metadata['decay_score'] == 0.2
        assert metadata['color'] == 'dark_red'


class TestRealWorldScenarios:
    """Test real-world usage scenarios"""

    def test_emergency_timeline_progression(self):
        """Test a report aging through all categories"""
        base_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

        # Just reported (5 minutes ago) - FRESH
        result = TimeDecayService.calculate_time_decay(
            (base_time - timedelta(minutes=5)).isoformat(),
            base_time
        )
        assert result['age_category'] == 'fresh'
        assert result['decay_score'] == 1.0

        # 2 hours old - RECENT
        result = TimeDecayService.calculate_time_decay(
            (base_time - timedelta(hours=2)).isoformat(),
            base_time
        )
        assert result['age_category'] == 'recent'
        assert result['decay_score'] == 0.8

        # 12 hours old - OLD
        result = TimeDecayService.calculate_time_decay(
            (base_time - timedelta(hours=12)).isoformat(),
            base_time
        )
        assert result['age_category'] == 'old'
        assert result['decay_score'] == 0.6

        # 30 hours old - STALE
        result = TimeDecayService.calculate_time_decay(
            (base_time - timedelta(hours=30)).isoformat(),
            base_time
        )
        assert result['age_category'] == 'stale'
        assert result['decay_score'] == 0.4

        # 5 days old - VERY STALE
        result = TimeDecayService.calculate_time_decay(
            (base_time - timedelta(days=5)).isoformat(),
            base_time
        )
        assert result['age_category'] == 'very_stale'
        assert result['decay_score'] == 0.2

    def test_filtering_24_hour_window(self):
        """Test filtering to only show last 24 hours"""
        max_age = 24.0

        # Reports within 24 hours - should NOT filter
        assert TimeDecayService.should_filter_by_age(0.5, max_age) is False
        assert TimeDecayService.should_filter_by_age(12.0, max_age) is False
        assert TimeDecayService.should_filter_by_age(23.99, max_age) is False

        # Reports beyond 24 hours - should filter
        assert TimeDecayService.should_filter_by_age(24.01, max_age) is True
        assert TimeDecayService.should_filter_by_age(48.0, max_age) is True
        assert TimeDecayService.should_filter_by_age(120.0, max_age) is True

    def test_filtering_48_hour_window(self):
        """Test filtering to only show last 48 hours (2 days)"""
        max_age = 48.0

        # Reports within 48 hours - should NOT filter
        assert TimeDecayService.should_filter_by_age(1.0, max_age) is False
        assert TimeDecayService.should_filter_by_age(24.0, max_age) is False
        assert TimeDecayService.should_filter_by_age(47.99, max_age) is False

        # Reports beyond 48 hours - should filter
        assert TimeDecayService.should_filter_by_age(48.01, max_age) is True
        assert TimeDecayService.should_filter_by_age(72.0, max_age) is True

    def test_timezone_aware_consistency(self):
        """Test that timezone-aware calculations are consistent"""
        # Same instant in different timezones should give same age
        base_utc = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        reference = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        age1 = TimeDecayService.calculate_age_hours(
            base_utc.isoformat(),
            reference
        )

        # Naive timestamp (assumed UTC)
        age2 = TimeDecayService.calculate_age_hours(
            "2025-01-15T10:00:00",
            reference
        )

        assert age1 == age2 == 2.0
