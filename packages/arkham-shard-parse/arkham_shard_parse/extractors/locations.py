"""Geographic location extraction and geocoding."""

import logging
from typing import List

from ..models import LocationMention

logger = logging.getLogger(__name__)


class LocationExtractor:
    """Extract and geocode location mentions."""

    def __init__(self):
        """Initialize location extractor."""
        self.geocoder = None

        try:
            from geopy.geocoders import Nominatim
            self.geocoder = Nominatim(user_agent="arkham-parse-shard")
            logger.info("Geocoder initialized")
        except ImportError:
            logger.warning("geopy not available, geocoding disabled")

    def extract(
        self,
        text: str,
        doc_id: str | None = None,
        geocode: bool = False,
    ) -> List[LocationMention]:
        """
        Extract location mentions from text.

        Args:
            text: Text to process
            doc_id: Source document ID
            geocode: Whether to geocode locations

        Returns:
            List of location mentions
        """
        # In production, this would use NER to find GPE/LOC entities
        # For now, return empty - locations come from NER
        return []

    def geocode_location(self, location_text: str) -> LocationMention | None:
        """
        Geocode a location string to coordinates.

        Args:
            location_text: Location to geocode

        Returns:
            LocationMention with coordinates, or None
        """
        if not self.geocoder:
            return None

        try:
            location = self.geocoder.geocode(location_text)

            if location:
                return LocationMention(
                    text=location_text,
                    location_type="geocoded",
                    latitude=location.latitude,
                    longitude=location.longitude,
                    confidence=0.8,
                )
        except Exception as e:
            logger.warning(f"Geocoding failed for '{location_text}': {e}")

        return None

    def batch_geocode(
        self,
        locations: List[str],
    ) -> List[LocationMention]:
        """
        Geocode multiple locations.

        Args:
            locations: List of location strings

        Returns:
            List of geocoded location mentions
        """
        results = []

        for loc_text in locations:
            mention = self.geocode_location(loc_text)
            if mention:
                results.append(mention)

        return results
