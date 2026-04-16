"""Unit tests for the SEO rule-based scoring provider."""

import pytest

from modules.seo.adapters.rule_scoring_provider import RuleScoringProvider
from modules.seo.interfaces.scoring_provider import PageSEOData, ScoreResult


@pytest.fixture
def provider():
    return RuleScoringProvider()


def _make_page(
    title="Great Product Name Here For Testing",
    description="This is a well-crafted description that is between one hundred and twenty and one hundred sixty characters long for optimal SEO display results.",
    canonical_url="https://example.com/products/test",
    robots="index, follow",
    og_tags=None,
    twitter_tags=None,
    structured_data=None,
    headings=None,
    **kwargs,
) -> PageSEOData:
    if og_tags is None:
        og_tags = {
            "og:title": "Test",
            "og:description": "Test desc",
            "og:image": "/custom-product-image.png",
        }
    if twitter_tags is None:
        twitter_tags = {
            "twitter:card": "summary_large_image",
            "twitter:title": "Test",
            "twitter:description": "Test desc",
        }
    if structured_data is None:
        structured_data = [
            {"@type": "Organization"},
            {"@type": "WebSite"},
            {
                "@type": "Product",
                "name": "Test Product",
                "offers": {
                    "@type": "Offer",
                    "price": "29.99",
                    "priceCurrency": "USD",
                },
            },
        ]
    return PageSEOData(
        path="products/test",
        title=title,
        description=description,
        canonical_url=canonical_url,
        robots=robots,
        og_tags=og_tags,
        twitter_tags=twitter_tags,
        structured_data=structured_data,
        headings=headings,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Core scoring tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_perfect_score(provider):
    """A page with all rules passing should score 100."""
    data = _make_page()
    result = await provider.score_page(data)
    assert isinstance(result, ScoreResult)
    # Find any failing rules for debug info
    failing = [r for r in result.rules if not r.passed]
    assert result.score == 100, f"Failing rules: {[(r.rule_id, r.recommendation) for r in failing]}"
    assert all(r.passed for r in result.rules)
    assert result.provider == "rule_based"


@pytest.mark.asyncio
async def test_empty_page_scores_low(provider):
    """A page with no SEO data should score very low."""
    data = PageSEOData(path="empty")
    result = await provider.score_page(data)
    assert result.score < 50
    failed = [r for r in result.rules if not r.passed]
    assert len(failed) >= 6


@pytest.mark.asyncio
async def test_score_bounds(provider):
    """Score should always be between 0 and 100."""
    perfect = await provider.score_page(_make_page())
    assert 0 <= perfect.score <= 100

    empty = await provider.score_page(PageSEOData(path=""))
    assert 0 <= empty.score <= 100


@pytest.mark.asyncio
async def test_rule_count(provider):
    """Should have exactly 30 rules."""
    result = await provider.score_page(_make_page())
    assert len(result.rules) == 30


@pytest.mark.asyncio
async def test_all_rules_have_required_fields(provider):
    result = await provider.score_page(_make_page())
    for r in result.rules:
        assert r.rule_id
        assert r.name
        assert isinstance(r.passed, bool)
        assert r.weight > 0
        assert r.max_points > 0
        assert r.points >= 0
        assert r.points <= r.max_points
        assert r.category in ("content", "technical", "social", "performance")


@pytest.mark.asyncio
async def test_all_rules_have_categories(provider):
    """Every rule should have a valid category."""
    result = await provider.score_page(_make_page())
    valid_categories = {"content", "technical", "social", "performance"}
    for r in result.rules:
        assert r.category in valid_categories, f"Rule {r.rule_id} has invalid category: {r.category}"


# ---------------------------------------------------------------------------
# Original 10 rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_title_present_rule(provider):
    """Missing title fails the title_present rule."""
    data = _make_page(title=None)
    result = await provider.score_page(data)
    title_rule = next(r for r in result.rules if r.rule_id == "title_present")
    assert not title_rule.passed
    assert title_rule.points == 0
    assert title_rule.recommendation is not None


@pytest.mark.asyncio
async def test_title_too_short(provider):
    data = _make_page(title="Hi")
    result = await provider.score_page(data)
    length_rule = next(r for r in result.rules if r.rule_id == "title_length")
    assert not length_rule.passed
    assert "too short" in length_rule.recommendation.lower()


@pytest.mark.asyncio
async def test_title_too_long(provider):
    data = _make_page(title="A" * 65)
    result = await provider.score_page(data)
    length_rule = next(r for r in result.rules if r.rule_id == "title_length")
    assert not length_rule.passed
    assert "too long" in length_rule.recommendation.lower()


@pytest.mark.asyncio
async def test_description_missing(provider):
    data = _make_page(description=None)
    result = await provider.score_page(data)
    desc_rule = next(r for r in result.rules if r.rule_id == "desc_present")
    assert not desc_rule.passed


@pytest.mark.asyncio
async def test_description_too_short(provider):
    data = _make_page(description="Short desc")
    result = await provider.score_page(data)
    length_rule = next(r for r in result.rules if r.rule_id == "desc_length")
    assert not length_rule.passed


@pytest.mark.asyncio
async def test_canonical_missing(provider):
    data = _make_page(canonical_url=None)
    result = await provider.score_page(data)
    canon_rule = next(r for r in result.rules if r.rule_id == "canonical_set")
    assert not canon_rule.passed


@pytest.mark.asyncio
async def test_og_incomplete(provider):
    data = _make_page(og_tags={"og:title": "Test"})  # missing desc + image
    result = await provider.score_page(data)
    og_rule = next(r for r in result.rules if r.rule_id == "og_complete")
    assert not og_rule.passed
    assert "og:description" in og_rule.recommendation
    assert "og:image" in og_rule.recommendation


@pytest.mark.asyncio
async def test_twitter_incomplete(provider):
    data = _make_page(twitter_tags={})
    result = await provider.score_page(data)
    tw_rule = next(r for r in result.rules if r.rule_id == "twitter_complete")
    assert not tw_rule.passed


@pytest.mark.asyncio
async def test_structured_data_generic_only(provider):
    """Only Organization + WebSite should fail the structured_data rule."""
    data = _make_page(
        structured_data=[{"@type": "Organization"}, {"@type": "WebSite"}]
    )
    result = await provider.score_page(data)
    sd_rule = next(r for r in result.rules if r.rule_id == "structured_data")
    assert not sd_rule.passed


@pytest.mark.asyncio
async def test_noindex_fails_indexable(provider):
    data = _make_page(robots="noindex, follow")
    result = await provider.score_page(data)
    robot_rule = next(r for r in result.rules if r.rule_id == "robots_indexable")
    assert not robot_rule.passed


@pytest.mark.asyncio
async def test_h1_present_with_crawl_data(provider):
    data = _make_page(headings=[{"tag": "h1", "text": "Product Title"}])
    result = await provider.score_page(data)
    h1_rule = next(r for r in result.rules if r.rule_id == "h1_present")
    assert h1_rule.passed


@pytest.mark.asyncio
async def test_h1_missing_with_crawl_data(provider):
    data = _make_page(headings=[{"tag": "h2", "text": "Subheading"}])
    result = await provider.score_page(data)
    h1_rule = next(r for r in result.rules if r.rule_id == "h1_present")
    assert not h1_rule.passed


@pytest.mark.asyncio
async def test_h1_auto_passes_without_crawl_data(provider):
    """Without crawl data (headings=None), H1 check gives benefit of the doubt."""
    data = _make_page(headings=None)
    result = await provider.score_page(data)
    h1_rule = next(r for r in result.rules if r.rule_id == "h1_present")
    assert h1_rule.passed


# ---------------------------------------------------------------------------
# New rule: heading_hierarchy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heading_hierarchy_auto_passes_without_crawl_data(provider):
    data = _make_page(headings=None)
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "heading_hierarchy")
    assert rule.passed
    assert rule.category == "technical"


