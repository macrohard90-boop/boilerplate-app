"""AgentParser abstract base class for User-Agent string parsing."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AgentInfo:
    """Parsed user agent information."""

    raw: str = ""
    browser: str = "Unknown"
    browser_version: str = ""
    os: str = "Unknown"
    device_type: str = "unknown"  # desktop, mobile, tablet, bot, unknown


class AgentParser(ABC):
    """Abstract user agent parser interface.

    Default implementation uses regex. Swap for a library-based parser
    (e.g., user-agents pip package) if more accuracy is needed.
    """

    @abstractmethod
    def parse(self, user_agent: str) -> AgentInfo:
        """Parse a User-Agent string into structured fields."""
        ...
