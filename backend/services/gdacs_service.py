"""
GDACS (Global Disaster Alert and Coordination System) Integration
Fetches major global disaster alerts from GDACS RSS feed
Documentation: https://www.gdacs.org/
"""
import feedparser
import requests
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)
from typing import List, Dict, Optional


class GDACSService:
    """Service to fetch global disaster alerts from GDACS"""

    RSS_URL = "https://www.gdacs.org/xml/rss.xml"

    def __init__(self, confidence_scorer=None):
        """
        Initialize GDACS service

        Args:
            confidence_scorer: Optional ConfidenceScorer instance for scoring events
        """
        self.headers = {
            'User-Agent': 'DisasterAlertSystem/1.0 (contact@example.com)',
            'Accept': 'application/rss+xml, application/xml, text/xml'
        }

        # Import confidence scorer to add scoring to events
        self.confidence_scorer = confidence_scorer
        if not self.confidence_scorer:
            # Lazy import to avoid circular dependency
            from services.confidence_scorer import ConfidenceScorer
            self.confidence_scorer = ConfidenceScorer()

    def fetch_recent_events(self, days: int = 3) -> List[Dict]:
        """
        Fetch major global disasters from GDACS RSS feed

        Args:
            days (int): Number of days to look back for recent events (default: 3)

        Returns:
            list: List of disaster event data points
        """
        try:
            logger.info(f"GDACS: Fetching events from RSS feed...")
            logger.info(f"GDACS: URL: {self.RSS_URL}")

            # Fetch RSS feed
            response = requests.get(
                self.RSS_URL,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            logger.info(f"GDACS: Status code: {response.status_code}")

            # Parse RSS feed
            feed = feedparser.parse(response.content)

            if not feed.entries:
                logger.info("GDACS: No entries found in RSS feed")
                return []

            logger.info(f"GDACS: Received {len(feed.entries)} total entries")

            # Parse and filter events
            events = self._parse_gdacs_rss(feed, days)
            logger.info(f"GDACS: Successfully parsed {len(events)} events from past {days} days")

            return events

        except requests.exceptions.RequestException as e:
            logger.error(f"GDACS ERROR: Request exception: {e}")
            import traceback
            traceback.print_exc()
            return []
        except Exception as e:
            logger.error(f"GDACS ERROR: Processing exception: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_cached_events(self, days: int = 3) -> List[Dict]:
        """
        Get GDACS events with caching support
        This method should be called from app.py with cache_manager integration

        Args:
            days (int): Number of days to look back for recent events

        Returns:
            list: List of disaster event data points
        """
        # This will be integrated with CacheManager in app.py
        return self.fetch_recent_events(days)

    def _parse_gdacs_rss(self, feed: feedparser.FeedParserDict, days: int = 3) -> List[Dict]:
        """
        Parse GDACS RSS feed and extract disaster event data

        Args:
            feed: Parsed feedparser object
            days (int): Number of days to filter recent events

        Returns:
            list: List of parsed event dictionaries
        """
        events = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        for entry in feed.entries:
            try:
                # Extract event data from entry
                event_data = self._extract_event_data(entry)

                if not event_data:
                    continue

                # Filter by date - only include events from past N days
                event_date = datetime.fromisoformat(event_data['timestamp'].replace('Z', '+00:00'))
                if event_date < cutoff_date:
                    continue

                # Add confidence scoring for this event
                if self.confidence_scorer:
                    try:
                        confidence_result = self.confidence_scorer.calculate_confidence(event_data)
                        event_data['confidence_score'] = confidence_result.get('confidence_score', 0.90)
                        event_data['confidence_level'] = confidence_result.get('confidence_level', 'High')
                        event_data['confidence_breakdown'] = confidence_result.get('breakdown', {})

                        # GDACS is official source - ensure high confidence (minimum 0.90)
                        if event_data['confidence_score'] < 0.90:
                            event_data['confidence_score'] = 0.90
                            event_data['confidence_level'] = 'High'
                    except Exception as e:
                        logger.warning(f" Confidence calculation failed for GDACS event {event_data.get('id')}: {e}")
                        # Default to high confidence for official source
                        event_data['confidence_score'] = 0.90
                        event_data['confidence_level'] = 'High'
                        event_data['confidence_breakdown'] = {
                            'source': 'gdacs',
                            'error_fallback': True,
                            'note': 'Official GDACS source - defaulted to high confidence after error'
                        }

                events.append(event_data)

            except Exception as e:
                logger.info(f"GDACS: Error parsing entry: {e}")
                continue

        return events

    def _extract_event_data(self, entry: feedparser.FeedParserDict) -> Optional[Dict]:
        """
        Extract structured event data from a GDACS RSS entry

        GDACS RSS format includes:
        - title: Event description
        - link: URL to event details
        - description: HTML description with details
        - pubDate: Publication date
        - gdacs:* fields: GDACS-specific metadata (eventtype, alertlevel, country, etc.)
        - geo:Point: Coordinates in "lat lon" format

        Args:
            entry: Single RSS entry from feedparser

        Returns:
            dict: Structured event data or None if parsing fails
        """
        try:
            # Extract coordinates from geo_lat and geo_long fields
            geo_lat = entry.get('geo_lat')
            geo_long = entry.get('geo_long')

            if not geo_lat or not geo_long:
                # Fallback: try geo:Point format
                geo_point = entry.get('georss_point', entry.get('geo_point', ''))
                if geo_point:
                    coords = geo_point.split()
                    if len(coords) == 2:
                        latitude = float(coords[0])
                        longitude = float(coords[1])
                    else:
                        logger.info(f"GDACS: No coordinates found for entry: {entry.get('title', 'Unknown')}")
                        return None
                else:
                    logger.info(f"GDACS: No coordinates found for entry: {entry.get('title', 'Unknown')}")
                    return None
            else:
                latitude = float(geo_lat)
                longitude = float(geo_long)

            # Validate coordinates
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                logger.info(f"GDACS: Invalid coordinates: lat={latitude}, lon={longitude}")
                return None

            # Extract GDACS-specific metadata
            gdacs_ns = entry.get('gdacs_', {})

            # Event type mapping (GDACS codes to our system)
            # EQ: Earthquake, TC: Tropical Cyclone, FL: Flood, VO: Volcano, DR: Drought
            event_type_map = {
                'EQ': 'earthquake',
                'TC': 'hurricane',  # Tropical cyclone
                'FL': 'flood',
                'VO': 'volcano',
                'DR': 'drought',
                'WF': 'wildfire'
            }

            gdacs_event_type = gdacs_ns.get('eventtype', entry.get('gdacs_eventtype', 'other'))
            event_type = event_type_map.get(gdacs_event_type.upper(), 'other')

            # Alert level mapping (Red/Orange/Green to severity)
            # Red: Most severe, Orange: Moderate, Green: Minor
            alert_level_map = {
                'Red': 'critical',
                'Orange': 'high',
                'Green': 'medium'
            }

            gdacs_alert_level = gdacs_ns.get('alertlevel', entry.get('gdacs_alertlevel', 'Green'))
            severity = alert_level_map.get(gdacs_alert_level, 'medium')

            # Extract magnitude/severity metrics
            magnitude = None
            severity_value = gdacs_ns.get('severity', entry.get('gdacs_severity'))
            if severity_value:
                try:
                    magnitude = float(severity_value.get('value', severity_value) if isinstance(severity_value, dict) else severity_value)
                except (ValueError, TypeError):
                    magnitude = None

            # Extract country
            country = gdacs_ns.get('country', entry.get('gdacs_country', 'Unknown'))

            # Parse timestamp
            published = entry.get('published', entry.get('pubDate', ''))
            if published:
                try:
                    # feedparser provides published_parsed (time.struct_time)
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        timestamp = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
                    else:
                        # Fallback to string parsing
                        timestamp = datetime.fromisoformat(published.replace('Z', '+00:00')).isoformat()
                except (ValueError, AttributeError, TypeError):
                    timestamp = datetime.now(timezone.utc).isoformat()
            else:
                timestamp = datetime.now(timezone.utc).isoformat()

            # Extract from_date (event start date)
            from_date = gdacs_ns.get('fromdate', entry.get('gdacs_fromdate', timestamp))

            # Create unique ID
            event_id = entry.get('id', entry.get('link', f"gdacs_{timestamp}_{latitude}_{longitude}"))

            # Build event dictionary
            event = {
                'id': event_id,
                'source': 'gdacs',
                'type': event_type,
                'severity': severity,
                'latitude': latitude,
                'longitude': longitude,
                'title': entry.get('title', 'GDACS Alert'),
                'description': entry.get('summary', entry.get('description', '')),
                'event_type_code': gdacs_event_type,  # Original GDACS code (EQ/TC/FL/VO)
                'alert_level': gdacs_alert_level,  # Red/Orange/Green
                'country': country,
                'magnitude': magnitude,
                'from_date': from_date,
                'timestamp': timestamp,
                'link': entry.get('link', '')
            }

            return event

        except Exception as e:
            logger.info(f"GDACS: Error extracting event data: {e}")
            import traceback
            traceback.print_exc()
            return None
