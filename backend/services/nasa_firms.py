"""
NASA FIRMS Wildfire Data Integration
Fetches active fire/thermal anomaly data from NASA's Fire Information for Resource Management System (FIRMS)
Documentation: https://firms.modaps.eosdis.nasa.gov/
"""
import requests
import os
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class NASAFirmsService:
    """Service to fetch wildfire data from NASA FIRMS"""

    # Use the Area API endpoint for precise geographic filtering
    BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area"

    def __init__(self, confidence_scorer=None):
        self.api_key = os.getenv('NASA_FIRMS_API_KEY')
        if not self.api_key:
            logger.warning("NASA_FIRMS_API_KEY not set. Wildfire data will not be available.")

        # Define precise bounding boxes for US 50 states only
        # Format: west,south,east,north (decimal degrees)
        # Single continental US box with conservative southern boundary
        self.us_bounding_boxes = [
            "-125,25.8,-66,49",    # Continental US (25.8°N to exclude Mexico)
            "-180,51,-130,72",     # Alaska
            "-160,18.5,-154,23"    # Hawaii (adjusted south to 18.5 to include Big Island)
        ]

        # Import confidence scorer to add scoring to wildfires
        self.confidence_scorer = confidence_scorer
        if not self.confidence_scorer:
            # Lazy import to avoid circular dependency
            from services.confidence_scorer import ConfidenceScorer
            self.confidence_scorer = ConfidenceScorer()

    def get_us_wildfires(self, days=5):
        """
        Fetch wildfire data for the United States from NASA FIRMS using Area API

        Args:
            days (int): Number of days of data to retrieve (1-10 supported by API, default 5)

        Returns:
            list: List of wildfire data points
        """
        if not self.api_key:
            logger.warning("NASA FIRMS: No API key configured")
            return []

        # Limit days to API maximum
        days = min(max(days, 1), 10)

        all_wildfires = []

        try:
            # Fetch data for each US region (Continental, Alaska, Hawaii)
            for bbox in self.us_bounding_boxes:
                # Use VIIRS S-NPP for best coverage and latest data
                # Format: /api/area/csv/[MAP_KEY]/VIIRS_SNPP_NRT/[AREA]/[DAYS]
                url = f"{self.BASE_URL}/csv/{self.api_key}/VIIRS_SNPP_NRT/{bbox}/{days}"

                logger.info(f"NASA FIRMS: Fetching from bounding box {bbox}")
                logger.info(f"NASA FIRMS: URL: {url}")

                response = requests.get(url, timeout=30)
                logger.info(f"NASA FIRMS: Status code: {response.status_code}")

                # Skip if no data for this region
                if response.status_code == 404:
                    logger.info(f"NASA FIRMS: No data for region {bbox}")
                    continue

                response.raise_for_status()

                # Parse CSV data
                csv_data = response.text.strip()

                if not csv_data or "Invalid" in csv_data:
                    logger.warning(f"NASA FIRMS: Invalid or empty data for region {bbox}")
                    continue

                lines = csv_data.split('\n')
                logger.info(f"NASA FIRMS: Received {len(lines)} lines for region {bbox}")

                if len(lines) < 2:
                    logger.warning(f"NASA FIRMS: Insufficient data for region {bbox}")
                    continue

                # Parse header (first line)
                header = lines[0].split(',')

                # Parse data rows
                for line in lines[1:]:
                    if not line.strip():
                        continue

                    values = line.split(',')
                    if len(values) < len(header):
                        continue

                    # Create dictionary from header and values
                    data = dict(zip(header, values))

                    try:
                        latitude = float(data.get('latitude', 0))
                        longitude = float(data.get('longitude', 0))
                    except (ValueError, TypeError):
                        continue

                    # Filter out Mexico fires using more accurate border
                    # US-Mexico border varies by longitude:
                    # - West (CA/AZ): ~32.5°N
                    # - New Mexico: ~32°N
                    # - Texas: slopes from ~31.8°N (west) to ~26°N (Gulf coast)
                    if not self._is_in_us(latitude, longitude):
                        continue

                    # Extract brightness and FRP for severity calculation
                    brightness = float(data.get('bright_ti4', 0)) if data.get('bright_ti4') else 0
                    frp = float(data.get('frp', 0)) if data.get('frp') else 0
                    timestamp = self._parse_timestamp(data.get('acq_date', ''), data.get('acq_time', ''))

                    # Extract and transform data to standard format
                    wildfire = {
                        'id': f"firms_{data.get('latitude', '')}_{data.get('longitude', '')}_{data.get('acq_date', '')}_{data.get('acq_time', '')}",
                        'source': 'nasa_firms',
                        'type': 'wildfire',
                        'latitude': latitude,
                        'longitude': longitude,
                        'brightness': brightness,
                        'scan': float(data.get('scan', 0)) if data.get('scan') else 0,
                        'track': float(data.get('track', 0)) if data.get('track') else 0,
                        'acquisition_date': data.get('acq_date', ''),
                        'acquisition_time': data.get('acq_time', ''),
                        'satellite': data.get('satellite', ''),
                        'confidence': data.get('confidence', ''),  # NASA's own confidence (n/l/h)
                        'version': data.get('version', ''),
                        'frp': frp,
                        'daynight': data.get('daynight', ''),
                        'timestamp': timestamp,
                        'severity': self._determine_severity(brightness, frp)
                    }

                    # Add confidence scoring for this wildfire
                    if self.confidence_scorer:
                        confidence_result = self.confidence_scorer.calculate_confidence(wildfire)
                        wildfire['confidence_score'] = confidence_result['confidence_score']
                        wildfire['confidence_level'] = confidence_result['confidence_level']
                        wildfire['confidence_breakdown'] = confidence_result['breakdown']

                    all_wildfires.append(wildfire)

            logger.info(f"NASA FIRMS: Successfully parsed {len(all_wildfires)} total wildfire detections across all regions")
            return all_wildfires

        except requests.exceptions.RequestException as e:
            logger.error(f"NASA FIRMS ERROR: Request exception: {e}", exc_info=True)
            return all_wildfires  # Return whatever we got so far
        except Exception as e:
            logger.error(f"NASA FIRMS ERROR: Processing exception: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            return all_wildfires  # Return whatever we got so far

    def _is_in_us(self, latitude, longitude):
        """
        Check if coordinates are within US territory (excluding Mexico)

        Handles continental US, Alaska, and Hawaii separately.
        US-Mexico border is not a straight line - it follows the Rio Grande in Texas
        and varies by longitude.

        Args:
            latitude (float): Latitude in decimal degrees
            longitude (float): Longitude in decimal degrees

        Returns:
            bool: True if coordinates are in US, False if in Mexico or outside bounds
        """
        # Alaska: -180 to -130°W, 51 to 72°N
        if -180 <= longitude <= -130 and 51 <= latitude <= 72:
            return True

        # Hawaii: -160 to -154°W, 18.5 to 23°N
        if -160 <= longitude <= -154 and 18.5 <= latitude <= 23:
            return True

        # Continental US - Mexico border varies by longitude
        # West of -114 (California/Arizona area)
        if longitude <= -114:
            # Actual border is ~32.534°N, use 32.53 to exclude close calls
            min_lat = 32.53
        elif longitude <= -108:
            # Arizona/New Mexico border area
            min_lat = 31.8
        elif longitude <= -106:
            # New Mexico/West Texas border area
            min_lat = 31.8
        elif longitude <= -103:
            # West Texas - border starts sloping down
            min_lat = 29.5
        elif longitude <= -100:
            # Central Texas - Rio Grande valley
            min_lat = 28.0
        else:
            # East Texas / Gulf Coast
            min_lat = 26.0

        # Check if continental US coordinates are north of Mexico border
        return latitude >= min_lat

    def _determine_severity(self, brightness, frp):
        """
        Determine wildfire severity from NASA FIRMS metrics

        Args:
            brightness (float): Brightness temperature in Kelvin
            frp (float): Fire Radiative Power in MW

        Returns:
            str: Severity level ('low', 'medium', 'high', 'critical')
        """
        # Use both brightness and FRP to determine severity
        # Higher values indicate more intense fires
        if brightness > 360 or frp > 100:
            return 'critical'
        elif brightness > 340 or frp > 50:
            return 'high'
        elif brightness > 320 or frp > 20:
            return 'medium'
        else:
            return 'low'

    def _parse_timestamp(self, date_str, time_str):
        """
        Parse FIRMS date and time into ISO timestamp with UTC timezone

        Args:
            date_str (str): Date in YYYY-MM-DD format
            time_str (str): Time in HHMM format

        Returns:
            str: ISO 8601 timestamp with timezone
        """
        try:
            # Pad time to 4 digits if needed
            time_str = time_str.zfill(4)

            # Parse date and time
            dt_str = f"{date_str} {time_str[:2]}:{time_str[2:]}"
            dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')

            # Make timezone-aware (FIRMS data is in UTC)
            dt = dt.replace(tzinfo=timezone.utc)

            return dt.isoformat()
        except Exception:
            return datetime.now(timezone.utc).isoformat()
