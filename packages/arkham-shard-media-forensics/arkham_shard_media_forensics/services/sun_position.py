"""
Sun position verification service.
Calculates expected shadow direction based on GPS and timestamp.
"""

from typing import Dict, Any
from datetime import datetime, timezone
import math

import structlog

logger = structlog.get_logger()

try:
    from pysolar.solar import get_altitude, get_azimuth
    PYSOLAR_AVAILABLE = True
except ImportError:
    PYSOLAR_AVAILABLE = False
    logger.info("pysolar not installed, sun position verification disabled")


class SunPositionService:
    """
    Verify shadow consistency using sun position calculations.

    Uses GPS coordinates and timestamp from EXIF to calculate
    where the sun would have been, and therefore where shadows
    should point.
    """

    def __init__(self, frame):
        self.frame = frame

    def is_available(self) -> bool:
        """Check if sun position calculation is available."""
        return PYSOLAR_AVAILABLE

    async def calculate_sun_position(
        self,
        latitude: float,
        longitude: float,
        dt: datetime,
    ) -> Dict[str, Any]:
        """
        Calculate sun position for given coordinates and time.

        Args:
            latitude: Decimal degrees (positive = North)
            longitude: Decimal degrees (positive = East)
            dt: Timezone-aware datetime

        Returns:
            Dict with sun altitude, azimuth, and shadow direction
        """
        if not PYSOLAR_AVAILABLE:
            return {"error": "pysolar not installed", "success": False}

        # Ensure datetime is timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        try:
            # Get sun position
            altitude = get_altitude(latitude, longitude, dt)
            azimuth = get_azimuth(latitude, longitude, dt)

            # Shadow direction is opposite to sun azimuth
            shadow_direction = (azimuth + 180) % 360

            # Calculate expected shadow length ratio (for vertical objects)
            # shadow_length = object_height / tan(altitude)
            if altitude > 0:
                shadow_length_ratio = 1.0 / math.tan(math.radians(altitude))
            else:
                shadow_length_ratio = float("inf")  # Sun below horizon

            return {
                "success": True,
                "latitude": latitude,
                "longitude": longitude,
                "datetime": dt.isoformat(),
                "sun_altitude": round(altitude, 2),
                "sun_azimuth": round(azimuth, 2),
                "expected_shadow_direction": round(shadow_direction, 2),
                "shadow_length_ratio": round(shadow_length_ratio, 2) if shadow_length_ratio != float("inf") else None,
                "sun_above_horizon": altitude > 0,
                "interpretation": self._interpret_position(altitude, azimuth),
            }

        except Exception as e:
            logger.error("Sun position calculation failed", error=str(e))
            return {"success": False, "error": str(e)}

    def _interpret_position(self, altitude: float, azimuth: float) -> str:
        """Generate human-readable interpretation of sun position."""
        if altitude < 0:
            return "Sun is below the horizon - no direct sunlight possible"

        # Time of day approximation
        if altitude < 10:
            time_desc = "very low (sunrise/sunset)"
        elif altitude < 30:
            time_desc = "low (morning/evening)"
        elif altitude < 60:
            time_desc = "moderate (mid-morning/afternoon)"
        else:
            time_desc = "high (midday)"

        # Direction
        if 337.5 <= azimuth or azimuth < 22.5:
            direction = "North"
        elif 22.5 <= azimuth < 67.5:
            direction = "Northeast"
        elif 67.5 <= azimuth < 112.5:
            direction = "East"
        elif 112.5 <= azimuth < 157.5:
            direction = "Southeast"
        elif 157.5 <= azimuth < 202.5:
            direction = "South"
        elif 202.5 <= azimuth < 247.5:
            direction = "Southwest"
        elif 247.5 <= azimuth < 292.5:
            direction = "West"
        else:
            direction = "Northwest"

        return f"Sun is {time_desc}, positioned to the {direction}. Shadows should point roughly opposite."

    async def verify_from_exif(
        self,
        gps_data: Dict[str, Any],
        timestamp_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculate sun position from EXIF GPS and timestamp data.

        Args:
            gps_data: GPS data from EXIF (latitude, longitude)
            timestamp_data: Timestamp data from EXIF (datetime_original, etc.)

        Returns:
            Sun position calculation or error
        """
        # Get coordinates
        latitude = gps_data.get("latitude")
        longitude = gps_data.get("longitude")

        if latitude is None or longitude is None:
            return {
                "success": False,
                "error": "GPS coordinates not available in EXIF",
            }

        # Get timestamp
        dt_str = (
            timestamp_data.get("datetime_original")
            or timestamp_data.get("datetime_digitized")
            or timestamp_data.get("datetime_modified")
        )

        if not dt_str:
            return {
                "success": False,
                "error": "No timestamp available in EXIF",
            }

        # Parse timestamp (EXIF format is typically "YYYY:MM:DD HH:MM:SS")
        try:
            dt_str = dt_str.replace(":", "-", 2)  # Fix date separators
            dt = datetime.fromisoformat(dt_str)

            # Check for GPS timestamp for more precision
            gps_time = timestamp_data.get("gps_timestamp")
            gps_date = timestamp_data.get("gps_datestamp")
            if gps_time and gps_date:
                # GPS timestamps are always UTC
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                # Assume local time, but note uncertainty
                dt = dt.replace(tzinfo=timezone.utc)  # Treat as UTC for calculation

        except Exception as e:
            return {
                "success": False,
                "error": f"Could not parse timestamp: {dt_str} ({e})",
            }

        result = await self.calculate_sun_position(latitude, longitude, dt)
        result["timestamp_source"] = "exif"
        result["timezone_note"] = (
            "Timezone assumed UTC if not specified in EXIF. "
            "Actual local time may differ, affecting accuracy."
        )

        return result
