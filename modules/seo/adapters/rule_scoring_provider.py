"""Rule-based SEO scoring provider.

Scores pages 0-100 using weighted on-page rules. No external dependencies —
works fully offline/local. Designed for the boilerplate template; operators
can swap this for a Lighthouse or Search Console provider later.

Rules are organized into 4 categories:
- technical: URL structure, canonical, robots, HTTPS, headings
- content: title, description, content length, images, internal links, keywords
- social: Open Graph, Twitter Cards, OG images
- performance: schema completeness, structured data
"""

import re

from backend.core.config import settings
from modules.seo.interfaces.scoring_provider import (
    PageSEOData,
    RuleResult,
    ScoreResult,
    ScoringProvider,
)


# ---------------------------------------------------------------------------
# Category: content
# ---------------------------------------------------------------------------


def _check_title_present(data: PageSEOData) -> RuleResult:
    passed = bool(data.title and data.title.strip())
    return RuleResult(
        rule_id="title_present",
        name="Title exists",
        passed=passed,
        weight=10,
        points=100 if passed else 0,
        max_points=100,
        category="content",
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
        rec = (
            f"Title is too long ({length} chars). "
            "Keep it under 60 characters to avoid truncation in search results."
        )
    return RuleResult(
        rule_id="title_length",
        name="Title length optimal",
        passed=passed,
        weight=8,
        points=80 if passed else 0,
        max_points=80,
        category="content",
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
        category="content",
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
        category="content",
        recommendation=rec,
    )


def _check_content_length(data: PageSEOData) -> RuleResult:
    """Check page body content length. Auto-passes without crawl data."""
    if data.content_length == 0 and data.headings is None:
        # No crawl data — can't check
        return RuleResult(
            rule_id="content_length",
            name="Content length sufficient",
            passed=True,
            weight=5,
            points=50,
            max_points=50,
            category="content",
        )
    is_product = data.path.startswith("products/")
    threshold = 300 if is_product else 500
    label = "300" if is_product else "500"
    passed = data.content_length >= threshold
    rec = None
    if not passed:
        rec = (
            f"Page has only {data.content_length} characters of content. "
            f"Aim for at least {label} characters."
        )
    return RuleResult(
        rule_id="content_length",
        name="Content length sufficient",
        passed=passed,
        weight=5,
        points=50 if passed else 0,
        max_points=50,
        category="content",
        recommendation=rec,
    )


def _check_images_alt_text(data: PageSEOData) -> RuleResult:
    """Check that all images have alt text. Auto-passes without crawl data."""
    if data.images_without_alt is None:
        return RuleResult(
            rule_id="images_alt_text",
            name="All images have alt text",
            passed=True,
            weight=6,
            points=60,
            max_points=60,
            category="content",
        )
    count = len(data.images_without_alt)
    passed = count == 0
    rec = None
    if not passed:
        rec = (
            f"{count} image(s) missing alt text. "
            "Add descriptive alt text for accessibility and SEO."
        )
    return RuleResult(
        rule_id="images_alt_text",
        name="All images have alt text",
        passed=passed,
        weight=6,
        points=60 if passed else 0,
        max_points=60,
        category="content",
        recommendation=rec,
    )


def _check_internal_links(data: PageSEOData) -> RuleResult:
    """Check for sufficient internal links. Auto-passes without crawl data."""
    if data.internal_links == 0 and data.headings is None:
        return RuleResult(
            rule_id="internal_links",
            name="Internal links present",
            passed=True,
            weight=4,
            points=40,
            max_points=40,
            category="content",
        )
    passed = data.internal_links >= 2
    rec = None
    if not passed:
        rec = (
            f"Page has only {data.internal_links} internal link(s). "
            "Add at least 2 internal links to improve crawlability."
        )
    return RuleResult(
        rule_id="internal_links",
        name="Internal links present",
        passed=passed,
        weight=4,
        points=40 if passed else 0,
        max_points=40,
        category="content",
        recommendation=rec,
    )


def _check_keyword_in_content(data: PageSEOData) -> RuleResult:
    """Check if target keywords appear in title, description, and H1.

    Auto-passes if no target keywords are assigned to the page.
    """
    if not data.target_keywords:
        return RuleResult(
            rule_id="keyword_in_content",
            name="Target keyword present",
            passed=True,
            weight=5,
            points=50,
            max_points=50,
            category="content",
        )

    keyword = data.target_keywords[0].lower()
    in_title = keyword in (data.title or "").lower()
    in_desc = keyword in (data.description or "").lower()
    h1_texts = [
        h["text"].lower()
        for h in (data.headings or [])
        if h.get("tag", "").lower() == "h1"
    ]
    in_h1 = any(keyword in t for t in h1_texts)

    matches = sum([in_title, in_desc, in_h1])
    passed = matches >= 2

    missing = []
    if not in_title:
        missing.append("title")
    if not in_desc:
        missing.append("description")
    if not in_h1:
        missing.append("H1")
    rec = None
    if not passed:
        rec = (
            f"Target keyword \"{data.target_keywords[0]}\" missing from: "
            f"{', '.join(missing)}. Include it in at least 2 of: title, description, H1."
        )
    return RuleResult(
        rule_id="keyword_in_content",
        name="Target keyword present",
        passed=passed,
        weight=5,
        points=50 if passed else 0,
        max_points=50,
        category="content",
        recommendation=rec,
    )


# ---------------------------------------------------------------------------
# Category: technical
# ---------------------------------------------------------------------------


def _check_canonical(data: PageSEOData) -> RuleResult:
    passed = bool(data.canonical_url)
    return RuleResult(
        rule_id="canonical_set",
        name="Canonical URL set",
        passed=passed,
        weight=6,
        points=60 if passed else 0,
        max_points=60,
        category="technical",
        recommendation=None
        if passed
        else "Set a canonical URL to prevent duplicate content issues.",
    )


def _check_canonical_self_ref(data: PageSEOData) -> RuleResult:
    """Check that canonical URL points to this page's own URL."""
    if not data.canonical_url:
        return RuleResult(
            rule_id="canonical_self_ref",
            name="Canonical is self-referencing",
            passed=False,
            weight=3,
            points=0,
            max_points=30,
            category="technical",
            recommendation="Set a canonical URL that points to this page.",
        )
    # Normalize: strip trailing slashes, compare path portion
    canon_path = data.canonical_url.rstrip("/").split("//", 1)[-1]
    # Remove domain portion to get just the path
    if "/" in canon_path:
        canon_path = canon_path.split("/", 1)[1]
    else:
        canon_path = ""
    page_path = data.path.strip("/")
    passed = canon_path.strip("/") == page_path
    return RuleResult(
        rule_id="canonical_self_ref",
        name="Canonical is self-referencing",
        passed=passed,
        weight=3,
        points=30 if passed else 0,
        max_points=30,
        category="technical",
        recommendation=None
        if passed
        else "Canonical URL should point to this page's own URL.",
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
        category="technical",
        recommendation=None
        if passed
        else "Page is set to noindex. Remove noindex if this page should appear in search results.",
    )


def _check_h1_present(data: PageSEOData) -> RuleResult:
    """Check for H1 heading. Auto-passes if no crawl data is available."""
    if data.headings is None:
        return RuleResult(
            rule_id="h1_present",
            name="H1 heading present",
            passed=True,
            weight=6,
            points=60,
            max_points=60,
            category="technical",
        )
    has_h1 = any(h.get("tag", "").lower() == "h1" for h in data.headings)
    return RuleResult(
        rule_id="h1_present",
        name="H1 heading present",
        passed=has_h1,
        weight=6,
        points=60 if has_h1 else 0,
        max_points=60,
        category="technical",
        recommendation=None if has_h1 else "Add an H1 heading to the page.",
    )


def _check_heading_hierarchy(data: PageSEOData) -> RuleResult:
    """Check heading hierarchy: has H2s and no skipped levels."""
    if data.headings is None:
        return RuleResult(
            rule_id="heading_hierarchy",
            name="Heading hierarchy valid",
            passed=True,
            weight=5,
            points=50,
            max_points=50,
            category="technical",
        )
    levels = [
        int(h["tag"][1])
        for h in data.headings
        if h.get("tag", "").lower() in ("h1", "h2", "h3", "h4", "h5", "h6")
    ]
    has_h2 = 2 in levels

    # Check for skipped levels (e.g. H1 then H3 with no H2)
    skipped = False
    if levels:
        sorted_unique = sorted(set(levels))
        for i in range(1, len(sorted_unique)):
            if sorted_unique[i] - sorted_unique[i - 1] > 1:
                skipped = True
                break

    passed = has_h2 and not skipped
    rec = None
    if not has_h2:
        rec = "Add H2 subheadings to structure your content."
    elif skipped:
        rec = "Heading levels are skipped (e.g. H1 to H3 without H2). Use sequential heading levels."
    return RuleResult(
        rule_id="heading_hierarchy",
        name="Heading hierarchy valid",
        passed=passed,
        weight=5,
        points=50 if passed else 0,
        max_points=50,
        category="technical",
        recommendation=rec,
    )


def _check_url_quality(data: PageSEOData) -> RuleResult:
    """Check URL structure: short, hyphens, no special chars."""
    path = data.path
    issues = []
    if len(path) > 100:
        issues.append(f"URL path is long ({len(path)} chars)")
    if "_" in path:
        issues.append("uses underscores (use hyphens)")
    if re.search(r"[^a-zA-Z0-9\-/.]", path):
        issues.append("contains special characters")
    if "//" in path:
        issues.append("contains double slashes")

    passed = len(issues) == 0
    rec = None
    if not passed:
        rec = f"URL issues: {'; '.join(issues)}."
    return RuleResult(
        rule_id="url_quality",
        name="URL structure clean",
        passed=passed,
        weight=4,
        points=40 if passed else 0,
        max_points=40,
        category="technical",
        recommendation=rec,
    )


def _check_https_enforced(data: PageSEOData) -> RuleResult:
    """Check that canonical URL uses HTTPS (skip in dev/localhost)."""
    if not data.canonical_url:
        return RuleResult(
            rule_id="https_enforced",
            name="HTTPS enforced",
            passed=True,  # can't check without URL
            weight=3,
            points=30,
            max_points=30,
            category="technical",
        )
    is_localhost = "localhost" in data.canonical_url or "127.0.0.1" in data.canonical_url
    if is_localhost:
        # Dev environment — auto-pass
        return RuleResult(
            rule_id="https_enforced",
            name="HTTPS enforced",
            passed=True,
            weight=3,
            points=30,
            max_points=30,
            category="technical",
        )
    passed = data.canonical_url.startswith("https://")
    return RuleResult(
        rule_id="https_enforced",
        name="HTTPS enforced",
        passed=passed,
        weight=3,
        points=30 if passed else 0,
        max_points=30,
        category="technical",
        recommendation=None
        if passed
        else "Page canonical URL uses HTTP. Enforce HTTPS for security and SEO ranking.",
    )


# ---------------------------------------------------------------------------
# Category: technical (HTML-analysis rules)
# ---------------------------------------------------------------------------


def _check_viewport_present(data: PageSEOData) -> RuleResult:
    """Check for viewport meta tag (Lighthouse critical check)."""
    if data.has_viewport is None:
        return RuleResult(
            rule_id="viewport_present",
            name="Viewport meta tag",
            passed=True,
            weight=4,
            points=40,
            max_points=40,
            category="technical",
        )
    passed = data.has_viewport
    return RuleResult(
        rule_id="viewport_present",
        name="Viewport meta tag",
        passed=passed,
        weight=4,
        points=40 if passed else 0,
        max_points=40,
        category="technical",
        recommendation=None
        if passed
        else 'Add <meta name="viewport" content="width=device-width, initial-scale=1"> for mobile rendering.',
    )


def _check_lang_attribute(data: PageSEOData) -> RuleResult:
    """Check that <html> has a lang attribute."""
    if data.has_lang is None:
        return RuleResult(
            rule_id="lang_attribute",
            name="Language attribute set",
            passed=True,
            weight=3,
            points=30,
            max_points=30,
            category="technical",
        )
    passed = data.has_lang
    return RuleResult(
        rule_id="lang_attribute",
        name="Language attribute set",
        passed=passed,
        weight=3,
        points=30 if passed else 0,
        max_points=30,
        category="technical",
        recommendation=None
        if passed
        else 'Add a lang attribute to the <html> element (e.g. <html lang="en">) for accessibility and SEO.',
    )


def _check_favicon_present(data: PageSEOData) -> RuleResult:
    """Check for a favicon link element."""
    if data.has_favicon is None:
        return RuleResult(
            rule_id="favicon_present",
            name="Favicon present",
            passed=True,
            weight=2,
            points=20,
            max_points=20,
            category="technical",
        )
    passed = data.has_favicon
    return RuleResult(
        rule_id="favicon_present",
        name="Favicon present",
        passed=passed,
        weight=2,
        points=20 if passed else 0,
        max_points=20,
        category="technical",
        recommendation=None
        if passed
        else 'Add a favicon (<link rel="icon">) for brand recognition in browser tabs and bookmarks.',
    )


# ---------------------------------------------------------------------------
# Category: content (HTML-analysis rules)
# ---------------------------------------------------------------------------


def _check_readability_score(data: PageSEOData) -> RuleResult:
    """Check content readability using Flesch Reading Ease.

    Auto-passes when body text is unavailable or too short for meaningful analysis.
    """
    if data.body_text is None or len(data.body_text) < 100:
        return RuleResult(
            rule_id="readability_score",
            name="Content readability",
            passed=True,
            weight=4,
            points=40,
            max_points=40,
            category="content",
        )

    from modules.seo.services.readability_service import analyze_content

    result = analyze_content(data.body_text)
    passed = result.flesch_reading_ease >= 60
    rec = None
    if not passed:
        rec = (
            f"Content readability is low (Flesch score: {result.flesch_reading_ease}, "
            f'quality: "{result.quality}"). Use shorter sentences and simpler words. '
            "Aim for a Flesch score of 60+ (8th-9th grade level)."
        )
    return RuleResult(
        rule_id="readability_score",
        name="Content readability",
        passed=passed,
        weight=4,
        points=40 if passed else 0,
        max_points=40,
        category="content",
        recommendation=rec,
    )


def _check_keyword_density(data: PageSEOData) -> RuleResult:
    """Check that target keyword density is in the optimal 0.5-3% range.

    Auto-passes when no target keywords are assigned or body text is unavailable.
    """
    if (
        not data.target_keywords
        or data.body_text is None
        or len(data.body_text) < 100
    ):
        return RuleResult(
            rule_id="keyword_density",
            name="Keyword density optimal",
            passed=True,
            weight=3,
            points=30,
            max_points=30,
            category="content",
        )

    keyword = data.target_keywords[0].lower()
    text_lower = data.body_text.lower()
    word_count = len(text_lower.split())
    if word_count == 0:
        return RuleResult(
            rule_id="keyword_density",
            name="Keyword density optimal",
            passed=True,
            weight=3,
            points=30,
            max_points=30,
            category="content",
        )

    # Count occurrences of the keyword phrase
    occurrences = text_lower.count(keyword)
    keyword_word_count = len(keyword.split())
    density = (occurrences * keyword_word_count / word_count) * 100

    passed = 0.5 <= density <= 3.0
    rec = None
    if density < 0.5:
        rec = (
            f'Target keyword "{data.target_keywords[0]}" density is too low '
            f"({density:.1f}%). Use it naturally 2-5 more times in your content."
        )
    elif density > 3.0:
        rec = (
            f'Target keyword "{data.target_keywords[0]}" density is too high '
            f"({density:.1f}%). Reduce usage to avoid keyword stuffing."
        )
    return RuleResult(
        rule_id="keyword_density",
        name="Keyword density optimal",
        passed=passed,
        weight=3,
        points=30 if passed else 0,
        max_points=30,
        category="content",
        recommendation=rec,
    )


def _check_external_links_present(data: PageSEOData) -> RuleResult:
    """Check for at least one outbound link (link diversity signal)."""
    if data.external_links is None:
        return RuleResult(
            rule_id="external_links_present",
            name="External links present",
            passed=True,
            weight=2,
            points=20,
            max_points=20,
            category="content",
        )
    passed = data.external_links >= 1
    return RuleResult(
        rule_id="external_links_present",
        name="External links present",
        passed=passed,
        weight=2,
        points=20 if passed else 0,
        max_points=20,
        category="content",
        recommendation=None
        if passed
        else "Add at least one outbound link to a relevant, authoritative source. Link diversity signals content quality.",
    )


def _check_title_h1_differentiated(data: PageSEOData) -> RuleResult:
    """Check that the page title and H1 heading are not identical."""
    # Determine H1 text: prefer html_analysis h1_text, fall back to headings data
    h1_text = data.h1_text
    if not h1_text and data.headings:
        for h in data.headings:
            if h.get("tag", "").lower() == "h1":
                h1_text = h.get("text", "")
                break

    if not data.title or not h1_text:
        return RuleResult(
            rule_id="title_h1_differentiated",
            name="Title and H1 differ",
            passed=True,
            weight=2,
            points=20,
            max_points=20,
            category="content",
        )

    # Strip site name suffix from title for comparison (e.g. "About | My Site")
    title_clean = data.title.strip().lower()
    h1_clean = h1_text.strip().lower()

    # Also compare without the "| site name" suffix
    if " | " in title_clean:
        title_clean = title_clean.rsplit(" | ", 1)[0].strip()
    if " - " in title_clean:
        title_clean = title_clean.rsplit(" - ", 1)[0].strip()

    passed = title_clean != h1_clean
    return RuleResult(
        rule_id="title_h1_differentiated",
        name="Title and H1 differ",
        passed=passed,
        weight=2,
        points=20 if passed else 0,
        max_points=20,
        category="content",
        recommendation=None
        if passed
        else "Title and H1 are identical. Differentiate them to target slightly different keyword variations.",
    )


def _check_meta_desc_complete(data: PageSEOData) -> RuleResult:
    """Check that the meta description ends cleanly (not truncated)."""
    if not data.description or len(data.description) < 10:
        return RuleResult(
            rule_id="meta_desc_complete",
            name="Description is complete",
            passed=True,
            weight=2,
            points=20,
            max_points=20,
            category="content",
        )

    desc = data.description.strip()
    # Passes if it ends with sentence-ending punctuation or a complete word
    ends_cleanly = bool(re.search(r"[.!?…]$", desc))
    passed = ends_cleanly
    return RuleResult(
        rule_id="meta_desc_complete",
        name="Description is complete",
        passed=passed,
        weight=2,
        points=20 if passed else 0,
        max_points=20,
        category="content",
        recommendation=None
        if passed
        else "Meta description appears truncated — it should end with proper punctuation (., !, or ?).",
    )


# ---------------------------------------------------------------------------
# Category: performance (HTML-analysis rules)
# ---------------------------------------------------------------------------


def _check_img_dimensions(data: PageSEOData) -> RuleResult:
    """Check that images have explicit width/height (prevents CLS)."""
    if data.total_images is None or data.total_images == 0:
        return RuleResult(
            rule_id="img_dimensions",
            name="Images have dimensions",
            passed=True,
            weight=3,
            points=30,
            max_points=30,
            category="performance",
        )

    missing = data.images_missing_dimensions or 0
    with_dims = data.total_images - missing
    ratio = with_dims / data.total_images if data.total_images > 0 else 1
    passed = ratio >= 0.8  # 80% threshold

    rec = None
    if not passed:
        rec = (
            f"{missing} of {data.total_images} images missing explicit width/height attributes. "
            "Add dimensions to prevent Cumulative Layout Shift (CLS)."
        )
    return RuleResult(
        rule_id="img_dimensions",
        name="Images have dimensions",
        passed=passed,
        weight=3,
        points=30 if passed else 0,
        max_points=30,
        category="performance",
        recommendation=rec,
    )


# ---------------------------------------------------------------------------
# Category: social (HTML-analysis rules)
# ---------------------------------------------------------------------------


def _check_og_url_valid(data: PageSEOData) -> RuleResult:
    """Check that og:image URL is structurally valid (not empty/broken)."""
    og = data.og_tags or {}
    og_image = og.get("og:image", "")

    if not og_image:
        # No og:image at all — other rules handle presence
        return RuleResult(
            rule_id="og_url_valid",
            name="OG image URL valid",
            passed=True,
            weight=2,
            points=20,
            max_points=20,
            category="social",
        )

    # Check it looks like a real URL (not just "/" or empty path)
    passed = len(og_image.strip("/")) > 0 and (
        og_image.startswith(("http://", "https://", "/"))
    )
    return RuleResult(
        rule_id="og_url_valid",
        name="OG image URL valid",
        passed=passed,
        weight=2,
        points=20 if passed else 0,
        max_points=20,
        category="social",
        recommendation=None
        if passed
        else f'OG image URL "{og_image}" appears invalid. Use a full URL or absolute path to a real image.',
    )


# ---------------------------------------------------------------------------
# Category: social
# ---------------------------------------------------------------------------


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
        category="social",
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
        category="social",
        recommendation=rec,
    )


