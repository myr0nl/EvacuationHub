#!/usr/bin/env python3
"""
Real-world scenario testing for spatial corroboration

Tests realistic disaster reporting scenarios to verify:
1. Confidence scores make sense for real-world cases
2. Boost calculations are reasonable and helpful
3. System behaves correctly with actual data patterns
"""

import sys
import os
from datetime import datetime, timezone, timedelta

# Add parent directory to path to import services
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.confidence_scorer import ConfidenceScorer

class RealScenarioTester:
    def __init__(self):
        self.scorer = ConfidenceScorer()

    def print_result(self, title, result):
        """Pretty print confidence result"""
        print(f"\n{'='*60}")
        print(f"📊 {title}")
        print(f"{'='*60}")
        print(f"Confidence Score: {result['confidence_score']*100:.1f}%")  # Convert 0-1 to percentage
        print(f"Confidence Level: {result['confidence_level']}")

        if 'corroboration' in result['breakdown']:
            corr = result['breakdown']['corroboration']
            print(f"\n🌍 Spatial Corroboration:")
            print(f"  Nearby reports: {corr['nearby_count']}")
            print(f"  Boost applied: +{corr['boost']*100:.0f}%")
            if 'total_score' in corr:  # Only show if available
                print(f"  Total score: {corr['total_score']:.2f}")
            print(f"  Sources: {corr['sources']}")

            if corr.get('top_matches'):
                print(f"\n  Top matches:")
                for i, match in enumerate(corr['top_matches'][:3], 1):
                    print(f"    {i}. {match['source']} - {match['distance_mi']:.1f}mi (score: {match['score']:.2f})")

        print(f"\n📈 Breakdown:")
        for key, value in result['breakdown'].items():
            if key != 'corroboration':
                if isinstance(value, dict):
                    print(f"  {key}: {value.get('score', 0)*100:.1f}% (weight: {value.get('weight', 0)*100:.0f}%)")
                else:
                    print(f"  {key}: {value}")

    def scenario_1_verified_wildfire(self):
        """Scenario 1: User reports wildfire confirmed by NASA FIRMS"""
        print("\n" + "="*60)
        print("🔥 SCENARIO 1: User Reports Wildfire Confirmed by NASA FIRMS")
        print("="*60)
        print("Context: User reports wildfire, 3 NASA FIRMS detections nearby")

        now = datetime.now(timezone.utc).isoformat()

        # User report
        user_report = {
            'type': 'wildfire',
            'latitude': 34.0522,  # Los Angeles area
            'longitude': -118.2437,
            'severity': 'high',
            'description': 'Large fire spreading fast near residential area',
            'recaptcha_score': 0.7,
            'timestamp': now
        }

        # NASA FIRMS detections nearby
        nearby = [
            {
                'type': 'wildfire',
                'latitude': 34.0530,  # ~1km away
                'longitude': -118.2445,
                'brightness': 365.2,
                'frp': 35.5,
                'confidence': 'nominal',
                'source': 'nasa_firms',
                'timestamp': now
            },
            {
                'type': 'wildfire',
                'latitude': 34.0550,  # ~3km away
                'longitude': -118.2460,
                'brightness': 358.7,
                'frp': 28.3,
                'confidence': 'nominal',
                'source': 'nasa_firms',
                'timestamp': now
            },
            {
                'type': 'wildfire',
                'latitude': 34.0600,  # ~9km away
                'longitude': -118.2500,
                'brightness': 352.1,
                'frp': 22.1,
                'confidence': 'nominal',
                'source': 'nasa_firms',
                'timestamp': now
            }
        ]

        result = self.scorer.calculate_confidence(user_report, nearby_reports=nearby)
        self.print_result("User Report with NASA FIRMS Confirmation", result)

        # Expected: Should get 20-30% boost, final score ~85-95%
        print(f"\n✅ Expected: High confidence (85-95%) with substantial boost from official data")
        print(f"   Actual: {result['confidence_score']*100:.1f}% ({result['confidence_level']})")

    def scenario_2_community_corroboration(self):
        """Scenario 2: Multiple users report same earthquake"""
        print("\n" + "="*60)
        print("🏚️ SCENARIO 2: Multiple Users Report Same Earthquake")
        print("="*60)
        print("Context: 5 users independently report earthquake in same area")

        now = datetime.now(timezone.utc).isoformat()

        # Primary report
        primary_report = {
            'type': 'earthquake',
            'latitude': 37.7749,  # San Francisco
            'longitude': -122.4194,
            'severity': 'medium',
            'description': 'Strong shaking, lasted about 15 seconds',
            'recaptcha_score': 0.75,
            'timestamp': now
        }

        # Other user reports nearby
        nearby = [
            {
                'id': 'user_1',
                'type': 'earthquake',
                'latitude': 37.7755,  # 0.7km
                'longitude': -122.4200,
                'severity': 'medium',
                'source': 'user_report',
                'timestamp': now
            },
            {
                'id': 'user_2',
                'type': 'earthquake',
                'latitude': 37.7760,  # 1.2km
                'longitude': -122.4210,
                'severity': 'high',  # Adjacent severity
                'source': 'user_report',
                'timestamp': now
            },
            {
                'id': 'user_3',
                'type': 'earthquake',
                'latitude': 37.7800,  # 5.6km
                'longitude': -122.4300,
                'severity': 'medium',
                'source': 'user_report',
                'timestamp': now
            },
            {
                'id': 'user_4',
                'type': 'earthquake',
                'latitude': 37.7850,  # 11.3km
                'longitude': -122.4400,
                'severity': 'low',  # Different severity
                'source': 'user_report',
                'timestamp': now
            },
            {
                'id': 'user_5',
                'type': 'earthquake',
                'latitude': 37.8000,  # 27.8km
                'longitude': -122.4500,
                'severity': 'medium',
                'source': 'user_report',
                'timestamp': now
            }
        ]

        result = self.scorer.calculate_confidence(primary_report, nearby_reports=nearby)
        self.print_result("Primary Report with Community Corroboration", result)

        # Expected: Should get 20-30% boost from multiple nearby reports
        print(f"\n✅ Expected: High confidence (80-90%) from community corroboration")
        print(f"   Actual: {result['confidence_score']*100:.1f}% ({result['confidence_level']})")

    def scenario_3_severe_weather_noaa_confirmed(self):
        """Scenario 3: User reports flooding confirmed by NOAA alerts"""
        print("\n" + "="*60)
        print("🌊 SCENARIO 3: User Reports Flooding with NOAA Confirmation")
        print("="*60)
        print("Context: User reports flooding, NOAA has flood warning active")

        now = datetime.now(timezone.utc).isoformat()

        # User report
        user_report = {
            'type': 'flood',
            'latitude': 29.7604,  # Houston
            'longitude': -95.3698,
            'severity': 'high',
            'description': 'Streets flooding rapidly, water rising',
            'recaptcha_score': 0.8,
            'timestamp': now
        }

        # NOAA flood warning (type must match for corroboration)
        nearby = [
            {
                'type': 'flood',  # Changed from 'weather_alert' to match user report type
                'event': 'Flood Warning',
                'latitude': 29.7650,  # 5.1km
                'longitude': -95.3750,
                'severity': 'high',  # Normalized severity to match user report
                'source': 'noaa',
                'timestamp': now
            },
            {
                'type': 'flood',
                'event': 'Flash Flood Warning',
                'latitude': 29.7700,  # 10.7km
                'longitude': -95.3800,
                'severity': 'critical',  # Extreme -> critical
                'source': 'noaa',
                'timestamp': now
            }
        ]

        result = self.scorer.calculate_confidence(user_report, nearby_reports=nearby)
        self.print_result("User Report with NOAA Alert Confirmation", result)

        # Expected: Should get 10-20% boost from official weather alerts
        print(f"\n✅ Expected: High confidence (85-95%) with official weather service confirmation")
        print(f"   Actual: {result['confidence_score']*100:.1f}% ({result['confidence_level']})")

    def scenario_4_isolated_report_no_corroboration(self):
        """Scenario 4: Isolated report with no nearby confirmation"""
        print("\n" + "="*60)
        print("❓ SCENARIO 4: Isolated Report (No Corroboration)")
        print("="*60)
        print("Context: User reports tornado but no nearby data confirms")

        now = datetime.now(timezone.utc).isoformat()

        # Isolated report
        report = {
            'type': 'tornado',
            'latitude': 35.4676,  # Oklahoma
            'longitude': -97.5164,
            'severity': 'critical',
            'description': 'Tornado sighted heading east',
            'recaptcha_score': 0.6,  # Lower reCAPTCHA
            'timestamp': now
        }

        # No nearby reports (empty array)
        nearby = []

        result = self.scorer.calculate_confidence(report, nearby_reports=nearby)
        self.print_result("Isolated Report (No Corroboration)", result)

        # Expected: Base score without boost, lower due to no confirmation
        print(f"\n✅ Expected: Medium confidence (60-75%) - no corroboration, lower reCAPTCHA")
        print(f"   Actual: {result['confidence_score']*100:.1f}% ({result['confidence_level']})")

    def scenario_5_mixed_disaster_types(self):
        """Scenario 5: User reports wildfire, nearby weather alerts (different type)"""
        print("\n" + "="*60)
        print("🔥🌪️ SCENARIO 5: Wildfire Report with Weather Alerts (Different Types)")
        print("="*60)
        print("Context: User reports wildfire, nearby wind/heat advisories from NOAA")

        now = datetime.now(timezone.utc).isoformat()

        # Wildfire report
        report = {
            'type': 'wildfire',
            'latitude': 38.5816,  # Northern California
            'longitude': -121.4944,
            'severity': 'high',
            'description': 'Fire spreading due to high winds',
            'recaptcha_score': 0.75,
            'timestamp': now
        }

        # Weather alerts (related but different type)
        nearby = [
            {
                'type': 'weather_alert',
                'event': 'Red Flag Warning',  # Fire weather
                'latitude': 38.5900,  # 9.3km
                'longitude': -121.5000,
                'severity': 'Extreme',
                'source': 'noaa',
                'timestamp': now
            },
            {
                'type': 'weather_alert',
                'event': 'High Wind Warning',
                'latitude': 38.6000,  # 20.6km
                'longitude': -121.5200,
                'severity': 'Moderate',
                'source': 'noaa',
                'timestamp': now
            }
        ]

        result = self.scorer.calculate_confidence(report, nearby_reports=nearby)
        self.print_result("Wildfire with Related Weather Alerts", result)

        # Expected: No boost (different disaster types), but still good base score
        print(f"\n✅ Expected: Medium-High confidence (70-80%) - base score only, types don't match")
        print(f"   Actual: {result['confidence_score']*100:.1f}% ({result['confidence_level']})")

    def scenario_6_old_nearby_reports(self):
        """Scenario 6: User reports fire, nearby reports are >24h old"""
        print("\n" + "="*60)
        print("⏰ SCENARIO 6: Current Report with Old Nearby Data (>24h)")
        print("="*60)
        print("Context: User reports wildfire, nearby FIRMS data is 30 hours old")

        now = datetime.now(timezone.utc)
        old_time = (now - timedelta(hours=30)).isoformat()

        # Current report
        report = {
            'type': 'wildfire',
            'latitude': 34.0522,
            'longitude': -118.2437,
            'severity': 'high',
            'description': 'New fire outbreak',
            'recaptcha_score': 0.75,
            'timestamp': now.isoformat()
        }

        # Old NASA FIRMS data
        nearby = [
            {
                'type': 'wildfire',
                'latitude': 34.0530,
                'longitude': -118.2445,
                'brightness': 365.2,
                'source': 'nasa_firms',
                'timestamp': old_time  # 30 hours ago
            }
        ]

        result = self.scorer.calculate_confidence(report, nearby_reports=nearby)
        self.print_result("Current Report with Old Nearby Data", result)

        # Expected: No boost (temporal filter excludes >24h reports)
        print(f"\n✅ Expected: Medium confidence (70-80%) - old data filtered out, no boost")
        print(f"   Actual: {result['confidence_score']*100:.1f}% ({result['confidence_level']})")

    def run_all_scenarios(self):
        """Run all real-world scenario tests"""
        print("\n" + "="*60)
        print("🌍 REAL-WORLD SCENARIO TESTING")
        print("="*60)

        self.scenario_1_verified_wildfire()
        self.scenario_2_community_corroboration()
        self.scenario_3_severe_weather_noaa_confirmed()
        self.scenario_4_isolated_report_no_corroboration()
        self.scenario_5_mixed_disaster_types()
        self.scenario_6_old_nearby_reports()

        print("\n" + "="*60)
        print("✅ All real-world scenarios completed")
        print("="*60)
        print("\nManual verification points:")
        print("1. Scores should increase with official source confirmation")
        print("2. Community corroboration should provide meaningful boost")
        print("3. Isolated reports should still be credible but not boosted")
        print("4. Different disaster types should not cross-boost")
        print("5. Old data should be filtered out by temporal window")
        print("="*60)

if __name__ == '__main__':
    tester = RealScenarioTester()
    tester.run_all_scenarios()
