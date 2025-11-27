import os
import json
import time
from typing import Optional, Tuple, Dict
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from sqlalchemy.orm import Session
from backend.db.models import CanonicalEntity

CACHE_FILE = os.path.join(os.path.dirname(__file__), "geocoding_cache.json")


class GeocodingService:
    def __init__(self, user_agent: str = "ArkhamMirror/0.3"):
        self.geolocator = Nominatim(user_agent=user_agent)
        self.cache = self._load_cache()
        self.last_request_time = 0
        self.min_delay = 1.1  # Nominatim requires 1 request per second max

    def _load_cache(self) -> Dict[str, dict]:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load geocoding cache: {e}")
                return {}
        return {}

    def _save_cache(self):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save geocoding cache: {e}")

    def _rate_limit(self):
        """Ensure we don't hit the API too fast."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request_time = time.time()

    def geocode(self, query: str) -> Optional[Dict[str, float]]:
        """
        Geocode a query string (e.g., "Paris, France").
        Returns dict with lat, lon, address, or None if not found.
        """
        if not query:
            return None

        # Check cache
        if query in self.cache:
            return self.cache[query]

        self._rate_limit()

        try:
            print(f"🌍 Geocoding: {query}...")
            location = self.geolocator.geocode(query, language="en")

            if location:
                result = {
                    "lat": location.latitude,
                    "lon": location.longitude,
                    "address": location.address,
                }
                self.cache[query] = result
                self._save_cache()
                return result
            else:
                # Cache negative results too to avoid retrying
                self.cache[query] = None
                self._save_cache()
                return None

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"❌ Geocoding error for '{query}': {e}")
            return None
        except Exception as e:
            print(f"❌ Unexpected geocoding error: {e}")
            return None

    def batch_process_entities(self, db: Session, limit: int = 50):
        """
        Find GPE/LOC entities without coordinates and geocode them.
        """
        entities = (
            db.query(CanonicalEntity)
            .filter(
                CanonicalEntity.label.in_(["GPE", "LOC", "FAC"]),
                CanonicalEntity.latitude.is_(None),
            )
            .limit(limit)
            .all()
        )

        print(f"📍 Found {len(entities)} entities to geocode.")

        count = 0
        for entity in entities:
            result = self.geocode(entity.canonical_name)
            if result:
                entity.latitude = result["lat"]
                entity.longitude = result["lon"]
                entity.resolved_address = result["address"]
                count += 1
            else:
                # Mark as processed but failed (maybe set lat=0 or flag?)
                # For now, we leave it null so it might be retried or handled manually later
                # Or we could add a 'geocoding_status' column, but let's keep it simple.
                pass

        db.commit()
        print(f"✅ Successfully geocoded {count}/{len(entities)} entities.")


# Singleton instance
_geocoder = None


def get_geocoder() -> GeocodingService:
    global _geocoder
    if _geocoder is None:
        _geocoder = GeocodingService()
    return _geocoder