def _check_og_image_custom(data: PageSEOData) -> RuleResult:
    """Check that the OG image is not the default fallback."""
    og = data.og_tags or {}
    og_image = og.get("og:image", "")
    default_image = getattr(settings, "default_og_image", "/images/og-default.png")
    if not og_image:
        return RuleResult(
            rule_id="og_image_custom",
            name="OG image is page-specific",
            passed=False,
            weight=4,
            points=0,
            max_points=40,
            category="social",
            recommendation="No OG image set. Add a page-specific image for better social sharing.",
        )
    passed = og_image != default_image and not og_image.endswith(default_image)
    return RuleResult(
        rule_id="og_image_custom",
        name="OG image is page-specific",
        passed=passed,
        weight=4,
        points=40 if passed else 0,
        max_points=40,
        category="social",
        recommendation=None
        if passed
        else "Using default OG image. Set a page-specific image for better social sharing.",
    )


# ---------------------------------------------------------------------------
# Category: performance (schema/structured data)
# ---------------------------------------------------------------------------


def _check_structured_data(data: PageSEOData) -> RuleResult:
    """Check for page-specific structured data beyond Organization/WebSite."""
    schemas = data.structured_data or []
    generic_types = {"Organization", "WebSite"}
    has_specific = any(s.get("@type") not in generic_types for s in schemas)
    passed = has_specific
    return RuleResult(
        rule_id="structured_data",
        name="Structured data present",
        passed=passed,
        weight=8,
        points=80 if passed else 0,
        max_points=80,
        category="performance",
        recommendation=None
        if passed
        else "Add page-specific structured data (e.g., Product, BreadcrumbList).",
    )


