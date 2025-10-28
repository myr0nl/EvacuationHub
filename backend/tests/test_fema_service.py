"""
Tests for FEMA Disaster Service
"""
import pytest
from services.fema_disaster_service import FEMADisasterService


def test_fema_service_initialization():
    """Test FEMA service initializes correctly"""
    service = FEMADisasterService()
    assert service is not None
    assert service.BASE_URL == "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"


def test_map_disaster_type():
    """Test disaster type mapping"""
    service = FEMADisasterService()

    # Test exact matches
    assert service._map_disaster_type('Fire') == 'wildfire'
    assert service._map_disaster_type('Wildfire') == 'wildfire'
    assert service._map_disaster_type('Flood') == 'flood'
    assert service._map_disaster_type('Flooding') == 'flood'
    assert service._map_disaster_type('Hurricane') == 'hurricane'
    assert service._map_disaster_type('Earthquake') == 'earthquake'
    assert service._map_disaster_type('Tornado') == 'tornado'
    assert service._map_disaster_type('Tornadoes') == 'tornado'

    # Test partial matches (case-insensitive)
    assert service._map_disaster_type('Severe Storm') == 'other'
    assert service._map_disaster_type('Winter Storm') == 'other'
    assert service._map_disaster_type('Coastal Storm') == 'other'

    # Test unknown type defaults to 'other'
    assert service._map_disaster_type('Unknown Disaster') == 'other'


def test_is_us_state():
    """Test US state validation"""
    service = FEMADisasterService()

    # Test valid 50 states
    assert service._is_us_state('CA') == True
    assert service._is_us_state('NY') == True
    assert service._is_us_state('TX') == True
    assert service._is_us_state('AK') == True
    assert service._is_us_state('HI') == True

    # Test territories (should be excluded)
    assert service._is_us_state('PR') == False  # Puerto Rico
    assert service._is_us_state('VI') == False  # Virgin Islands
    assert service._is_us_state('GU') == False  # Guam
    assert service._is_us_state('AS') == False  # American Samoa

    # Test invalid codes
    assert service._is_us_state('XX') == False
    assert service._is_us_state('') == False


def test_get_state_centroid():
    """Test state centroid coordinates"""
    service = FEMADisasterService()

    # Test some known states
    lat, lon = service._get_state_centroid('CA')
    assert lat is not None and lon is not None
    assert 32 < lat < 42  # California latitude range
    assert -125 < lon < -114  # California longitude range

    lat, lon = service._get_state_centroid('NY')
    assert lat is not None and lon is not None
    assert 40 < lat < 45  # New York latitude range
    assert -80 < lon < -71  # New York longitude range

    # Test invalid state
    lat, lon = service._get_state_centroid('XX')
    assert lat is None
    assert lon is None


def test_determine_severity():
    """Test severity determination logic"""
    service = FEMADisasterService()

    # Test critical incidents
    declaration = {'incidentType': 'Hurricane', 'declarationType': 'Major Disaster'}
    assert service._determine_severity(declaration) == 'critical'

    declaration = {'incidentType': 'Earthquake', 'declarationType': 'Emergency'}
    assert service._determine_severity(declaration) == 'critical'

    # Test high severity
    declaration = {'incidentType': 'Fire', 'declarationType': 'Major Disaster'}
    assert service._determine_severity(declaration) == 'high'

    declaration = {'incidentType': 'Flood', 'declarationType': 'DR'}
    assert service._determine_severity(declaration) == 'high'

    # Test medium severity
    declaration = {'incidentType': 'Severe Storm', 'declarationType': 'Emergency'}
    assert service._determine_severity(declaration) == 'medium'

    declaration = {'incidentType': 'Flood', 'declarationType': 'EM'}
    assert service._determine_severity(declaration) == 'medium'


def test_parse_timestamp():
    """Test timestamp parsing"""
    service = FEMADisasterService()

    # Test FEMA format
    timestamp = service._parse_timestamp('2024-01-15T00:00:00.000z')
    assert '2024-01-15' in timestamp
    assert 'T' in timestamp

    # Test alternative format
    timestamp = service._parse_timestamp('2024-01-15T12:30:00.000Z')
    assert '2024-01-15' in timestamp

    # Test invalid format (should return current time)
    timestamp = service._parse_timestamp('invalid')
    assert timestamp is not None
    assert 'T' in timestamp


@pytest.mark.integration
def test_fetch_recent_disasters_integration():
    """Integration test - fetch real FEMA data (requires network)"""
    service = FEMADisasterService()

    # Fetch 7 days of data
    disasters = service.get_recent_disasters(days=7)

    # Should return list (may be empty if no recent disasters)
    assert isinstance(disasters, list)

    # If there are disasters, validate structure
    if len(disasters) > 0:
        disaster = disasters[0]
        assert 'id' in disaster
        assert 'source' in disaster
        assert disaster['source'] == 'fema'
        assert 'type' in disaster
        assert 'latitude' in disaster
        assert 'longitude' in disaster
        assert 'disaster_number' in disaster
        assert 'state' in disaster
        assert 'severity' in disaster
        assert 'timestamp' in disaster

        # Validate coordinates are valid
        assert -90 <= disaster['latitude'] <= 90
        assert -180 <= disaster['longitude'] <= 180

        # Validate confidence scoring was applied
        assert 'confidence_score' in disaster
        assert 'confidence_level' in disaster
        assert 0 <= disaster['confidence_score'] <= 1

        print(f"\nFetched {len(disasters)} FEMA disasters")
        print(f"Sample disaster: {disaster['state']} - {disaster['incident_type']}")


def test_parse_fema_response():
    """Test parsing of FEMA API response"""
    service = FEMADisasterService()

    # Mock FEMA response data
    mock_declarations = [
        {
            'disasterNumber': 4747,
            'state': 'CA',
            'incidentType': 'Fire',
            'declarationTitle': 'WILDFIRES',
            'declarationDate': '2024-01-15T00:00:00.000z',
            'declarationType': 'Major Disaster'
        },
        {
            'disasterNumber': 3500,
            'state': 'FL',
            'incidentType': 'Hurricane',
            'declarationTitle': 'HURRICANE IAN',
            'declarationDate': '2024-01-10T00:00:00.000z',
            'declarationType': 'Major Disaster'
        }
    ]

    disasters = service._parse_fema_response(mock_declarations)

    assert len(disasters) == 2

    # Validate California fire
    ca_fire = disasters[0]
    assert ca_fire['state'] == 'CA'
    assert ca_fire['type'] == 'wildfire'
    assert ca_fire['incident_type'] == 'Fire'
    assert ca_fire['disaster_number'] == 4747
    assert ca_fire['severity'] == 'high'
    assert ca_fire['source'] == 'fema'

    # Validate Florida hurricane
    fl_hurricane = disasters[1]
    assert fl_hurricane['state'] == 'FL'
    assert fl_hurricane['type'] == 'hurricane'
    assert fl_hurricane['incident_type'] == 'Hurricane'
    assert fl_hurricane['disaster_number'] == 3500
    assert fl_hurricane['severity'] == 'critical'
    assert fl_hurricane['source'] == 'fema'


if __name__ == '__main__':
    # Run integration test to verify API connectivity
    print("Running FEMA Service integration test...")
    test_fetch_recent_disasters_integration()
