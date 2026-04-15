"""Rule-based SEO scoring provider.

Scores pages 0-100 using weighted on-page rules. No external dependencies —
works fully offline/local. Designed for the boilerplate template; operators
can swap this for a Lighthouse or Search Console provider later.
"""

from modules.seo.interfaces.scoring_provider import (
    PageSEOData,
    RuleResult,
    ScoreResult,
    ScoringProvider,
)


def _check_title_present(data: PageSEOData) -> RuleResult:
    passed = bool(data.title and data.title.strip())
    return RuleResult(
        rule_id="title_present",
        name="Title exists",
        passed=passed,
        weight=10,
        points=100 if passed else 0,
        max_points=100,
        recommendation=None if passed else "Add a page title.",
    )


def _check_title_length(data: PageSEOData) -> RuleResult:
    length = len(data.title) if data.title else 0
    passed = 30 <= length <= 60
    rec = None
    if not data.title:
        rec = "Add a page title (30-60 characters recommended)."
    elif length < 30:
        rec = f"Title is too short ({length} chars). Aim for 30-60 characters."
    elif length > 60:
        rec = f"Title is too long ({length} chars). Keep it under 60 characters to avoid truncation in search results."
    return RuleResult(
        rule_id="title_length",
        name="Title length optimal",
        passed=passed,
        weight=8,
        points=80 if passed else 0,
        max_points=80,
        recommendation=rec,
    )


def _check_desc_present(data: PageSEOData) -> RuleResult:
    passed = bool(data.description and data.description.strip())
    return RuleResult(
        rule_id="desc_present",
        name="Description exists",
        passed=passed,
        weight=10,
        points=100 if passed else 0,
        max_points=100,
        recommendation=None if passed else "Add a meta description.",
    )


def _check_desc_length(data: PageSEOData) -> RuleResult:
    length = len(data.description) if data.description else 0
    passed = 120 <= length <= 160
    rec = None
    if not data.description:
        rec = "Add a meta description (120-160 characters recommended)."
    elif length < 120:
        rec = f"Description is short ({length} chars). Aim for 120-160 characters for better CTR."
    elif length > 160:
        rec = f"Description is long ({length} chars). Keep it under 160 characters to avoid truncation."
    return RuleResult(
        rule_id="desc_length",
        name="Description length optimal",
        passed=passed,
        weight=7,
        points=70 if passed else 0,
        max_points=70,
        recommendation=rec,
    )


def _check_canonical(data: PageSEOData) -> RuleResult:
    passed = bool(data.canonical_url)
    return RuleResult(
        rule_id="canonical_set",
        name="Canonical URL set",
        passed=passed,
        weight=6,
        points=60 if passed else 0,
        max_points=60,
        recommendation=None if passed else "Set a canonical URL to prevent duplicate content issues.",
    )


def _check_og_complete(data: PageSEOData) -> RuleResult:
    og = data.og_tags or {}
    has_title = bool(og.get("og:title"))
    has_desc = bool(og.get("og:description"))
    has_image = bool(og.get("og:image"))
    passed = has_title and has_desc and has_image
    missing = []
    if not has_title:
        missing.append("og:title")
    if not has_desc:
        missing.append("og:description")
    if not has_image:
        missing.append("og:image")
    rec = None if passed else f"Missing Open Graph tags: {', '.join(missing)}."
    return RuleResult(
        rule_id="og_complete",
        name="Open Graph tags complete",
        passed=passed,
        weight=7,
        points=70 if passed else 0,
        max_points=70,
        recommendation=rec,
    )


def _check_twitter_complete(data: PageSEOData) -> RuleResult:
    tw = data.twitter_tags or {}
    has_card = bool(tw.get("twitter:card"))
    has_title = bool(tw.get("twitter:title"))
    has_desc = bool(tw.get("twitter:description"))
    passed = has_card and has_title and has_desc
    missing = []
    if not has_card:
        missing.append("twitter:card")
    if not has_title:
        missing.append("twitter:title")
    if not has_desc:
        missing.append("twitter:description")
    rec = None if passed else f"Missing Twitter Card tags: {', '.join(missing)}."
    return RuleResult(
        rule_id="twitter_complete",
        name="Twitter Card tags complete",
        passed=passed,
        weight=5,
        points=50 if passed else 0,
        max_points=50,
        recommendation=rec,
    )


def _check_structured_data(data: PageSEOData) -> RuleResult:
    """Check for page-specific structured data beyond Organization/WebSite."""
    schemas = data.structured_data or []
    generic_types = {"Organization", "WebSite"}
    has_specific = any(
        s.get("@type") not in generic_types for s in schemas
    )
    passed = has_specific
    return RuleResult(
        rule_id="structured_data",
        name="Structured data present",
        passed=passed,
        weight=8,
        points=80 if passed else 0,
        max_points=80,
        recommendation=None if passed else "Add page-specific structured data (e.g., Product, BreadcrumbList).",
    )


def _check_indexable(data: PageSEOData) -> RuleResult:
    passed = "noindex" not in data.robots.lower()
    return RuleResult(
        rule_id="robots_indexable",
        name="Page is indexable",
        passed=passed,
        weight=4,
        points=40 if passed else 0,
        max_points=40,
        recommendation=None if passed else "Page is set to noindex. Remove noindex if this page should appear in search results.",
    )


def _check_h1_present(data: PageSEOData) -> RuleResult:
    """Check for H1 heading. Auto-passes if no crawl data is available."""
    if data.headings is None:
        # No crawl data — can't check, give benefit of the doubt
        return RuleResult(
            rule_id="h1_present",
            name="H1 heading present",
            passed=True,
            weight=6,
            points=60,
            max_points=60,
            recommendation=None,
        )
    has_h1 = any(h.get("tag", "").lower() == "h1" for h in data.headings)
    return RuleResult(
        rule_id="h1_present",
        name="H1 heading present",
        passed=has_h1,
        weight=6,
        points=60 if has_h1 else 0,
        max_points=60,
        recommendation=None if has_h1 else "Add an H1 heading to the page.",
    )


# All rules in evaluation order
_RULES = [
    _check_title_present,
    _check_title_length,
    _check_desc_present,
    _check_desc_length,
    _check_canonical,
    _check_og_complete,
    _check_twitter_complete,
    _check_structured_data,
    _check_indexable,
    _check_h1_present,
]


class RuleScoringProvider(ScoringProvider):
    """Rule-based on-page SEO scoring provider."""

    async def score_page(self, data: PageSEOData) -> ScoreResult:
        rules = [rule(data) for rule in _RULES]
        total_points = sum(r.points for r in rules)
        total_max = sum(r.max_points for r in rules)
        score = round(total_points / total_max * 100) if total_max > 0 else 0
        return ScoreResult(score=score, rules=rules, provider="rule_based")
