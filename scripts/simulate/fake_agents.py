"""Pool of realistic User-Agent strings for simulation.

Each entry includes the raw UA string and pre-parsed metadata
so we can verify the backend agent parser produces correct results.
"""

from dataclasses import dataclass


@dataclass
class FakeAgent:
    raw: str
    browser: str
    os: str
    device_type: str  # desktop, mobile, tablet


AGENTS: list[FakeAgent] = [
    # ── Desktop — Chrome ──
    FakeAgent(
        raw="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        browser="Chrome",
        os="Windows 10",
        device_type="desktop",
    ),
    FakeAgent(
        raw="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        browser="Chrome",
        os="macOS",
        device_type="desktop",
    ),
    FakeAgent(
        raw="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        browser="Chrome",
        os="Linux",
        device_type="desktop",
    ),
    # ── Desktop — Firefox ──
    FakeAgent(
        raw="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        browser="Firefox",
        os="Windows 10",
        device_type="desktop",
    ),
    FakeAgent(
        raw="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
        browser="Firefox",
        os="macOS",
        device_type="desktop",
    ),
    # ── Desktop — Safari ──
    FakeAgent(
        raw="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        browser="Safari",
        os="macOS",
        device_type="desktop",
    ),
    # ── Desktop — Edge ──
    FakeAgent(
        raw="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        browser="Edge",
        os="Windows 10",
        device_type="desktop",
    ),
    # ── Mobile — Chrome ──
    FakeAgent(
        raw="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
        browser="Chrome",
        os="Android",
        device_type="mobile",
    ),
    FakeAgent(
        raw="Mozilla/5.0 (Linux; Android 14; SM-S926B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
        browser="Chrome",
        os="Android",
        device_type="mobile",
    ),
    # ── Mobile — Safari (iPhone) ──
    FakeAgent(
        raw="Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        browser="Safari",
        os="iOS",
        device_type="mobile",
    ),
    FakeAgent(
        raw="Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
        browser="Safari",
        os="iOS",
        device_type="mobile",
    ),
    # ── Tablet — iPad ──
    FakeAgent(
        raw="Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        browser="Safari",
        os="iOS",
        device_type="tablet",
    ),
    # ── Tablet — Android ──
    FakeAgent(
        raw="Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Safari/537.36",
        browser="Chrome",
        os="Android",
        device_type="tablet",
    ),
    # ── Desktop — Chrome (older versions) ──
    FakeAgent(
        raw="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        browser="Chrome",
        os="Windows 10",
        device_type="desktop",
    ),
    FakeAgent(
        raw="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        browser="Chrome",
        os="Windows 10",
        device_type="desktop",
    ),
    # ── Desktop — Opera ──
    FakeAgent(
        raw="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OPR/110.0.0.0",
        browser="Opera",
        os="Windows 10",
        device_type="desktop",
    ),
    # ── Mobile — Firefox ──
    FakeAgent(
        raw="Mozilla/5.0 (Android 14; Mobile; rv:125.0) Gecko/125.0 Firefox/125.0",
        browser="Firefox",
        os="Android",
        device_type="mobile",
    ),
    # ── Desktop — Chrome macOS Sonoma ──
    FakeAgent(
        raw="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        browser="Chrome",
        os="macOS",
        device_type="desktop",
    ),
    # ── Desktop — Firefox Linux ──
    FakeAgent(
        raw="Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        browser="Firefox",
        os="Linux",
        device_type="desktop",
    ),
    # ── Mobile — Samsung Internet ──
    FakeAgent(
        raw="Mozilla/5.0 (Linux; Android 14; SM-S926B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.0.0 Mobile Safari/537.36",
        browser="Chrome",
        os="Android",
        device_type="mobile",
    ),
]


# Distribution weights for realistic browser mix:
# ~45% Chrome Desktop, ~20% Safari, ~15% Firefox, ~10% Edge, ~10% Mobile
DESKTOP_AGENTS = [a for a in AGENTS if a.device_type == "desktop"]
MOBILE_AGENTS = [a for a in AGENTS if a.device_type == "mobile"]
TABLET_AGENTS = [a for a in AGENTS if a.device_type == "tablet"]
