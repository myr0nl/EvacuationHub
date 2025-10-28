"""
Time Decay Service for Disaster Reports

Calculates time decay scores and age categories for reports based on their timestamps.
Used for visual opacity/priority filtering in the frontend.
"""
from datetime import datetime, timezone
from typing import Dict, Optional, Literal

# Age category type definition
AgeCategory = Literal["fresh", "recent", "old", "stale", "very_stale"]


class TimeDecayService:
    """
    Service for calculating time-based decay scores for disaster reports.

    Time decay helps prioritize recent reports while still showing older context.
    Disasters evolve over time, so decay is gradual rather than abrupt.
    """

    # Age thresholds in hours
    FRESH_THRESHOLD = 1.0      # <1 hour: Fresh reports
    RECENT_THRESHOLD = 6.0     # 1-6 hours: Recent reports
    OLD_THRESHOLD = 24.0       # 6-24 hours: Old reports
    STALE_THRESHOLD = 48.0     # 24-48 hours: Stale reports
    # >48 hours: Very stale reports

    # Decay scores for opacity visualization (0.0-1.0)
    FRESH_SCORE = 1.0          # 100% opacity - bright green
    RECENT_SCORE = 0.8         # 80% opacity - yellow
    OLD_SCORE = 0.6            # 60% opacity - orange
    STALE_SCORE = 0.4          # 40% opacity - red
    VERY_STALE_SCORE = 0.2     # 20% opacity - faded red

    @staticmethod
    def calculate_age_hours(timestamp: str, reference_time: Optional[datetime] = None) -> float:
        """
        Calculate age in hours from timestamp to reference time (or now).

        Args:
            timestamp: ISO 8601 timestamp string (e.g., "2025-01-15T10:30:00+00:00")
            reference_time: Optional reference datetime (defaults to current UTC time)

        Returns:
            Age in hours as float

        Raises:
            ValueError: If timestamp is invalid or cannot be parsed
        """
        try:
            # Parse timestamp - handle both timezone-aware and naive timestamps
            if isinstance(timestamp, str):
                report_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            elif isinstance(timestamp, datetime):
                report_time = timestamp
            else:
                raise ValueError(f"Invalid timestamp type: {type(timestamp)}")

            # Ensure timezone-aware datetime
            if report_time.tzinfo is None:
                report_time = report_time.replace(tzinfo=timezone.utc)

            # Use provided reference time or current UTC time
            if reference_time is None:
                reference_time = datetime.now(timezone.utc)
            elif reference_time.tzinfo is None:
                reference_time = reference_time.replace(tzinfo=timezone.utc)

            # Calculate age
            age_delta = reference_time - report_time
            age_hours = age_delta.total_seconds() / 3600.0

            # Prevent negative ages (future timestamps)
            return max(0.0, age_hours)

        except (ValueError, AttributeError, TypeError) as e:
            raise ValueError(f"Failed to parse timestamp '{timestamp}': {e}")

    @staticmethod
    def get_age_category(age_hours: float) -> AgeCategory:
        """
        Determine age category based on hours elapsed.

        Args:
            age_hours: Age in hours

        Returns:
            Age category string
        """
        if age_hours < TimeDecayService.FRESH_THRESHOLD:
            return "fresh"
        elif age_hours < TimeDecayService.RECENT_THRESHOLD:
            return "recent"
        elif age_hours < TimeDecayService.OLD_THRESHOLD:
            return "old"
        elif age_hours < TimeDecayService.STALE_THRESHOLD:
            return "stale"
        else:
            return "very_stale"

    @staticmethod
    def get_decay_score(age_hours: float) -> float:
        """
        Calculate decay score for visual opacity (0.0-1.0).

        Args:
            age_hours: Age in hours

        Returns:
            Decay score between 0.0 and 1.0
        """
        if age_hours < TimeDecayService.FRESH_THRESHOLD:
            return TimeDecayService.FRESH_SCORE
        elif age_hours < TimeDecayService.RECENT_THRESHOLD:
            return TimeDecayService.RECENT_SCORE
        elif age_hours < TimeDecayService.OLD_THRESHOLD:
            return TimeDecayService.OLD_SCORE
        elif age_hours < TimeDecayService.STALE_THRESHOLD:
            return TimeDecayService.STALE_SCORE
        else:
            return TimeDecayService.VERY_STALE_SCORE

    @staticmethod
    def calculate_time_decay(timestamp: str, reference_time: Optional[datetime] = None) -> Dict:
        """
        Calculate complete time decay metadata for a report.

        Args:
            timestamp: ISO 8601 timestamp string
            reference_time: Optional reference datetime (defaults to current UTC time)

        Returns:
            Dictionary with time decay metadata:
            {
                'age_hours': float,
                'age_category': str,
                'decay_score': float
            }

        Example:
            >>> TimeDecayService.calculate_time_decay("2025-01-15T10:00:00+00:00")
            {
                'age_hours': 0.5,
                'age_category': 'fresh',
                'decay_score': 1.0
            }
        """
        try:
            age_hours = TimeDecayService.calculate_age_hours(timestamp, reference_time)
            age_category = TimeDecayService.get_age_category(age_hours)
            decay_score = TimeDecayService.get_decay_score(age_hours)

            return {
                'age_hours': round(age_hours, 2),
                'age_category': age_category,
                'decay_score': decay_score
            }
        except ValueError:
            # Graceful degradation for missing/invalid timestamps
            return {
                'age_hours': None,
                'age_category': 'unknown',
                'decay_score': 0.5  # Default medium visibility
            }

    @staticmethod
    def should_filter_by_age(age_hours: Optional[float], max_age_hours: Optional[float]) -> bool:
        """
        Determine if a report should be filtered out based on age.

        Args:
            age_hours: Age of the report in hours (None if unknown)
            max_age_hours: Maximum age threshold in hours (None for no filtering)

        Returns:
            True if report should be filtered out, False otherwise
        """
        # No filtering if max_age_hours not specified
        if max_age_hours is None:
            return False

        # Don't filter reports with unknown age (keep them visible)
        if age_hours is None:
            return False

        # Filter if age exceeds threshold
        return age_hours > max_age_hours

    @staticmethod
    def get_category_metadata() -> Dict:
        """
        Get metadata about all age categories for frontend display.

        Returns:
            Dictionary mapping categories to their properties
        """
        return {
            'fresh': {
                'threshold_hours': TimeDecayService.FRESH_THRESHOLD,
                'decay_score': TimeDecayService.FRESH_SCORE,
                'color': 'green',
                'label': 'Fresh (<1h)',
                'description': 'Very recent reports requiring immediate attention'
            },
            'recent': {
                'threshold_hours': TimeDecayService.RECENT_THRESHOLD,
                'decay_score': TimeDecayService.RECENT_SCORE,
                'color': 'yellow',
                'label': 'Recent (1-6h)',
                'description': 'Recent reports still highly relevant'
            },
            'old': {
                'threshold_hours': TimeDecayService.OLD_THRESHOLD,
                'decay_score': TimeDecayService.OLD_SCORE,
                'color': 'orange',
                'label': 'Old (6-24h)',
                'description': 'Older reports providing context'
            },
            'stale': {
                'threshold_hours': TimeDecayService.STALE_THRESHOLD,
                'decay_score': TimeDecayService.STALE_SCORE,
                'color': 'red',
                'label': 'Stale (24-48h)',
                'description': 'Stale reports, situation may have changed'
            },
            'very_stale': {
                'threshold_hours': float('inf'),
                'decay_score': TimeDecayService.VERY_STALE_SCORE,
                'color': 'dark_red',
                'label': 'Very Stale (>48h)',
                'description': 'Very old reports, mostly historical'
            }
        }
