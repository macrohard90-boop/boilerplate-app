"""Placeholder geo provider — returns Unknown for all fields.

Replace with MaxMind GeoIP2 or similar for production use.
"""

from modules.tracking.interfaces.geo_provider import GeoProvider, GeoResult


class PlaceholderGeoProvider(GeoProvider):
    async def lookup(self, ip_address: str) -> GeoResult:
        return GeoResult()


def get_geo_provider() -> GeoProvider:
    return PlaceholderGeoProvider()