@pytest.mark.asyncio
async def test_heading_hierarchy_valid(provider):
    data = _make_page(
        headings=[
            {"tag": "h1", "text": "Title"},
            {"tag": "h2", "text": "Section"},
            {"tag": "h3", "text": "Sub-section"},
        ]
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "heading_hierarchy")
    assert rule.passed


@pytest.mark.asyncio
async def test_heading_hierarchy_missing_h2(provider):
    data = _make_page(headings=[{"tag": "h1", "text": "Only H1"}])
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "heading_hierarchy")
    assert not rule.passed
    assert "H2" in rule.recommendation


@pytest.mark.asyncio
async def test_heading_hierarchy_skipped_level(provider):
    """H1 then H2 then H5 (skipping H3, H4) should fail."""
    data = _make_page(
        headings=[
            {"tag": "h1", "text": "Title"},
            {"tag": "h2", "text": "Section"},
            {"tag": "h5", "text": "Skipped to H5"},
        ]
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "heading_hierarchy")
    assert not rule.passed
    assert "skipped" in rule.recommendation.lower()


# ---------------------------------------------------------------------------
# New rule: url_quality
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_url_quality_clean(provider):
    data = _make_page()  # path="products/test" — clean
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "url_quality")
    assert rule.passed
    assert rule.category == "technical"


