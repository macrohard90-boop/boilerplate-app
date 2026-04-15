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
            "og:image": "/img.png",
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
            {"@type": "Product", "name": "Test"},
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


@pytest.mark.asyncio
async def test_perfect_score(provider):
    """A page with all rules passing should score 100."""
    data = _make_page()
    result = await provider.score_page(data)
    assert isinstance(result, ScoreResult)
    assert result.score == 100
    assert all(r.passed for r in result.rules)
    assert result.provider == "rule_based"


@pytest.mark.asyncio
async def test_empty_page_scores_low(provider):
    """A page with no SEO data should score very low."""
    data = PageSEOData(path="empty")
    result = await provider.score_page(data)
    assert result.score < 30
    failed = [r for r in result.rules if not r.passed]
    assert len(failed) >= 6


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


@pytest.mark.asyncio
async def test_score_bounds(provider):
    """Score should always be between 0 and 100."""
    # Perfect page
    perfect = await provider.score_page(_make_page())
    assert 0 <= perfect.score <= 100

    # Empty page
    empty = await provider.score_page(PageSEOData(path=""))
    assert 0 <= empty.score <= 100


@pytest.mark.asyncio
async def test_rule_count(provider):
    """Should have exactly 10 rules."""
    result = await provider.score_page(_make_page())
    assert len(result.rules) == 10


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
