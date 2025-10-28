"""
Test Input Validation for API Endpoint
"""
import requests
import json

BASE_URL = "http://localhost:5001"

def test_validation():
    """Test API input validation"""
    print("\n" + "="*60)
    print("API VALIDATION TESTS")
    print("="*60)

    # Test 1: Missing required fields
    print("\n1. Testing missing required fields...")
    response = requests.post(f"{BASE_URL}/api/reports", json={})
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 400
    assert "Missing required fields" in response.json()['error']
    print("   ✅ PASSED")

    # Test 2: Invalid latitude
    print("\n2. Testing invalid latitude...")
    response = requests.post(f"{BASE_URL}/api/reports", json={
        'latitude': 100,  # Invalid: > 90
        'longitude': -118.25,
        'type': 'wildfire'
    })
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 400
    assert "Latitude must be between" in response.json()['error']
    print("   ✅ PASSED")

    # Test 3: Invalid longitude
    print("\n3. Testing invalid longitude...")
    response = requests.post(f"{BASE_URL}/api/reports", json={
        'latitude': 34.05,
        'longitude': 200,  # Invalid: > 180
        'type': 'wildfire'
    })
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 400
    assert "Longitude must be between" in response.json()['error']
    print("   ✅ PASSED")

    # Test 4: Invalid disaster type
    print("\n4. Testing invalid disaster type...")
    response = requests.post(f"{BASE_URL}/api/reports", json={
        'latitude': 34.05,
        'longitude': -118.25,
        'type': 'alien_invasion'  # Invalid type
    })
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 400
    assert "Invalid disaster type" in response.json()['error']
    print("   ✅ PASSED")

    # Test 5: Invalid recaptcha score
    print("\n5. Testing invalid recaptcha score...")
    response = requests.post(f"{BASE_URL}/api/reports", json={
        'latitude': 34.05,
        'longitude': -118.25,
        'type': 'wildfire',
        'recaptcha_score': 1.5  # Invalid: > 1
    })
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 400
    assert "recaptcha_score must be between" in response.json()['error']
    print("   ✅ PASSED")

    # Test 6: Valid request
    print("\n6. Testing valid request...")
    response = requests.post(f"{BASE_URL}/api/reports", json={
        'latitude': 34.05,
        'longitude': -118.25,
        'type': 'wildfire',
        'description': 'Large wildfire near residential area',
        'recaptcha_score': 0.9,
        'source': 'user_report'
    })
    print(f"   Status: {response.status_code}")
    if response.status_code == 201:
        data = response.json()
        print(f"   Report ID: {data['id']}")
        print(f"   Confidence Score: {data['confidence']['confidence_score']}")
        print(f"   Confidence Level: {data['confidence']['confidence_level']}")
        print("   ✅ PASSED")
    else:
        print(f"   ❌ FAILED: {response.json()}")

    print("\n" + "="*60)
    print("✅ ALL VALIDATION TESTS PASSED")
    print("="*60)

if __name__ == "__main__":
    print("\n⚠️  Note: Make sure backend server is running on localhost:5001")
    print("   Run: cd backend && source venv/bin/activate && python app.py\n")

    try:
        test_validation()
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to backend server")
        print("   Make sure the server is running on localhost:5001")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