@pytest.mark.asyncio
async def test_url_quality_underscores(provider):
    data = PageSEOData(path="products/my_product_here")
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "url_quality")
    assert not rule.passed
    assert "underscores" in rule.recommendation.lower()


@pytest.mark.asyncio
async def test_url_quality_too_long(provider):
    data = PageSEOData(path="a/" * 60)
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "url_quality")
    assert not rule.passed
    assert "long" in rule.recommendation.lower()


@pytest.mark.asyncio
async def test_url_quality_special_chars(provider):
    data = PageSEOData(path="products/test?query=1&foo=bar")
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "url_quality")
    assert not rule.passed
    assert "special characters" in rule.recommendation.lower()


@pytest.mark.asyncio
async def test_url_quality_double_slashes(provider):
    data = PageSEOData(path="products//test")
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "url_quality")
    assert not rule.passed
    assert "double slashes" in rule.recommendation.lower()


# ---------------------------------------------------------------------------
# New rule: canonical_self_ref
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_canonical_self_ref_matching(provider):
    data = _make_page(
        canonical_url="https://example.com/products/test",
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "canonical_self_ref")
    assert rule.passed
    assert rule.category == "technical"


@pytest.mark.asyncio
async def test_canonical_self_ref_mismatch(provider):
    data = _make_page(
        canonical_url="https://example.com/other-page",
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "canonical_self_ref")
    assert not rule.passed
    assert "should point to this page" in rule.recommendation.lower()


@pytest.mark.asyncio
async def test_canonical_self_ref_missing_canonical(provider):
    data = _make_page(canonical_url=None)
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "canonical_self_ref")
    assert not rule.passed


# ---------------------------------------------------------------------------
# New rule: images_alt_text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_images_alt_text_auto_passes_no_crawl(provider):
    data = _make_page(images_without_alt=None)
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "images_alt_text")
    assert rule.passed
    assert rule.category == "content"


@pytest.mark.asyncio
async def test_images_alt_text_all_have_alt(provider):
    data = _make_page(images_without_alt=[])
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "images_alt_text")
    assert rule.passed


@pytest.mark.asyncio
async def test_images_alt_text_some_missing(provider):
    data = _make_page(images_without_alt=["/img1.png", "/img2.png"])
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "images_alt_text")
    assert not rule.passed
    assert "2 image(s)" in rule.recommendation


