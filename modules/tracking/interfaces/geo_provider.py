"""GeoProvider abstract base class for IP-based geolocation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GeoResult:
    """Geographic location result from IP lookup."""

    country: str = "Unknown"
    city: str = "Unknown"
    region: str = "Unknown"
    latitude: float | None = None
    longitude: float | None = None


class GeoProvider(ABC):
    """Abstract geo lookup interface.

    Swap by implementing this ABC and setting GEO_PROVIDER in .env.
    Default: placeholder (returns Unknown for all fields).
    Recommended: MaxMind GeoIP2.
    """

    @abstractmethod
    async def lookup(self, ip_address: str) -> GeoResult:
        """Look up geographic location from IP address."""
        ...
