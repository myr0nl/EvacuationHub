"""
Tests for SafeZoneService
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from services.safe_zone_service import SafeZoneService


class TestSafeZoneService:
    """Test cases for SafeZoneService"""

    @pytest.fixture
    def mock_db(self):
        """Create mock Firebase database"""
        return Mock()

    @pytest.fixture
    def safe_zone_service(self, mock_db):
        """Create SafeZoneService instance with mocked database"""
        return SafeZoneService(mock_db)

    @pytest.fixture
    def sample_zones(self):
        """Sample safe zone data"""
        return {
            'sz_001': {
                'name': 'Test Evacuation Center',
                'type': 'evacuation_center',
                'location': {'latitude': 37.7749, 'longitude': -122.4194},
                'address': '123 Main St',
                'capacity': 5000,
                'operational_status': 'open'
            },
            'sz_002': {
                'name': 'Test Hospital',
                'type': 'hospital',
                'location': {'latitude': 37.7849, 'longitude': -122.4094},
                'address': '456 Hospital Rd',
                'capacity': 3000,
                'operational_status': 'open'
            },
            'sz_003': {
                'name': 'Far Away Shelter',
                'type': 'emergency_shelter',
                'location': {'latitude': 38.0000, 'longitude': -122.0000},
                'address': '789 Distant Ave',
                'capacity': 2000,
                'operational_status': 'closed'
            }
        }

    def test_get_nearest_safe_zones_basic(self, safe_zone_service, mock_db, sample_zones):
        """Test basic nearest safe zones functionality"""
        # Mock Firebase response
        mock_ref = Mock()
        mock_ref.get.return_value = sample_zones
        mock_db.reference.return_value = mock_ref

        # Get nearest zones
        result = safe_zone_service.get_nearest_safe_zones(37.7749, -122.4194, limit=3)

        # Verify results are sorted by distance
        assert len(result) == 3
        assert result[0]['id'] == 'sz_001'  # Closest (same location)
        assert result[0]['distance_from_user_mi'] == 0.0
        assert result[1]['distance_from_user_mi'] > 0

    def test_get_nearest_safe_zones_with_limit(self, safe_zone_service, mock_db, sample_zones):
        """Test limit parameter"""
        mock_ref = Mock()
        mock_ref.get.return_value = sample_zones
        mock_db.reference.return_value = mock_ref

        result = safe_zone_service.get_nearest_safe_zones(37.7749, -122.4194, limit=2)

        assert len(result) <= 2

    def test_get_nearest_safe_zones_with_type_filter(self, safe_zone_service, mock_db, sample_zones):
        """Test filtering by zone type"""
        mock_ref = Mock()
        mock_ref.get.return_value = sample_zones
        mock_db.reference.return_value = mock_ref

        result = safe_zone_service.get_nearest_safe_zones(
            37.7749, -122.4194,
            limit=5,
            zone_types=['hospital']
        )

        # Should only return hospitals
        assert all(zone['type'] == 'hospital' for zone in result)

    def test_get_nearest_safe_zones_invalid_coordinates(self, safe_zone_service):
        """Test with invalid coordinates"""
        with pytest.raises(ValueError):
            safe_zone_service.get_nearest_safe_zones(999, -122.4194)

    def test_get_nearest_safe_zones_no_zones_in_db(self, safe_zone_service, mock_db):
        """Test when no zones exist in database"""
        mock_ref = Mock()
        mock_ref.get.return_value = None
        mock_db.reference.return_value = mock_ref

        result = safe_zone_service.get_nearest_safe_zones(37.7749, -122.4194)

        assert result == []

    def test_is_zone_safe_no_threats(self, safe_zone_service, mock_db, sample_zones):
        """Test zone safety check with no nearby disasters"""
        # Mock get_zone_by_id
        with patch.object(safe_zone_service, 'get_zone_by_id', return_value=sample_zones['sz_001']):
            # Empty disaster list
            result = safe_zone_service.is_zone_safe('sz_001', [])

            assert result['safe'] is True
            assert result['threats'] == []
            assert result['distance_to_nearest_threat_mi'] is None

    def test_is_zone_safe_with_threats(self, safe_zone_service, mock_db, sample_zones):
        """Test zone safety check with nearby disasters"""
        # Mock get_zone_by_id
        with patch.object(safe_zone_service, 'get_zone_by_id', return_value=sample_zones['sz_001']):
            # Disaster very close to zone (within 5km)
            disasters = [
                {
                    'id': 'disaster_001',
                    'type': 'wildfire',
                    'severity': 'critical',
                    'latitude': 37.7750,  # Very close
                    'longitude': -122.4195
                }
            ]

            result = safe_zone_service.is_zone_safe('sz_001', disasters, threat_radius_mi=3.1)

            assert result['safe'] is False
            assert 'disaster_001' in result['threats']
            assert result['distance_to_nearest_threat_mi'] < 1.0

    def test_get_zone_by_id_success(self, safe_zone_service, mock_db, sample_zones):
        """Test retrieving zone by ID"""
        mock_ref = Mock()
        mock_ref.get.return_value = sample_zones['sz_001']
        mock_db.reference.return_value = mock_ref

        result = safe_zone_service.get_zone_by_id('sz_001')

        assert result is not None
        assert result['id'] == 'sz_001'
        assert result['name'] == 'Test Evacuation Center'

    def test_get_zone_by_id_not_found(self, safe_zone_service, mock_db):
        """Test retrieving non-existent zone"""
        mock_ref = Mock()
        mock_ref.get.return_value = None
        mock_db.reference.return_value = mock_ref

        result = safe_zone_service.get_zone_by_id('nonexistent')

        assert result is None

    def test_update_zone_status_success(self, safe_zone_service, mock_db):
        """Test updating zone status"""
        mock_ref = Mock()
        mock_ref.get.return_value = {'name': 'Test Zone'}  # Zone exists
        mock_db.reference.return_value = mock_ref

        result = safe_zone_service.update_zone_status('sz_001', 'closed', 'Flooding nearby')

        assert result is True
        mock_ref.update.assert_called_once()

    def test_update_zone_status_invalid_status(self, safe_zone_service):
        """Test updating with invalid status"""
        with pytest.raises(ValueError):
            safe_zone_service.update_zone_status('sz_001', 'invalid_status')

    def test_create_safe_zone_success(self, safe_zone_service, mock_db):
        """Test creating a new safe zone"""
        mock_ref = Mock()
        mock_db.reference.return_value = mock_ref

        zone_data = {
            'name': 'New Evacuation Center',
            'type': 'evacuation_center',
            'location': {'latitude': 37.7749, 'longitude': -122.4194},
            'address': '999 New St',
            'capacity': 4000
        }

        result = safe_zone_service.create_safe_zone(zone_data)

        assert result is not None
        assert result.startswith('sz_')
        mock_ref.set.assert_called_once()

    def test_create_safe_zone_missing_required_field(self, safe_zone_service):
        """Test creating zone with missing required field"""
        zone_data = {
            'name': 'Incomplete Zone',
            # Missing 'type' and 'location'
        }

        with pytest.raises(ValueError, match='Missing required field'):
            safe_zone_service.create_safe_zone(zone_data)

    def test_create_safe_zone_invalid_coordinates(self, safe_zone_service):
        """Test creating zone with invalid coordinates"""
        zone_data = {
            'name': 'Bad Location Zone',
            'type': 'evacuation_center',
            'location': {'latitude': 999, 'longitude': -122.4194}
        }

        with pytest.raises(ValueError, match='Invalid location coordinates'):
            safe_zone_service.create_safe_zone(zone_data)

    def test_get_all_zones(self, safe_zone_service, mock_db, sample_zones):
        """Test retrieving all zones"""
        mock_ref = Mock()
        mock_ref.get.return_value = sample_zones
        mock_db.reference.return_value = mock_ref

        result = safe_zone_service.get_all_zones()

        assert len(result) == 3
        assert all('id' in zone for zone in result)

    def test_seed_default_safe_zones(self, safe_zone_service, mock_db):
        """Test seeding default zones"""
        mock_ref = Mock()
        mock_db.reference.return_value = mock_ref

        # Mock create_safe_zone to return success
        with patch.object(safe_zone_service, 'create_safe_zone', return_value='sz_new'):
            count = safe_zone_service.seed_default_safe_zones()

            # Should create 5 default zones
            assert count == 5
