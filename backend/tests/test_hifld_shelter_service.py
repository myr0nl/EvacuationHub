"""
Tests for HIFLDShelterService
Tests API integration, response parsing, and data transformation
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from services.hifld_shelter_service import HIFLDShelterService


class TestHIFLDShelterService:
    """Test suite for HIFLD shelter service"""

    def setup_method(self):
        """Set up test fixtures"""
        self.service = HIFLDShelterService()

    def test_initialization(self):
        """Test service initializes correctly"""
        assert self.service is not None
        assert self.service.BASE_URL.endswith("/MapServer/7/query")
        assert self.service.MAX_RECORDS == 10000
        assert self.service.TIMEOUT_SECONDS == 30

    def test_map_shelter_type_hospital(self):
        """Test mapping hospital types"""
        assert self.service._map_shelter_type("Hospital") == "hospital"
        assert self.service._map_shelter_type("Medical Center") == "hospital"
        assert self.service._map_shelter_type("Emergency Medical") == "hospital"

    def test_map_shelter_type_fire_station(self):
        """Test mapping fire station types"""
        assert self.service._map_shelter_type("Fire Station") == "fire_station"
        assert self.service._map_shelter_type("Fire Department") == "fire_station"

    def test_map_shelter_type_evacuation_center(self):
        """Test mapping evacuation center types"""
        assert self.service._map_shelter_type("Evacuation Center") == "evacuation_center"
        assert self.service._map_shelter_type("Temporary Evacuation Point") == "evacuation_center"

    def test_map_shelter_type_default(self):
        """Test default mapping for unknown types"""
        assert self.service._map_shelter_type("Unknown Type") == "evacuation_center"
        assert self.service._map_shelter_type("") == "evacuation_center"
        assert self.service._map_shelter_type(None) == "evacuation_center"

    def test_map_status_open(self):
        """Test mapping open status"""
        assert self.service._map_status("OPEN") == "open"
        assert self.service._map_status("Active") == "open"
        assert self.service._map_status("Available") == "open"
        assert self.service._map_status("Operational") == "open"

    def test_map_status_closed(self):
        """Test mapping closed status"""
        assert self.service._map_status("CLOSED") == "closed"
        assert self.service._map_status("Inactive") == "closed"
        assert self.service._map_status("Unavailable") == "closed"

    def test_map_status_at_capacity(self):
        """Test mapping at_capacity status"""
        assert self.service._map_status("AT CAPACITY") == "at_capacity"
        assert self.service._map_status("Full") == "at_capacity"

    def test_map_status_damaged(self):
        """Test mapping damaged status"""
        assert self.service._map_status("DAMAGED") == "damaged"
        assert self.service._map_status("Destroyed") == "damaged"
        assert self.service._map_status("Compromised") == "damaged"

    def test_map_status_unknown(self):
        """Test default mapping for unknown status"""
        assert self.service._map_status("Unknown Status") == "unknown"
        assert self.service._map_status("") == "unknown"
        assert self.service._map_status(None) == "unknown"

    def test_build_address_all_fields(self):
        """Test building address with all fields present"""
        address = self.service._build_address(
            "123 Main St",
            "San Francisco",
            "CA",
            "94102"
        )
        assert address == "123 Main St, San Francisco, CA, 94102"

    def test_build_address_partial_fields(self):
        """Test building address with some fields missing"""
        address = self.service._build_address(
            "123 Main St",
            "San Francisco",
            "",
            ""
        )
        assert address == "123 Main St, San Francisco"

    def test_build_address_empty(self):
        """Test building address with no fields"""
        address = self.service._build_address("", "", "", "")
        assert address == ""

    def test_parse_amenities_comma_separated(self):
        """Test parsing comma-separated amenities for evacuation center"""
        # Test with evacuation center - should include default amenities
        props = {'ada': 'YES', 'wheel': 'YES', 'electric': 'YES', 'pet_code': 'ALLOWED'}
        amenities = self.service._parse_amenities(props, 'EVACUATION')
        assert 'wheelchair_accessible' in amenities
        assert 'power' in amenities
        assert 'pets_allowed' in amenities
        assert 'shelter' in amenities
        assert 'water' in amenities
        assert 'food' in amenities

    def test_parse_amenities_flags(self):
        """Test parsing HIFLD-specific amenity flags for shelter"""
        props = {
            'ada': 'YES',
            'wheel': 'YES',
            'electric': 'YES'
        }
        # Test with shelter type - should include default amenities
        amenities = self.service._parse_amenities(props, 'BOTH')
        assert 'wheelchair_accessible' in amenities
        assert 'power' in amenities
        # Includes default shelter amenities (BOTH = evacuation + shelter)
        assert 'food' in amenities
        assert 'water' in amenities
        assert 'shelter' in amenities

    def test_parse_amenities_empty(self):
        """Test parsing with no special amenities for evacuation center"""
        props = {}
        # Test with evacuation center - should include default amenities
        amenities = self.service._parse_amenities(props, 'EVACUATION')
        # Should include default shelter amenities
        assert 'shelter' in amenities
        assert 'water' in amenities
        assert 'food' in amenities

    def test_parse_amenities_hospital_no_defaults(self):
        """Test that hospitals don't get default shelter amenities"""
        props = {'electric': 'YES'}
        amenities = self.service._parse_amenities(props, 'HOSPITAL')
        # Hospital should have power but NOT default shelter amenities
        assert 'power' in amenities
        assert 'shelter' not in amenities
        assert 'water' not in amenities
        assert 'food' not in amenities

    def test_parse_contact_all_fields(self):
        """Test parsing contact with all fields"""
        props = {
            'telephone': '+1-415-555-1234',
            'website': 'https://shelter.org'
        }
        contact = self.service._parse_contact(props)
        assert contact['phone'] == '+1-415-555-1234'
        assert contact['website'] == 'https://shelter.org'

    def test_parse_contact_partial_fields(self):
        """Test parsing contact with some fields missing"""
        props = {'telephone': '+1-415-555-1234'}
        contact = self.service._parse_contact(props)
        assert contact['phone'] == '+1-415-555-1234'
        assert 'website' not in contact

    def test_parse_contact_empty(self):
        """Test parsing contact with no fields"""
        props = {}
        contact = self.service._parse_contact(props)
        assert contact is None

    @patch('requests.get')
    def test_get_shelters_in_radius_success(self, mock_get):
        """Test successful fetch of shelters in radius"""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            'features': [
                {
                    'properties': {
                        'id': '12345',
                        'name': 'Test Evacuation Center',
                        'type': 'Evacuation Center',
                        'address': '123 Main St',
                        'city': 'San Francisco',
                        'state': 'CA',
                        'zip': '94102',
                        'evac_cap': 5000,
                        'status': 'OPEN',
                        'telephone': '+1-415-555-1234'
                    },
                    'geometry': {
                        'coordinates': [-122.4194, 37.7749]
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        # Call service
        shelters = self.service.get_shelters_in_radius(37.7749, -122.4194, 25)

        # Verify
        assert len(shelters) == 1
        shelter = shelters[0]
        assert shelter['id'] == 'hifld_12345'
        assert shelter['name'] == 'Test Evacuation Center'
        assert shelter['type'] == 'evacuation_center'
        assert shelter['location']['latitude'] == 37.7749
        assert shelter['location']['longitude'] == -122.4194
        assert shelter['capacity'] == 5000
        assert shelter['operational_status'] == 'open'
        assert shelter['source'] == 'hifld_nss'

    @patch('requests.get')
    def test_get_shelters_in_radius_request_exception(self, mock_get):
        """Test handling of request exceptions"""
        mock_get.side_effect = Exception("Network error")

        shelters = self.service.get_shelters_in_radius(37.7749, -122.4194, 25)

        assert shelters == []

    @patch('requests.get')
    def test_get_shelters_in_bbox_success(self, mock_get):
        """Test successful fetch of shelters in bounding box"""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            'features': [
                {
                    'properties': {
                        'id': '54321',
                        'name': 'Oakland Shelter',
                        'type': 'Emergency Shelter',
                        'address': '456 Oak St',
                        'city': 'Oakland',
                        'state': 'CA',
                        'evac_cap': 3000,
                        'status': 'OPEN'
                    },
                    'geometry': {
                        'coordinates': [-122.2711, 37.8044]
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        # Call service with bounding box
        shelters = self.service.get_shelters_in_bbox(
            min_lat=37.0,
            max_lat=38.0,
            min_lon=-123.0,
            max_lon=-122.0
        )

        # Verify
        assert len(shelters) == 1
        shelter = shelters[0]
        assert shelter['id'] == 'hifld_54321'
        assert shelter['name'] == 'Oakland Shelter'
        assert shelter['type'] == 'emergency_shelter'

    @patch('requests.get')
    def test_parse_hifld_response_invalid_coordinates(self, mock_get):
        """Test that shelters with invalid coordinates are skipped"""
        # Mock response with invalid coordinates
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            'features': [
                {
                    'properties': {'SHELTER_ID': '99999', 'SHELTER_NAME': 'Invalid Shelter'},
                    'geometry': {'coordinates': []}  # Empty coordinates
                },
                {
                    'properties': {'SHELTER_ID': '88888', 'SHELTER_NAME': 'Out of Range'},
                    'geometry': {'coordinates': [200, 100]}  # Out of range
                }
            ]
        }
        mock_get.return_value = mock_response

        shelters = self.service.get_shelters_in_radius(37.7749, -122.4194, 25)

        # Both shelters should be skipped
        assert shelters == []

    def test_parse_hifld_response_handles_exceptions(self):
        """Test that parsing handles exceptions gracefully"""
        # Features with missing/malformed data
        features = [
            {
                'properties': {'SHELTER_ID': '12345'},
                'geometry': None  # Will cause exception
            }
        ]

        shelters = self.service._parse_hifld_response(features)

        # Should return empty list, not crash
        assert shelters == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
