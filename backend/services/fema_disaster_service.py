"""
FEMA Disaster Declarations Integration
Fetches official disaster declarations from FEMA's OpenFEMA API v2
Documentation: https://www.fema.gov/about/openfema/data-sets
"""
import requests
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


class FEMADisasterService:
    """Service to fetch disaster declarations from FEMA OpenFEMA API"""

    BASE_URL = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"

    def __init__(self, confidence_scorer=None):
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': 'DisasterAlertSystem/1.0'
        }

        # Import confidence scorer to add scoring to disasters
        self.confidence_scorer = confidence_scorer
        if not self.confidence_scorer:
            # Lazy import to avoid circular dependency
            from services.confidence_scorer import ConfidenceScorer
            self.confidence_scorer = ConfidenceScorer()

    def get_recent_disasters(self, days=30):
        """
        Fetch recent FEMA disaster declarations

        Args:
            days (int): Number of days of data to retrieve (default 30)

        Returns:
            list: List of FEMA disaster declaration data points
        """
        try:
            # Calculate cutoff date for filtering
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')

            # Build API URL with filters
            # Filter by declarationDate >= cutoff_date and limit to US 50 states
            # API supports $filter parameter with OData-style queries
            params = {
                '$filter': f"declarationDate ge '{cutoff_date}T00:00:00.000z'",
                '$orderby': 'declarationDate desc',
                '$top': 1000  # Maximum records per request
            }

            logger.info(f"FEMA: Fetching disaster declarations from past {days} days")
            logger.info(f"FEMA: URL: {self.BASE_URL}")
            logger.info(f"FEMA: Filter: {params['$filter']}")

            response = requests.get(
                self.BASE_URL,
                params=params,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            declarations = data.get('DisasterDeclarationsSummaries', [])

            logger.info(f"FEMA: Received {len(declarations)} disaster declarations")

            # Parse and transform data
            disasters = self._parse_fema_response(declarations)

            logger.info(f"FEMA: Successfully parsed {len(disasters)} disaster declarations")
            return disasters

        except requests.exceptions.RequestException as e:
            logger.error(f"FEMA ERROR: Request exception: {e}")
            return []
        except Exception as e:
            logger.error(f"FEMA ERROR: Processing exception: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            return []

    def _parse_fema_response(self, declarations):
        """
        Parse FEMA API response and transform to standard format

        Args:
            declarations (list): Raw FEMA API response data

        Returns:
            list: Transformed disaster data
        """
        disasters = []

        for declaration in declarations:
            try:
                # Extract basic information
                disaster_number = declaration.get('disasterNumber')
                state = declaration.get('state', '')
                incident_type = declaration.get('incidentType', '')
                title = declaration.get('declarationTitle', '')
                declaration_date = declaration.get('declarationDate', '')

                # Map FEMA incident type to our disaster types
                disaster_type = self._map_disaster_type(incident_type)

                # Skip if we can't map the disaster type
                if not disaster_type:
                    continue

                # Filter to US 50 states only (exclude territories)
                if not self._is_us_state(state):
                    continue

                # Get coordinates if available
                # FEMA API may include placeCode (FIPS code) but not always lat/lon
                # We'll try to extract from designatedArea or use state centroid
                latitude, longitude = self._get_coordinates(declaration)

                # Skip if no coordinates available
                if not latitude or not longitude:
                    continue

                # Parse timestamp with timezone awareness
                timestamp = self._parse_timestamp(declaration_date)

                # Determine severity based on incident type and declaration type
                severity = self._determine_severity(declaration)

                # Create disaster object
                disaster = {
                    'id': f"fema_{disaster_number}_{state}",
                    'source': 'fema',
                    'type': disaster_type,
                    'disaster_number': disaster_number,
                    'state': state,
                    'incident_type': incident_type,
                    'title': title,
                    'declaration_date': declaration_date,
                    'declaration_type': declaration.get('declarationType', ''),
                    'latitude': latitude,
                    'longitude': longitude,
                    'severity': severity,
                    'timestamp': timestamp
                }

                # Add confidence scoring for this disaster
                if self.confidence_scorer:
                    confidence_result = self.confidence_scorer.calculate_confidence(disaster)
                    disaster['confidence_score'] = confidence_result['confidence_score']
                    disaster['confidence_level'] = confidence_result['confidence_level']
                    disaster['confidence_breakdown'] = confidence_result['breakdown']
                else:
                    # Default high confidence for official FEMA source
                    disaster['confidence_score'] = 0.95
                    disaster['confidence_level'] = 'High'

                disasters.append(disaster)

            except Exception as e:
                logger.warning(f"FEMA: Error parsing declaration {declaration.get('disasterNumber')}: {e}")
                continue

        return disasters

    def _map_disaster_type(self, fema_type):
        """
        Map FEMA incident type to our disaster type schema

        Args:
            fema_type (str): FEMA incident type

        Returns:
            str: Mapped disaster type or None if not mappable
        """
        # FEMA incident types to our types mapping
        type_mapping = {
            'Fire': 'wildfire',
            'Wildfire': 'wildfire',
            'Flood': 'flood',
            'Flooding': 'flood',
            'Hurricane': 'hurricane',
            'Typhoon': 'hurricane',
            'Tropical Storm': 'hurricane',
            'Tropical Depression': 'hurricane',
            'Earthquake': 'earthquake',
            'Severe Storm': 'other',
            'Severe Storm(s)': 'other',
            'Tornado': 'tornado',
            'Tornadoes': 'tornado',
            'Winter Storm': 'other',
            'Snowstorm': 'other',
            'Severe Ice Storm': 'other',
            'Ice Storm': 'other',
            'Coastal Storm': 'other',
            'Tsunami': 'flood',
            'Drought': 'other',
            'Dam/Levee Break': 'flood',
            'Mudslide': 'flood',
            'Landslide': 'flood',
            'Volcano': 'other'
        }

        # Try exact match first
        if fema_type in type_mapping:
            return type_mapping[fema_type]

        # Try case-insensitive partial match
        fema_type_lower = fema_type.lower()
        for key, value in type_mapping.items():
            if key.lower() in fema_type_lower:
                return value

        # Default to 'other' if no match found
        logger.info(f"FEMA: Unknown incident type '{fema_type}', mapping to 'other'")
        return 'other'

    def _get_coordinates(self, declaration):
        """
        Extract coordinates from FEMA declaration
        Uses state centroid as fallback since FEMA API doesn't always provide precise coordinates

        Args:
            declaration (dict): FEMA declaration object

        Returns:
            tuple: (latitude, longitude) or (None, None)
        """
        # FEMA API typically doesn't include lat/lon in the main response
        # Use state centroid as representative location
        state = declaration.get('state', '')
        return self._get_state_centroid(state)

    def _get_state_centroid(self, state_code):
        """
        Get approximate centroid coordinates for US state

        Args:
            state_code (str): Two-letter state code

        Returns:
            tuple: (latitude, longitude) or (None, None)
        """
        # US state centroids (approximate)
        state_centroids = {
            'AL': (32.806671, -86.791130),    # Alabama
            'AK': (61.370716, -152.404419),   # Alaska
            'AZ': (33.729759, -111.431221),   # Arizona
            'AR': (34.969704, -92.373123),    # Arkansas
            'CA': (36.116203, -119.681564),   # California
            'CO': (39.059811, -105.311104),   # Colorado
            'CT': (41.597782, -72.755371),    # Connecticut
            'DE': (39.318523, -75.507141),    # Delaware
            'FL': (27.766279, -81.686783),    # Florida
            'GA': (33.040619, -83.643074),    # Georgia
            'HI': (21.094318, -157.498337),   # Hawaii
            'ID': (44.240459, -114.478828),   # Idaho
            'IL': (40.349457, -88.986137),    # Illinois
            'IN': (39.849426, -86.258278),    # Indiana
            'IA': (42.011539, -93.210526),    # Iowa
            'KS': (38.526600, -96.726486),    # Kansas
            'KY': (37.668140, -84.670067),    # Kentucky
            'LA': (31.169546, -91.867805),    # Louisiana
            'ME': (44.693947, -69.381927),    # Maine
            'MD': (39.063946, -76.802101),    # Maryland
            'MA': (42.230171, -71.530106),    # Massachusetts
            'MI': (43.326618, -84.536095),    # Michigan
            'MN': (45.694454, -93.900192),    # Minnesota
            'MS': (32.741646, -89.678696),    # Mississippi
            'MO': (38.456085, -92.288368),    # Missouri
            'MT': (46.921925, -110.454353),   # Montana
            'NE': (41.125370, -98.268082),    # Nebraska
            'NV': (38.313515, -117.055374),   # Nevada
            'NH': (43.452492, -71.563896),    # New Hampshire
            'NJ': (40.298904, -74.521011),    # New Jersey
            'NM': (34.840515, -106.248482),   # New Mexico
            'NY': (42.165726, -74.948051),    # New York
            'NC': (35.630066, -79.806419),    # North Carolina
            'ND': (47.528912, -99.784012),    # North Dakota
            'OH': (40.388783, -82.764915),    # Ohio
            'OK': (35.565342, -96.928917),    # Oklahoma
            'OR': (44.572021, -122.070938),   # Oregon
            'PA': (40.590752, -77.209755),    # Pennsylvania
            'RI': (41.680893, -71.511780),    # Rhode Island
            'SC': (33.856892, -80.945007),    # South Carolina
            'SD': (44.299782, -99.438828),    # South Dakota
            'TN': (35.747845, -86.692345),    # Tennessee
            'TX': (31.054487, -97.563461),    # Texas
            'UT': (40.150032, -111.862434),   # Utah
            'VT': (44.045876, -72.710686),    # Vermont
            'VA': (37.769337, -78.169968),    # Virginia
            'WA': (47.400902, -121.490494),   # Washington
            'WV': (38.491226, -80.954453),    # West Virginia
            'WI': (44.268543, -89.616508),    # Wisconsin
            'WY': (42.755966, -107.302490)    # Wyoming
        }

        coords = state_centroids.get(state_code)
        if coords:
            return coords[0], coords[1]

        return None, None

    def _is_us_state(self, state_code):
        """
        Check if state code is a US 50 state (exclude territories)

        Args:
            state_code (str): Two-letter state code

        Returns:
            bool: True if US 50 state, False otherwise
        """
        us_50_states = {
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
        }
        return state_code in us_50_states

    def _determine_severity(self, declaration):
        """
        Determine disaster severity from FEMA declaration data

        Args:
            declaration (dict): FEMA declaration object

        Returns:
            str: Severity level ('low', 'medium', 'high', 'critical')
        """
        # Major disaster declarations are typically more severe than emergency declarations
        declaration_type = declaration.get('declarationType', '').lower()
        incident_type = declaration.get('incidentType', '').lower()

        # Critical incidents
        critical_keywords = ['hurricane', 'earthquake', 'tsunami', 'volcano']
        if any(keyword in incident_type for keyword in critical_keywords):
            return 'critical'

        # Major disasters are high severity
        if 'major disaster' in declaration_type or 'dr' in declaration_type:
            return 'high'

        # Fire/wildfire severity
        if 'fire' in incident_type:
            return 'high'

        # Emergency declarations are medium severity
        if 'emergency' in declaration_type or 'em' in declaration_type:
            return 'medium'

        # Default to medium for other declarations
        return 'medium'

    def _parse_timestamp(self, date_str):
        """
        Parse FEMA date string into ISO timestamp with UTC timezone

        Args:
            date_str (str): Date string from FEMA API

        Returns:
            str: ISO 8601 timestamp with timezone
        """
        try:
            # FEMA dates are typically in ISO format: 2024-01-15T00:00:00.000z
            if date_str:
                # Parse the date string and make it timezone-aware
                dt = datetime.fromisoformat(date_str.replace('z', '+00:00').replace('Z', '+00:00'))
                return dt.isoformat()
        except Exception:
            pass

        # Fallback to current time
        return datetime.now(timezone.utc).isoformat()