# ---------------------------------------------------------------------------
# New rule: content_length
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_content_length_auto_passes_no_crawl(provider):
    """No crawl data (content_length=0, headings=None) auto-passes."""
    data = _make_page(content_length=0, headings=None)
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "content_length")
    assert rule.passed
    assert rule.category == "content"


@pytest.mark.asyncio
async def test_content_length_product_page_sufficient(provider):
    """Product pages need >= 300 chars."""
    data = _make_page(content_length=350, headings=[{"tag": "h1", "text": "T"}])
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "content_length")
    assert rule.passed


@pytest.mark.asyncio
async def test_content_length_product_page_too_short(provider):
    data = _make_page(content_length=100, headings=[{"tag": "h1", "text": "T"}])
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "content_length")
    assert not rule.passed
    assert "100 characters" in rule.recommendation


@pytest.mark.asyncio
async def test_content_length_non_product_page(provider):
    """Non-product pages need >= 500 chars."""
    data = PageSEOData(
        path="about",
        content_length=400,
        headings=[{"tag": "h1", "text": "About"}],
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "content_length")
    assert not rule.passed
    assert "500" in rule.recommendation


# ---------------------------------------------------------------------------
# New rule: internal_links
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_internal_links_auto_passes_no_crawl(provider):
    data = _make_page(internal_links=0, headings=None)
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "internal_links")
    assert rule.passed
    assert rule.category == "content"


@pytest.mark.asyncio
async def test_internal_links_sufficient(provider):
    data = _make_page(internal_links=5, headings=[{"tag": "h1", "text": "T"}])
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "internal_links")
    assert rule.passed


@pytest.mark.asyncio
async def test_internal_links_insufficient(provider):
    data = _make_page(internal_links=1, headings=[{"tag": "h1", "text": "T"}])
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "internal_links")
    assert not rule.passed
    assert "1 internal link" in rule.recommendation


# ---------------------------------------------------------------------------
# New rule: keyword_in_content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_auto_passes_no_keywords(provider):
    """Pages with no target keywords auto-pass."""
    data = _make_page(target_keywords=None)
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "keyword_in_content")
    assert rule.passed
    assert rule.category == "content"


@pytest.mark.asyncio
async def test_keyword_in_title_and_desc(provider):
    """Keyword in both title and description = pass."""
    data = _make_page(
        title="Buy Energy Conference Tickets",
        description="Get your Energy Conference tickets today. Best prices for the Energy Conference in Canada with early bird deals.",
        target_keywords=["energy conference"],
        headings=[{"tag": "h1", "text": "Welcome"}],
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "keyword_in_content")
    assert rule.passed


@pytest.mark.asyncio
async def test_keyword_in_title_and_h1(provider):
    data = _make_page(
        title="Energy Conference 2026",
        description="Some description without the keyword present here at all for testing purposes and length.",
        target_keywords=["energy conference"],
        headings=[{"tag": "h1", "text": "Energy Conference"}],
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "keyword_in_content")
    assert rule.passed


@pytest.mark.asyncio
async def test_keyword_only_in_title(provider):
    """Keyword only in title (1 of 3) = fail."""
    data = _make_page(
        title="Energy Conference 2026",
        description="Some other description without the keyword at all for the purpose of this test that exceeds the min.",
        target_keywords=["energy conference"],
        headings=[{"tag": "h1", "text": "Welcome to Our Event"}],
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "keyword_in_content")
    assert not rule.passed
    assert "description" in rule.recommendation
    assert "H1" in rule.recommendation


@pytest.mark.asyncio
async def test_keyword_nowhere(provider):
    data = _make_page(
        title="Great Product Here",
        description="This is a well-crafted description that is between one hundred and twenty and one hundred sixty characters long for optimal SEO display results.",
        target_keywords=["energy conference"],
        headings=[{"tag": "h1", "text": "Products"}],
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "keyword_in_content")
    assert not rule.passed


