"""
Cache Manager for Public Data Sources
Implements smart caching with Firebase to avoid API spam
"""
from datetime import datetime, timedelta
from firebase_admin import db
import json
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching of public data sources in Firebase"""

    # Cache durations in minutes
    CACHE_DURATIONS = {
        'wildfires': 30,        # 30 minutes - Check more frequently for updates
        'weather_alerts': 60,   # 1 hour - NOAA updates frequently
        'cal_fire': 30,         # 30 minutes - Cal Fire incident updates
        'earthquakes': 15,      # 15 minutes - USGS earthquake feed updates
        'fema_disasters': 360,  # 6 hours - FEMA declarations update infrequently
        'cal_oes_alerts': 30,   # 30 minutes - Cal OES RSS feed updates
        'gdacs_events': 60,     # 1 hour - GDACS RSS feed updates
        'safe_zones': 60,       # 1 hour - Safe zones change infrequently
        'hifld_shelters': 360,  # 6 hours - HIFLD shelters update infrequently (Phase 9)
    }

    @staticmethod
    def should_update(data_type):
        """
        Check if cached data needs updating based on timestamp

        Args:
            data_type (str): Type of data ('wildfires' or 'weather_alerts')

        Returns:
            bool: True if data should be updated
        """
        try:
            ref = db.reference(f'public_data_cache/{data_type}/metadata')
            metadata = ref.get()

            if not metadata or 'last_updated' not in metadata:
                return True

            last_updated = datetime.fromisoformat(metadata['last_updated'])
            cache_duration = timedelta(minutes=CacheManager.CACHE_DURATIONS.get(data_type, 60))

            return datetime.utcnow() - last_updated > cache_duration

        except Exception as e:
            logger.error(f"Error checking cache for {data_type}: {e}")
            return True  # Update on error

    @staticmethod
    def get_cached_data(data_type):
        """
        Get cached data from Firebase

        Args:
            data_type (str): Type of data ('wildfires' or 'weather_alerts')

        Returns:
            list: Cached data or empty list if not available
        """
        try:
            ref = db.reference(f'public_data_cache/{data_type}/data')
            data = ref.get()
            return data if data else []
        except Exception as e:
            logger.error(f"Error getting cached {data_type}: {e}")
            return []

    @staticmethod
    def update_cache(data_type, new_data):
        """
        Update cache with new data and metadata

        For wildfires: Replaces old data completely (reflects current FIRMS state)
        For weather alerts: Merges and removes expired alerts

        Args:
            data_type (str): Type of data ('wildfires' or 'weather_alerts')
            new_data (list): New data to cache
        """
        try:
            # For wildfires, replace data completely to match FIRMS state
            # (if fires are extinguished/removed from FIRMS, they should be removed here too)
            if data_type == 'wildfires':
                final_data = new_data
                logger.info(f"Replaced cache for {data_type}: {len(final_data)} items")
            else:
                # For weather alerts, merge and remove expired
                existing_data = CacheManager.get_cached_data(data_type)
                final_data = CacheManager._merge_data(existing_data, new_data, data_type)
                logger.info(f"Merged cache for {data_type}: {len(final_data)} items")

            # Update data reference
            data_ref = db.reference(f'public_data_cache/{data_type}/data')
            data_ref.set(final_data)

            # Update metadata
            metadata_ref = db.reference(f'public_data_cache/{data_type}/metadata')
            metadata_ref.set({
                'last_updated': datetime.utcnow().isoformat(),
                'count': len(final_data),
                'cache_duration_minutes': CacheManager.CACHE_DURATIONS.get(data_type, 60)
            })

        except Exception as e:
            logger.error(f"Error updating cache for {data_type}: {e}")

    @staticmethod
    def _merge_data(existing, new, data_type):
        """
        Merge existing and new data, avoiding duplicates

        Args:
            existing (list): Existing cached data
            new (list): New data to add
            data_type (str): Type of data

        Returns:
            list: Merged data without duplicates
        """
        if not existing:
            return new

        # Create set of existing IDs for fast lookup
        existing_ids = {item.get('id') for item in existing if item.get('id')}

        # Add only new items that don't exist
        merged = list(existing)
        new_items_count = 0

        for item in new:
            if item.get('id') not in existing_ids:
                merged.append(item)
                new_items_count += 1

        logger.info(f"Merged {data_type}: {len(existing)} existing + {new_items_count} new = {len(merged)} total")

        # For wildfires, remove old data (older than 2 days)
        if data_type == 'wildfires':
            merged = CacheManager._remove_old_wildfires(merged)

        # For weather alerts, remove expired alerts
        if data_type == 'weather_alerts':
            merged = CacheManager._remove_expired_alerts(merged)

        # For GDACS events, remove old events (older than 7 days)
        if data_type == 'gdacs_events':
            merged = CacheManager._remove_old_gdacs_events(merged)

        # For Cal Fire incidents, remove old incidents (older than 7 days)
        if data_type == 'cal_fire':
            merged = CacheManager._remove_old_cal_fire_incidents(merged)

        return merged

    @staticmethod
    def _remove_old_wildfires(wildfires):
        """Remove wildfire data older than 2 days"""
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=2)).date()

            filtered = []
            for fire in wildfires:
                acq_date = fire.get('acquisition_date', '')
                if acq_date:
                    fire_date = datetime.strptime(acq_date, '%Y-%m-%d').date()
                    if fire_date >= cutoff_date:
                        filtered.append(fire)
                else:
                    filtered.append(fire)  # Keep if no date

            logger.info(f"Removed {len(wildfires) - len(filtered)} old wildfires")
            return filtered

        except Exception as e:
            logger.error(f"Error removing old wildfires: {e}")
            return wildfires

    @staticmethod
    def _remove_expired_alerts(alerts):
        """Remove weather alerts that have expired"""
        try:
            now = datetime.utcnow()

            filtered = []
            for alert in alerts:
                expires = alert.get('expires', '')
                if expires:
                    try:
                        expires_dt = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                        if expires_dt > now:
                            filtered.append(alert)
                    except:
                        filtered.append(alert)  # Keep if can't parse
                else:
                    filtered.append(alert)  # Keep if no expiry

            logger.info(f"Removed {len(alerts) - len(filtered)} expired alerts")
            return filtered

        except Exception as e:
            logger.error(f"Error removing expired alerts: {e}")
            return alerts

    @staticmethod
    def _remove_old_gdacs_events(events):
        """Remove GDACS events older than 7 days"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=7)

            filtered = []
            for event in events:
                timestamp = event.get('timestamp', '')
                if timestamp:
                    try:
                        event_date = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        if event_date >= cutoff_date:
                            filtered.append(event)
                    except:
                        filtered.append(event)  # Keep if can't parse
                else:
                    filtered.append(event)  # Keep if no timestamp

            logger.info(f"Removed {len(events) - len(filtered)} old GDACS events")
            return filtered

        except Exception as e:
            logger.error(f"Error removing old GDACS events: {e}")
            return events

    @staticmethod
    def _remove_old_cal_fire_incidents(incidents):
        """Remove Cal Fire incidents older than 7 days"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=7)

            filtered = []
            for incident in incidents:
                timestamp = incident.get('timestamp', '')
                if timestamp:
                    try:
                        incident_date = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        if incident_date >= cutoff_date:
                            filtered.append(incident)
                    except:
                        filtered.append(incident)  # Keep if can't parse
                else:
                    filtered.append(incident)  # Keep if no timestamp

            logger.info(f"Removed {len(incidents) - len(filtered)} old Cal Fire incidents")
            return filtered

        except Exception as e:
            logger.error(f"Error removing old Cal Fire incidents: {e}")
            return incidents

    @staticmethod
    def clear_cache(data_type=None):
        """
        Clear cache for specific data type or all

        Args:
            data_type (str, optional): Type to clear, or None for all
        """
        try:
            if data_type:
                ref = db.reference(f'public_data_cache/{data_type}')
                ref.delete()
                logger.info(f"Cleared cache for {data_type}")
            else:
                ref = db.reference('public_data_cache')
                ref.delete()
                logger.info("Cleared all cache")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
