"""
Cal OES Emergency Alerts Integration
Fetches California emergency alerts from Cal OES RSS feed
Documentation: https://news.caloes.ca.gov/feed
"""
import feedparser
import logging

logger = logging.getLogger(__name__)
import hashlib
from datetime import datetime, timezone
from services.cache_manager import CacheManager


class CalOESService:
    """Service to fetch emergency alerts from California Governor's Office of Emergency Services"""

    RSS_FEED_URL = "https://news.caloes.ca.gov/feed"
    CACHE_TYPE = "cal_oes_alerts"

    def __init__(self, confidence_scorer=None):
        """
        Initialize Cal OES service

        Args:
            confidence_scorer: Optional ConfidenceScorer instance for alert scoring
        """
        # Import confidence scorer to add scoring to alerts
        self.confidence_scorer = confidence_scorer
        if not self.confidence_scorer:
            # Lazy import to avoid circular dependency
            from services.confidence_scorer import ConfidenceScorer
            self.confidence_scorer = ConfidenceScorer()

    def get_cached_alerts(self):
        """
        Get Cal OES alerts from cache or fetch fresh data if cache expired

        Returns:
            list: List of Cal OES alert data points
        """
        try:
            # Check if cache needs updating (30 minute TTL)
            if CacheManager.should_update(self.CACHE_TYPE):
                logger.info(f"Cal OES: Cache expired or missing, fetching fresh data")
                fresh_alerts = self.fetch_recent_alerts()

                # Update cache with new data
                CacheManager.update_cache(self.CACHE_TYPE, fresh_alerts)
                return fresh_alerts
            else:
                # Return cached data
                logger.info(f"Cal OES: Using cached data")
                cached_data = CacheManager.get_cached_data(self.CACHE_TYPE)
                return cached_data if cached_data else []

        except Exception as e:
            logger.error(f"Cal OES ERROR: Failed to get cached alerts: {e}")
            # Try to return cached data on error
            try:
                cached_data = CacheManager.get_cached_data(self.CACHE_TYPE)
                return cached_data if cached_data else []
            except Exception:
                return []

    def fetch_recent_alerts(self):
        """
        Fetch recent emergency alerts from Cal OES RSS feed

        Returns:
            list: List of parsed alert data points with confidence scores
        """
        try:
            logger.info(f"Cal OES: Fetching RSS feed from {self.RSS_FEED_URL}")
            feed = feedparser.parse(self.RSS_FEED_URL)

            if hasattr(feed, 'bozo') and feed.bozo:
                logger.warning(f"Cal OES WARNING: RSS feed parse error: {feed.bozo_exception}")
                # Continue anyway - feedparser often succeeds despite warnings

            alerts = self._parse_rss_feed(feed)
            logger.info(f"Cal OES: Successfully parsed {len(alerts)} alerts")

            return alerts

        except Exception as e:
            logger.error(f"Cal OES ERROR: Failed to fetch RSS feed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_rss_feed(self, feed):
        """
        Parse RSS feed entries into standardized alert format

        Args:
            feed: Parsed feedparser feed object

        Returns:
            list: List of alert dictionaries
        """
        alerts = []

        try:
            entries = feed.get('entries', [])
            logger.info(f"Cal OES: Processing {len(entries)} RSS entries")

            for entry in entries:
                try:
                    # Generate unique ID from link hash
                    link = entry.get('link', '')
                    alert_id = f"caloes_{self._generate_id_hash(link)}"

                    # Extract publication date
                    pub_date = self._parse_pub_date(entry)

                    # Extract title and description
                    title = entry.get('title', 'Cal OES Alert')
                    description = entry.get('summary', entry.get('description', ''))

                    # Determine disaster type and severity from title/description
                    alert_type, severity = self._classify_alert(title, description)

                    # Get coordinates (Cal OES covers California, use state centroid as default)
                    # California geographic center: approximately 37°N, 119.5°W
                    latitude, longitude = self._extract_coordinates(entry, title, description)

                    # Build alert object
                    alert = {
                        'id': alert_id,
                        'source': 'cal_oes',
                        'type': alert_type,
                        'title': title,
                        'description': description,
                        'pub_date': pub_date,
                        'link': link,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'latitude': latitude,
                        'longitude': longitude,
                        'severity': severity
                    }

                    # Add confidence scoring
                    if self.confidence_scorer:
                        try:
                            confidence_result = self.confidence_scorer.calculate_confidence(alert)
                            alert['confidence_score'] = confidence_result.get('confidence_score', 0.95)
                            alert['confidence_level'] = confidence_result.get('confidence_level', 'High')
                            alert['confidence_breakdown'] = confidence_result.get('breakdown', {})

                            # Default to high confidence for official Cal OES source
                            if alert['confidence_score'] is None or alert['confidence_score'] < 0.90:
                                alert['confidence_score'] = 0.95
                                alert['confidence_level'] = 'High'
                                alert['confidence_breakdown'] = {
                                    'source': 'cal_oes',
                                    'official_source': True,
                                    'note': 'Official California emergency management - high confidence'
                                }
                        except Exception as e:
                            # Default to high confidence on error for official source
                            logger.warning(f"Cal OES WARNING: Confidence calculation failed for {alert_id}: {e}")
                            alert['confidence_score'] = 0.95
                            alert['confidence_level'] = 'High'
                            alert['confidence_breakdown'] = {
                                'source': 'cal_oes',
                                'error_fallback': True,
                                'note': 'Official California emergency management - defaulted to high confidence'
                            }
                    else:
                        # No confidence scorer available
                        alert['confidence_score'] = 0.95
                        alert['confidence_level'] = 'High'

                    alerts.append(alert)

                except Exception as e:
                    logger.error(f"Cal OES ERROR: Failed to parse RSS entry: {e}")
                    continue

        except Exception as e:
            logger.error(f"Cal OES ERROR: Failed to parse RSS feed: {e}")
            import traceback
            traceback.print_exc()

        return alerts

    def _generate_id_hash(self, text):
        """
        Generate short hash from text for ID generation

        Args:
            text (str): Text to hash

        Returns:
            str: First 12 characters of SHA-256 hash
        """
        if not text:
            text = str(datetime.now(timezone.utc).timestamp())
        return hashlib.sha256(text.encode()).hexdigest()[:12]

    def _parse_pub_date(self, entry):
        """
        Parse publication date from RSS entry

        Args:
            entry: RSS feed entry object

        Returns:
            str: ISO 8601 formatted timestamp
        """
        try:
            # Try published_parsed first
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                return dt.isoformat()

            # Try updated_parsed
            if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                return dt.isoformat()

            # Fallback to current time
            return datetime.now(timezone.utc).isoformat()

        except Exception:
            return datetime.now(timezone.utc).isoformat()

    def _classify_alert(self, title, description):
        """
        Classify alert type and severity from title and description

        Args:
            title (str): Alert title
            description (str): Alert description

        Returns:
            tuple: (alert_type, severity)
        """
        combined_text = f"{title} {description}".lower()

        # Disaster type classification
        alert_type = 'emergency'  # Default type

        if any(keyword in combined_text for keyword in ['wildfire', 'fire', 'smoke', 'burn']):
            alert_type = 'wildfire'
        elif any(keyword in combined_text for keyword in ['earthquake', 'seismic', 'tremor']):
            alert_type = 'earthquake'
        elif any(keyword in combined_text for keyword in ['flood', 'flooding', 'tsunami', 'storm surge']):
            alert_type = 'flood'
        elif any(keyword in combined_text for keyword in ['hurricane', 'tornado', 'storm', 'typhoon']):
            alert_type = 'storm'
        elif any(keyword in combined_text for keyword in ['drought', 'water shortage']):
            alert_type = 'drought'
        elif any(keyword in combined_text for keyword in ['landslide', 'mudslide']):
            alert_type = 'landslide'

        # Severity classification
        severity = 'medium'  # Default severity

        if any(keyword in combined_text for keyword in ['critical', 'extreme', 'emergency', 'evacuat', 'life-threatening', 'imminent']):
            severity = 'critical'
        elif any(keyword in combined_text for keyword in ['severe', 'major', 'significant', 'urgent', 'warning']):
            severity = 'high'
        elif any(keyword in combined_text for keyword in ['moderate', 'watch', 'advisory']):
            severity = 'medium'
        elif any(keyword in combined_text for keyword in ['minor', 'low', 'information']):
            severity = 'low'

        return alert_type, severity

    def _extract_coordinates(self, entry, title, description):
        """
        Extract coordinates from RSS entry or estimate from location mentions

        Args:
            entry: RSS feed entry
            title (str): Alert title
            description (str): Alert description

        Returns:
            tuple: (latitude, longitude)
        """
        # Check if entry has geo coordinates
        if hasattr(entry, 'geo_lat') and hasattr(entry, 'geo_long'):
            try:
                return float(entry.geo_lat), float(entry.geo_long)
            except (ValueError, TypeError):
                pass

        # Check for georss point
        if hasattr(entry, 'georss_point'):
            try:
                coords = entry.georss_point.split()
                if len(coords) == 2:
                    return float(coords[0]), float(coords[1])
            except (ValueError, TypeError, AttributeError):
                pass

        # Default to California geographic center
        # (Cal OES covers all of California)
        return 37.0, -119.5

    def _is_california_location(self, latitude, longitude):
        """
        Check if coordinates are within California boundaries

        Args:
            latitude (float): Latitude
            longitude (float): Longitude

        Returns:
            bool: True if within California boundaries
        """
        # California bounding box (more accurate to exclude Nevada/Arizona/Mexico)
        # North: 42°N (Oregon border)
        # South: 32.53°N (Mexico border - precise US border latitude)
        # West: -124.5°W (Pacific coast)
        # East: -114.1°W (Arizona/Nevada border at south, -120°W at north)

        # Basic bounding box check
        if not (32.53 <= latitude <= 42.0 and -124.5 <= longitude <= -114.1):
            return False

        # California's eastern border follows longitude more closely at different latitudes:
        # - Southern California (below 36°N): -114.1°W
        # - Central/Northern California (above 36°N): -120°W
        # This excludes Nevada (Las Vegas, Reno) and Arizona
        if latitude >= 36.0 and longitude > -120.0:
            return False

        return True
