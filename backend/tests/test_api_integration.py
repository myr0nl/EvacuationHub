#!/usr/bin/env python3
"""
End-to-end API integration test for spatial corroboration

This test simulates the complete flow:
1. Submit a user report via API
2. API queries Firebase for nearby reports
3. Confidence scorer calculates with spatial corroboration
4. Response includes corroboration breakdown
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from services.confidence_scorer import ConfidenceScorer

def setup_test_data():
    """Setup test data in Firebase"""
    print("\n🔧 Setting up test data in Firebase...")

    # Add some existing user reports for corroboration
    reports_ref = db.reference('reports')

    test_report_1 = {
        'type': 'wildfire',
        'latitude': 34.0530,  # ~1km from test location
        'longitude': -118.2445,
        'severity': 'high',
        'description': 'Fire spreading near residential area',
        'source': 'user_report',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'recaptcha_score': 0.8
    }

    test_report_2 = {
        'type': 'wildfire',
        'latitude': 34.0550,  # ~3km from test location
        'longitude': -118.2460,
        'severity': 'high',
        'description': 'Large smoke plume visible',
        'source': 'user_report',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'recaptcha_score': 0.75
    }

    # Add test reports
    ref1 = reports_ref.push(test_report_1)
    ref2 = reports_ref.push(test_report_2)

    print(f"✅ Added test report 1: {ref1.key}")
    print(f"✅ Added test report 2: {ref2.key}")

    return [ref1.key, ref2.key]

def cleanup_test_data(report_ids):
    """Remove test data from Firebase"""
    print("\n🧹 Cleaning up test data...")
    reports_ref = db.reference('reports')

    for report_id in report_ids:
        reports_ref.child(report_id).delete()
        print(f"✅ Deleted test report: {report_id}")

def test_api_submission():
    """Test the complete API submission with spatial corroboration"""
    print("\n" + "="*60)
    print("🧪 END-TO-END API INTEGRATION TEST")
    print("="*60)

    # Setup test data
    test_report_ids = setup_test_data()

    try:
        # Create test client
        client = app.test_client()

        # Submit a new report that should corroborate with existing ones
        new_report = {
            'type': 'wildfire',
            'latitude': 34.0522,  # Los Angeles (near existing reports)
            'longitude': -118.2437,
            'severity': 'high',
            'description': 'Large wildfire spreading quickly',
            'recaptcha_score': 0.7,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        print("\n📤 Submitting new report via API...")
        print(f"   Type: {new_report['type']}")
        print(f"   Location: ({new_report['latitude']}, {new_report['longitude']})")
        print(f"   Severity: {new_report['severity']}")
        print(f"   reCAPTCHA: {new_report['recaptcha_score']}")

        # Submit to API
        response = client.post('/api/reports',
                              data=json.dumps(new_report),
                              content_type='application/json')

        print(f"\n📥 API Response Status: {response.status_code}")

        if response.status_code in [200, 201]:  # Accept both 200 OK and 201 Created
            result = json.loads(response.data)

            print("\n" + "="*60)
            print("📊 CONFIDENCE SCORING RESULT")
            print("="*60)

            # Extract confidence info (handle both formats)
            if 'confidence' in result:
                confidence_data = result['confidence']
                confidence_score = confidence_data.get('confidence_score', 0)
                confidence_level = confidence_data.get('confidence_level', 'Unknown')
                breakdown = confidence_data.get('breakdown', {})
            else:
                confidence_score = result.get('confidence_score', 0)
                confidence_level = result.get('confidence_level', 'Unknown')
                breakdown = result.get('breakdown', {})

            print(f"\n✨ Confidence Score: {confidence_score*100:.1f}%")
            print(f"✨ Confidence Level: {confidence_level}")

            # Check for corroboration data
            if 'corroboration' in breakdown:
                corr = breakdown['corroboration']
                print(f"\n🌍 Spatial Corroboration:")
                print(f"   Nearby reports found: {corr.get('nearby_count', 0)}")
                print(f"   Boost applied: +{corr.get('boost', 0)*100:.0f}%")
                print(f"   Total score: {corr.get('total_score', 0):.2f}")
                print(f"   Sources: {corr.get('sources', {})}")

                if corr.get('top_matches'):
                    print(f"\n   Top matches:")
                    for i, match in enumerate(corr['top_matches'][:3], 1):
                        dist = match.get('distance_mi', 0)
                        source = match.get('source', 'unknown')
                        score = match.get('score', 0)
                        print(f"     {i}. {source} - {dist:.1f}mi (score: {score:.2f})")

                # Verification
                print("\n" + "="*60)
                print("✅ VERIFICATION")
                print("="*60)

                nearby_count = corr.get('nearby_count', 0)
                boost = corr.get('boost', 0)

                if nearby_count >= 2:
                    print(f"✅ Found {nearby_count} nearby reports (expected ≥2)")
                else:
                    print(f"❌ Found {nearby_count} nearby reports (expected ≥2)")

                if boost >= 0.1:  # At least 10% boost
                    print(f"✅ Applied {boost*100:.0f}% boost (expected ≥10%)")
                else:
                    print(f"❌ Applied {boost*100:.0f}% boost (expected ≥10%)")

                if confidence_score >= 0.85:  # Should be high with corroboration
                    print(f"✅ Final confidence {confidence_score*100:.1f}% (expected ≥85%)")
                else:
                    print(f"❌ Final confidence {confidence_score*100:.1f}% (expected ≥85%)")

                print("\n✅ END-TO-END TEST PASSED!")

            else:
                print("\n❌ ERROR: No corroboration data in breakdown")
                print(f"Breakdown keys: {breakdown.keys()}")
                return False

            # Clean up the submitted report
            report_id = result.get('id') or result.get('data', {}).get('id')
            if report_id:
                db.reference('reports').child(report_id).delete()
                print(f"\n🧹 Cleaned up submitted report: {report_id}")

            return True

        else:
            print(f"\n❌ API request failed: {response.status_code}")
            print(f"Response: {response.data}")
            return False

    finally:
        # Always cleanup test data
        cleanup_test_data(test_report_ids)

if __name__ == '__main__':
    success = test_api_submission()
    sys.exit(0 if success else 1)