def _check_schema_completeness(data: PageSEOData) -> RuleResult:
    """Check that structured data has required Schema.org fields."""
    schemas = data.structured_data or []
    generic_types = {"Organization", "WebSite"}
    specific = [s for s in schemas if s.get("@type") not in generic_types]

    if not specific:
        return RuleResult(
            rule_id="schema_complete",
            name="Structured data fields complete",
            passed=False,
            weight=5,
            points=0,
            max_points=50,
            category="performance",
            recommendation="No page-specific structured data to validate.",
        )

    missing_fields: list[str] = []
    for schema in specific:
        schema_type = schema.get("@type", "")
        if schema_type == "Product":
            if not schema.get("name"):
                missing_fields.append("Product.name")
            if not schema.get("offers"):
                missing_fields.append("Product.offers")
            else:
                offers = schema["offers"]
                if isinstance(offers, dict):
                    if not offers.get("price"):
                        missing_fields.append("Product.offers.price")
                    if not offers.get("priceCurrency"):
                        missing_fields.append("Product.offers.priceCurrency")
        elif schema_type == "BreadcrumbList":
            if not schema.get("itemListElement"):
                missing_fields.append("BreadcrumbList.itemListElement")

    passed = len(missing_fields) == 0
    rec = None
    if not passed:
        rec = f"Structured data missing required fields: {', '.join(missing_fields)}."
    return RuleResult(
        rule_id="schema_complete",
        name="Structured data fields complete",
        passed=passed,
        weight=5,
        points=50 if passed else 0,
        max_points=50,
        category="performance",
        recommendation=rec,
    )


