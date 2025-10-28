#!/usr/bin/env python3
"""
Comprehensive test suite for spatial corroboration feature

Tests the enhanced confidence scoring with nearby reports from:
- User-submitted reports
- NASA FIRMS wildfire data
- NOAA weather alerts

Verifies:
- Distance calculations (haversine formula)
- Source credibility weighting (official vs user)
- Severity matching logic
- Temporal filtering (24-hour window)
- Boost calculation correctness
"""

import sys
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List

# Add parent directory to path to import services
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.confidence_scorer import ConfidenceScorer

class TestSpatialCorroboration:
    def __init__(self):
        self.scorer = ConfidenceScorer()
        self.test_results = []

    def log(self, message: str, success: bool = True):
        """Log test results"""
        status = "✅" if success else "❌"
        print(f"{status} {message}")
        self.test_results.append({'message': message, 'success': success})

    def test_distance_calculation(self):
        """Test haversine distance calculations"""
        print("\n🧪 Testing Distance Calculations")
        print("=" * 60)

        # San Francisco to Los Angeles (approx 559km)
        sf_lat, sf_lon = 37.7749, -122.4194
        la_lat, la_lon = 34.0522, -118.2437

        distance = self.scorer._haversine_distance(sf_lat, sf_lon, la_lat, la_lon)
        expected = 559  # Known distance in km
        tolerance = 10  # Allow 6 miles tolerance

        if abs(distance - expected) <= tolerance:
            self.log(f"SF to LA distance: {distance:.1f}km (expected ~{expected}km)")
        else:
            self.log(f"SF to LA distance: {distance:.1f}km (expected ~{expected}km)", False)

        # Same location (should be 0)
        same_dist = self.scorer._haversine_distance(sf_lat, sf_lon, sf_lat, sf_lon)
        if same_dist < 0.01:
            self.log(f"Same location distance: {same_dist:.4f}km (expected ~0km)")
        else:
            self.log(f"Same location distance: {same_dist:.4f}km (expected ~0km)", False)

        # Short distance (~5km)
        nearby_lat, nearby_lon = 37.8044, -122.4708  # Oakland
        short_dist = self.scorer._haversine_distance(sf_lat, sf_lon, nearby_lat, nearby_lon)
        if 5 <= short_dist <= 7:
            self.log(f"SF to Oakland distance: {short_dist:.1f}km (expected ~5-7km)")
        else:
            self.log(f"SF to Oakland distance: {short_dist:.1f}km (expected ~5-7km)", False)

    def test_severity_adjacent(self):
        """Test severity adjacency detection"""
        print("\n🧪 Testing Severity Adjacency")
        print("=" * 60)

        test_cases = [
            ('low', 'medium', True, "low-medium adjacent"),
            ('medium', 'high', True, "medium-high adjacent"),
            ('high', 'critical', True, "high-critical adjacent"),
            ('low', 'high', False, "low-high not adjacent"),
            ('low', 'critical', False, "low-critical not adjacent"),
            ('medium', 'medium', False, "same severity not adjacent"),
        ]

        for sev1, sev2, expected, description in test_cases:
            result = self.scorer._severity_adjacent(sev1, sev2)
            if result == expected:
                self.log(f"{description}: {result} (expected {expected})")
            else:
                self.log(f"{description}: {result} (expected {expected})", False)

    def test_no_nearby_reports(self):
        """Test with no nearby reports (should return minimal boost)"""
        print("\n🧪 Testing No Nearby Reports")
        print("=" * 60)

        report = {
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'severity': 'high',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        boost, breakdown = self.scorer._calculate_corroboration(report, [])

        if boost == 0.0:
            self.log(f"No nearby reports boost: {boost*100}% (expected 0%)")
        else:
            self.log(f"No nearby reports boost: {boost*100}% (expected 0%)", False)

        if breakdown['nearby_count'] == 0:
            self.log(f"Nearby count: {breakdown['nearby_count']} (expected 0)")
        else:
            self.log(f"Nearby count: {breakdown['nearby_count']} (expected 0)", False)

    def test_single_user_report_nearby(self):
        """Test with single nearby user report (same type, ~5km away)"""
        print("\n🧪 Testing Single User Report Nearby")
        print("=" * 60)

        now = datetime.now(timezone.utc).isoformat()

        report = {
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'severity': 'high',
            'timestamp': now
        }

        nearby = [{
            'id': 'report_123',
            'type': 'wildfire',
            'latitude': 37.7800,  # ~5km away
            'longitude': -122.4100,
            'severity': 'high',
            'source': 'user_report',
            'timestamp': now
        }]

        boost, breakdown = self.scorer._calculate_corroboration(report, nearby)

        # Expected: distance_score ~1.0 (within 6 miles) × source_weight 1.0 (user) × severity 1.2 (exact) = 1.2
        # With 1 report, total_score ~1.2, should give 10% boost
        expected_boost = 0.10
        if abs(boost - expected_boost) <= 0.05:
            self.log(f"Single user report boost: {boost*100}% (expected ~{expected_boost*100}%)")
        else:
            self.log(f"Single user report boost: {boost*100}% (expected ~{expected_boost*100}%)", False)

        if breakdown['nearby_count'] == 1:
            self.log(f"Nearby count: {breakdown['nearby_count']} (expected 1)")
        else:
            self.log(f"Nearby count: {breakdown['nearby_count']} (expected 1)", False)

        if breakdown['sources'].get('user_report', 0) == 1:
            self.log(f"User report count: {breakdown['sources']['user_report']} (expected 1)")
        else:
            self.log(f"User report count: {breakdown['sources'].get('user_report', 0)} (expected 1)", False)

    def test_official_source_nearby(self):
        """Test with NASA FIRMS wildfire nearby (should get 1.5x weight)"""
        print("\n🧪 Testing Official Source (NASA FIRMS)")
        print("=" * 60)

        now = datetime.now(timezone.utc).isoformat()

        report = {
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'severity': 'high',
            'timestamp': now
        }

        nearby = [{
            'type': 'wildfire',
            'latitude': 37.7800,  # ~5km away
            'longitude': -122.4100,
            'brightness': 360.5,  # High brightness
            'frp': 25.3,
            'source': 'nasa_firms',
            'timestamp': now
        }]

        boost, breakdown = self.scorer._calculate_corroboration(report, nearby)

        # Expected: distance_score ~1.0 × source_weight 1.5 (official) × severity 1.2 (high brightness) = 1.8
        # With 1 report, total_score ~1.8, should give 10% boost
        expected_boost = 0.10
        if abs(boost - expected_boost) <= 0.05:
            self.log(f"NASA FIRMS boost: {boost*100}% (expected ~{expected_boost*100}%)")
        else:
            self.log(f"NASA FIRMS boost: {boost*100}% (expected ~{expected_boost*100}%)", False)

        if breakdown['sources'].get('nasa_firms', 0) == 1:
            self.log(f"NASA FIRMS count: {breakdown['sources']['nasa_firms']} (expected 1)")
        else:
            self.log(f"NASA FIRMS count: {breakdown['sources'].get('nasa_firms', 0)} (expected 1)", False)

        # Check top match has correct source
        if breakdown['top_matches'] and breakdown['top_matches'][0]['source'] == 'nasa_firms':
            self.log(f"Top match source: {breakdown['top_matches'][0]['source']} (expected nasa_firms)")
        else:
            self.log(f"Top match source: {breakdown['top_matches'][0]['source'] if breakdown['top_matches'] else 'none'} (expected nasa_firms)", False)

    def test_multiple_sources_mixed(self):
        """Test with mix of user reports and official sources"""
        print("\n🧪 Testing Multiple Mixed Sources")
        print("=" * 60)

        now = datetime.now(timezone.utc).isoformat()

        report = {
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'severity': 'high',
            'timestamp': now
        }

        nearby = [
            {  # User report, very close
                'id': 'report_1',
                'type': 'wildfire',
                'latitude': 37.7750,  # ~0.1km
                'longitude': -122.4195,
                'severity': 'high',
                'source': 'user_report',
                'timestamp': now
            },
            {  # NASA FIRMS, close
                'type': 'wildfire',
                'latitude': 37.7800,  # ~5km
                'longitude': -122.4100,
                'brightness': 360.5,
                'source': 'nasa_firms',
                'timestamp': now
            },
            {  # User report, medium distance
                'id': 'report_2',
                'type': 'wildfire',
                'latitude': 37.8200,  # ~20km
                'longitude': -122.3800,
                'severity': 'medium',  # Adjacent severity
                'source': 'user_report',
                'timestamp': now
            },
            {  # NOAA weather alert, farther
                'type': 'wildfire',
                'latitude': 37.9000,  # ~40km
                'longitude': -122.3000,
                'event': 'Red Flag Warning',
                'severity': 'high',
                'source': 'noaa',
                'timestamp': now
            }
        ]

        boost, breakdown = self.scorer._calculate_corroboration(report, nearby)

        # Should get 20-30% boost with multiple corroborating sources
        if 0.20 <= boost <= 0.35:
            self.log(f"Multiple sources boost: {boost*100}% (expected 20-35%)")
        else:
            self.log(f"Multiple sources boost: {boost*100}% (expected 20-35%)", False)

        if breakdown['nearby_count'] == 4:
            self.log(f"Nearby count: {breakdown['nearby_count']} (expected 4)")
        else:
            self.log(f"Nearby count: {breakdown['nearby_count']} (expected 4)", False)

        # Check source distribution (may include 'other': 0)
        expected_user = 2
        expected_nasa = 1
        expected_noaa = 1
        sources_correct = (
            breakdown['sources'].get('user_report', 0) == expected_user and
            breakdown['sources'].get('nasa_firms', 0) == expected_nasa and
            breakdown['sources'].get('noaa', 0) == expected_noaa
        )
        if sources_correct:
            self.log(f"Source distribution: user={expected_user}, nasa={expected_nasa}, noaa={expected_noaa}")
        else:
            self.log(f"Source distribution: {breakdown['sources']} (expected user={expected_user}, nasa={expected_nasa}, noaa={expected_noaa})", False)

    def test_temporal_filtering(self):
        """Test that old reports (>24h) are excluded"""
        print("\n🧪 Testing Temporal Filtering (24h window)")
        print("=" * 60)

        now = datetime.now(timezone.utc)
        old_time = (now - timedelta(hours=25)).isoformat()
        recent_time = (now - timedelta(hours=12)).isoformat()

        report = {
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'severity': 'high',
            'timestamp': now.isoformat()
        }

        nearby = [
            {  # Recent report (should be included)
                'id': 'report_recent',
                'type': 'wildfire',
                'latitude': 37.7800,
                'longitude': -122.4100,
                'severity': 'high',
                'source': 'user_report',
                'timestamp': recent_time
            },
            {  # Old report (should be excluded)
                'id': 'report_old',
                'type': 'wildfire',
                'latitude': 37.7800,
                'longitude': -122.4100,
                'severity': 'high',
                'source': 'user_report',
                'timestamp': old_time
            }
        ]

        boost, breakdown = self.scorer._calculate_corroboration(report, nearby)

        # Should only count 1 report (the recent one)
        if breakdown['nearby_count'] == 1:
            self.log(f"Temporal filter - nearby count: {breakdown['nearby_count']} (expected 1, old report excluded)")
        else:
            self.log(f"Temporal filter - nearby count: {breakdown['nearby_count']} (expected 1)", False)

    def test_distance_decay(self):
        """Test distance decay scoring (0-6 miles vs 30-50km vs 50-50 miles)"""
        print("\n🧪 Testing Distance Decay")
        print("=" * 60)

        now = datetime.now(timezone.utc).isoformat()
        base_report = {
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'severity': 'high',
            'timestamp': now
        }

        # Very close (within 6 miles)
        close_nearby = [{
            'type': 'wildfire',
            'latitude': 37.7800,  # ~5km
            'longitude': -122.4100,
            'severity': 'high',
            'source': 'user_report',
            'timestamp': now
        }]

        # Medium distance (30-50km)
        medium_nearby = [{
            'type': 'wildfire',
            'latitude': 38.1000,  # ~40km
            'longitude': -122.2000,
            'severity': 'high',
            'source': 'user_report',
            'timestamp': now
        }]

        # Far distance (50-50 miles)
        far_nearby = [{
            'type': 'wildfire',
            'latitude': 38.3000,  # ~70km
            'longitude': -122.0000,
            'severity': 'high',
            'source': 'user_report',
            'timestamp': now
        }]

        boost_close, breakdown_close = self.scorer._calculate_corroboration(base_report, close_nearby)
        boost_medium, breakdown_medium = self.scorer._calculate_corroboration(base_report, medium_nearby)
        boost_far, breakdown_far = self.scorer._calculate_corroboration(base_report, far_nearby)

        # Close should have higher score than medium, medium higher than far
        score_close = breakdown_close['total_score']
        score_medium = breakdown_medium['total_score']
        score_far = breakdown_far['total_score']

        if score_close > score_medium > score_far:
            self.log(f"Distance decay: close({score_close:.2f}) > medium({score_medium:.2f}) > far({score_far:.2f})")
        else:
            self.log(f"Distance decay: close({score_close:.2f}) > medium({score_medium:.2f}) > far({score_far:.2f})", False)

    def test_severity_mismatch_penalty(self):
        """Test that mismatched severity gets penalty"""
        print("\n🧪 Testing Severity Mismatch Penalty")
        print("=" * 60)

        now = datetime.now(timezone.utc).isoformat()

        # High severity report
        report = {
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'severity': 'high',
            'timestamp': now
        }

        # Exact match (high)
        exact_nearby = [{
            'type': 'wildfire',
            'latitude': 37.7800,
            'longitude': -122.4100,
            'severity': 'high',
            'source': 'user_report',
            'timestamp': now
        }]

        # Adjacent match (medium)
        adjacent_nearby = [{
            'type': 'wildfire',
            'latitude': 37.7800,
            'longitude': -122.4100,
            'severity': 'medium',
            'source': 'user_report',
            'timestamp': now
        }]

        # Mismatch (low)
        mismatch_nearby = [{
            'type': 'wildfire',
            'latitude': 37.7800,
            'longitude': -122.4100,
            'severity': 'low',
            'source': 'user_report',
            'timestamp': now
        }]

        boost_exact, breakdown_exact = self.scorer._calculate_corroboration(report, exact_nearby)
        boost_adjacent, breakdown_adjacent = self.scorer._calculate_corroboration(report, adjacent_nearby)
        boost_mismatch, breakdown_mismatch = self.scorer._calculate_corroboration(report, mismatch_nearby)

        # Exact should have highest score, adjacent moderate, mismatch lowest
        score_exact = breakdown_exact['total_score']
        score_adjacent = breakdown_adjacent['total_score']
        score_mismatch = breakdown_mismatch['total_score']

        if score_exact > score_adjacent > score_mismatch:
            self.log(f"Severity matching: exact({score_exact:.2f}) > adjacent({score_adjacent:.2f}) > mismatch({score_mismatch:.2f})")
        else:
            self.log(f"Severity matching: exact({score_exact:.2f}) > adjacent({score_adjacent:.2f}) > mismatch({score_mismatch:.2f})", False)

    def test_full_confidence_score_integration(self):
        """Test full confidence score calculation with corroboration"""
        print("\n🧪 Testing Full Confidence Score Integration")
        print("=" * 60)

        now = datetime.now(timezone.utc).isoformat()

        # Basic user report
        report = {
            'type': 'wildfire',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'severity': 'high',
            'description': 'Large wildfire spreading quickly',
            'recaptcha_score': 0.8,
            'timestamp': now
        }

        # No nearby reports
        result_no_corr = self.scorer.calculate_confidence(report, nearby_reports=[])

        # With nearby NASA FIRMS data
        nearby = [
            {
                'type': 'wildfire',
                'latitude': 37.7800,
                'longitude': -122.4100,
                'brightness': 360.5,
                'source': 'nasa_firms',
                'timestamp': now
            },
            {
                'type': 'wildfire',
                'latitude': 37.7850,
                'longitude': -122.4050,
                'brightness': 355.0,
                'source': 'nasa_firms',
                'timestamp': now
            }
        ]

        result_with_corr = self.scorer.calculate_confidence(report, nearby_reports=nearby)

        # Score with corroboration should be higher
        score_no_corr = result_no_corr['confidence_score']
        score_with_corr = result_with_corr['confidence_score']

        if score_with_corr > score_no_corr:
            boost_amount = score_with_corr - score_no_corr
            self.log(f"Corroboration boost: {score_no_corr:.1f}% → {score_with_corr:.1f}% (+{boost_amount:.1f}%)")
        else:
            self.log(f"Corroboration boost: {score_no_corr:.1f}% → {score_with_corr:.1f}%", False)

        # Check breakdown includes corroboration data
        if 'corroboration' in result_with_corr['breakdown']:
            corr_data = result_with_corr['breakdown']['corroboration']
            self.log(f"Corroboration data in breakdown: nearby_count={corr_data.get('nearby_count', 0)}, boost={corr_data.get('boost', 0)*100}%")
        else:
            self.log("Corroboration data in breakdown: missing", False)

    def run_all_tests(self):
        """Run all test cases"""
        print("\n" + "=" * 60)
        print("🧪 SPATIAL CORROBORATION TEST SUITE")
        print("=" * 60)

        self.test_distance_calculation()
        self.test_severity_adjacent()
        self.test_no_nearby_reports()
        self.test_single_user_report_nearby()
        self.test_official_source_nearby()
        self.test_multiple_sources_mixed()
        self.test_temporal_filtering()
        self.test_distance_decay()
        self.test_severity_mismatch_penalty()
        self.test_full_confidence_score_integration()

        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)

        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r['success'])
        failed = total - passed

        print(f"Total Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"Success Rate: {(passed/total*100):.1f}%")

        if failed > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['message']}")

        print("=" * 60)

        return failed == 0

if __name__ == '__main__':
    tester = TestSpatialCorroboration()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
