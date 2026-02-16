"""Regex-based User-Agent parser — no external dependencies.

Detects common browsers, operating systems, and device types.
Sufficient for analytics; swap for library-based parser if more accuracy needed.
"""

import re

from modules.tracking.interfaces.agent_parser import AgentInfo, AgentParser

# Browser patterns (order matters — check specific before generic)
_BROWSER_PATTERNS = [
    (r"Edg[e/](\d+[\.\d]*)", "Edge"),
    (r"OPR/(\d+[\.\d]*)", "Opera"),
    (r"Chrome/(\d+[\.\d]*)", "Chrome"),
    (r"Firefox/(\d+[\.\d]*)", "Firefox"),
    (r"Safari/(\d+[\.\d]*)", "Safari"),
    (r"MSIE (\d+[\.\d]*)", "IE"),
    (r"Trident/.*rv:(\d+[\.\d]*)", "IE"),
]

# OS patterns
_OS_PATTERNS = [
    (r"Windows NT 10", "Windows 10"),
    (r"Windows NT 6\.3", "Windows 8.1"),
    (r"Windows NT 6\.1", "Windows 7"),
    (r"Windows", "Windows"),
    (r"Mac OS X (\d+[_\.\d]*)", "macOS"),
    (r"iPhone", "iOS"),
    (r"iPad", "iPadOS"),
    (r"Android (\d+[\.\d]*)", "Android"),
    (r"Linux", "Linux"),
    (r"CrOS", "ChromeOS"),
]

# Bot patterns
_BOT_PATTERNS = re.compile(
    r"bot|crawl|spider|slurp|archiver|mediapartners|Googlebot|Bingbot|baiduspider",
    re.IGNORECASE,
)

# Mobile patterns
_MOBILE_PATTERNS = re.compile(r"Mobile|Android|iPhone|iPod|Opera Mini|IEMobile", re.IGNORECASE)

# Tablet patterns
_TABLET_PATTERNS = re.compile(r"iPad|Android(?!.*Mobile)|Tablet|PlayBook|Silk", re.IGNORECASE)


class DefaultAgentParser(AgentParser):
    def parse(self, user_agent: str) -> AgentInfo:
        if not user_agent:
            return AgentInfo(raw="")

        browser, browser_version = self._parse_browser(user_agent)
        os_name = self._parse_os(user_agent)
        device_type = self._parse_device(user_agent)

        return AgentInfo(
            raw=user_agent,
            browser=browser,
            browser_version=browser_version,
            os=os_name,
            device_type=device_type,
        )

    def _parse_browser(self, ua: str) -> tuple[str, str]:
        for pattern, name in _BROWSER_PATTERNS:
            match = re.search(pattern, ua)
            if match:
                version = match.group(1) if match.lastindex else ""
                # Safari version is in Version/ header
                if name == "Safari" and "Chrome" not in ua:
                    ver_match = re.search(r"Version/(\d+[\.\d]*)", ua)
                    if ver_match:
                        version = ver_match.group(1)
                elif name == "Safari" and "Chrome" in ua:
                    continue  # Chrome also has Safari/ in UA
                return name, version
        return "Unknown", ""

    def _parse_os(self, ua: str) -> str:
        for pattern, name in _OS_PATTERNS:
            match = re.search(pattern, ua)
            if match:
                if name == "macOS" and match.lastindex:
                    version = match.group(1).replace("_", ".")
                    return f"macOS {version}"
                if name == "Android" and match.lastindex:
                    return f"Android {match.group(1)}"
                return name
        return "Unknown"

    def _parse_device(self, ua: str) -> str:
        if _BOT_PATTERNS.search(ua):
            return "bot"
        if _TABLET_PATTERNS.search(ua):
            return "tablet"
        if _MOBILE_PATTERNS.search(ua):
            return "mobile"
        return "desktop"


def get_agent_parser() -> AgentParser:
    return DefaultAgentParser()