# ---------------------------------------------------------------------------
# All rules in evaluation order, grouped by category
# ---------------------------------------------------------------------------

_RULES = [
    # Content
    _check_title_present,
    _check_title_length,
    _check_desc_present,
    _check_desc_length,
    _check_content_length,
    _check_images_alt_text,
    _check_internal_links,
    _check_keyword_in_content,
    _check_readability_score,
    _check_keyword_density,
    _check_external_links_present,
    _check_title_h1_differentiated,
    _check_meta_desc_complete,
    # Technical
    _check_canonical,
    _check_canonical_self_ref,
    _check_indexable,
    _check_h1_present,
    _check_heading_hierarchy,
    _check_url_quality,
    _check_https_enforced,
    _check_viewport_present,
    _check_lang_attribute,
    _check_favicon_present,
    # Social
    _check_og_complete,
    _check_twitter_complete,
    _check_og_image_custom,
    _check_og_url_valid,
    # Performance / Schema
    _check_structured_data,
    _check_schema_completeness,
    _check_img_dimensions,
]


class RuleScoringProvider(ScoringProvider):
    """Rule-based on-page SEO scoring provider."""

    async def score_page(self, data: PageSEOData) -> ScoreResult:
        rules = [rule(data) for rule in _RULES]
        total_points = sum(r.points for r in rules)
        total_max = sum(r.max_points for r in rules)
        score = round(total_points / total_max * 100) if total_max > 0 else 0
        return ScoreResult(score=score, rules=rules, provider="rule_based")