# ---------------------------------------------------------------------------
# New rule: og_image_custom
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_og_image_custom_passes(provider):
    data = _make_page(
        og_tags={
            "og:title": "Test",
            "og:description": "Desc",
            "og:image": "/products/my-product.jpg",
        }
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "og_image_custom")
    assert rule.passed
    assert rule.category == "social"


@pytest.mark.asyncio
async def test_og_image_custom_fails_default(provider):
    data = _make_page(
        og_tags={
            "og:title": "Test",
            "og:description": "Desc",
            "og:image": "/images/og-default.png",
        }
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "og_image_custom")
    assert not rule.passed
    assert "default" in rule.recommendation.lower()


@pytest.mark.asyncio
async def test_og_image_custom_fails_no_image(provider):
    data = _make_page(og_tags={"og:title": "Test", "og:description": "Desc"})
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "og_image_custom")
    assert not rule.passed


# ---------------------------------------------------------------------------
# New rule: https_enforced
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_https_enforced_passes(provider):
    data = _make_page(canonical_url="https://example.com/products/test")
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "https_enforced")
    assert rule.passed
    assert rule.category == "technical"


@pytest.mark.asyncio
async def test_https_enforced_fails_http(provider):
    data = _make_page(canonical_url="http://example.com/products/test")
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "https_enforced")
    assert not rule.passed
    assert "HTTPS" in rule.recommendation


@pytest.mark.asyncio
async def test_https_enforced_auto_passes_localhost(provider):
    data = _make_page(canonical_url="http://localhost:3000/products/test")
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "https_enforced")
    assert rule.passed  # Dev environment auto-pass


@pytest.mark.asyncio
async def test_https_enforced_auto_passes_no_canonical(provider):
    data = _make_page(canonical_url=None)
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "https_enforced")
    assert rule.passed  # Can't check without URL


# ---------------------------------------------------------------------------
# New rule: schema_complete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schema_complete_product(provider):
    data = _make_page(
        structured_data=[
            {"@type": "Organization"},
            {"@type": "WebSite"},
            {
                "@type": "Product",
                "name": "Widget",
                "offers": {
                    "@type": "Offer",
                    "price": "10.00",
                    "priceCurrency": "USD",
                },
            },
        ]
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "schema_complete")
    assert rule.passed
    assert rule.category == "performance"


@pytest.mark.asyncio
async def test_schema_complete_product_missing_offers(provider):
    data = _make_page(
        structured_data=[
            {"@type": "Organization"},
            {"@type": "Product", "name": "Widget"},
        ]
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "schema_complete")
    assert not rule.passed
    assert "Product.offers" in rule.recommendation


@pytest.mark.asyncio
async def test_schema_complete_product_missing_price(provider):
    data = _make_page(
        structured_data=[
            {"@type": "Organization"},
            {
                "@type": "Product",
                "name": "Widget",
                "offers": {"@type": "Offer"},
            },
        ]
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "schema_complete")
    assert not rule.passed
    assert "price" in rule.recommendation.lower()


@pytest.mark.asyncio
async def test_schema_complete_breadcrumb(provider):
    data = _make_page(
        structured_data=[
            {"@type": "Organization"},
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home"},
                ],
            },
        ]
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "schema_complete")
    assert rule.passed


@pytest.mark.asyncio
async def test_schema_complete_breadcrumb_missing_items(provider):
    data = _make_page(
        structured_data=[
            {"@type": "Organization"},
            {"@type": "BreadcrumbList"},
        ]
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "schema_complete")
    assert not rule.passed
    assert "BreadcrumbList.itemListElement" in rule.recommendation


@pytest.mark.asyncio
async def test_schema_complete_no_specific_schemas(provider):
    """Only generic schemas = fail."""
    data = _make_page(
        structured_data=[{"@type": "Organization"}, {"@type": "WebSite"}]
    )
    result = await provider.score_page(data)
    rule = next(r for r in result.rules if r.rule_id == "schema_complete")
    assert not rule.passed
