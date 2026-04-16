"""Rule-based GEO scoring provider.

Scores pages 0-100 using weighted rules across 5 GEO dimensions:
- extractability: How easily AI engines can extract citable sentences
- fact_density: Statistical/data richness for AI synthesis
- authority: Outbound citations to credible sources, expert quotes
- freshness: Content recency signals
- metadata: Structured data stack depth (FAQ, Article, HowTo, etc.)

No external dependencies — works fully offline/local.
"""

import re
from datetime import datetime, timezone

from modules.seo.interfaces.geo_scoring_provider import (
    GEORuleResult,
    GEOScoreResult,
    GEOScoringProvider,
    PageGEOData,
)
from modules.seo.services.geo_html_analyzer import FILLER_OPENINGS


# ---------------------------------------------------------------------------
# Category: extractability
# ---------------------------------------------------------------------------


def _check_direct_answer_opening(data: PageGEOData) -> GEORuleResult:
    """First paragraph should be <=60 words with a direct answer."""
    text = data.first_paragraph_text.strip()
    wc = data.first_paragraph_word_count

    if not text:
        return GEORuleResult(
            rule_id="direct_answer_opening",
            name="Opening has direct answer",
            passed=False,
            weight=8,
            points=0,
            max_points=80,
            category="extractability",
            recommendation="Add an opening paragraph that directly answers the page's topic in 60 words or fewer.",
        )

    is_filler = bool(FILLER_OPENINGS.search(text))
    passed = wc <= 60 and not is_filler

    rec = None
    if is_filler:
        rec = (
            "The opening uses filler phrasing. Start with a direct statement that "
            "answers what the page is about — AI engines cite content that front-loads "
            "the answer."
        )
    elif wc > 60:
        rec = (
            f"Opening paragraph is {wc} words. Aim for 60 words or fewer with a "
            "direct answer — content cited by AI engines is front-loaded."
        )

    return GEORuleResult(
        rule_id="direct_answer_opening",
        name="Opening has direct answer",
        passed=passed,
        weight=8,
        points=80 if passed else 0,
        max_points=80,
        category="extractability",
        recommendation=rec,
    )


def _check_h2_question_format(data: PageGEOData) -> GEORuleResult:
    """>=50% of H2 headings should be phrased as questions."""
    headings = data.h2_headings or []
    total = len(headings)

    if total == 0:
        return GEORuleResult(
            rule_id="h2_question_format",
            name="H2s use question format",
            passed=False,
            weight=6,
            points=0,
            max_points=60,
            category="extractability",
            recommendation="Add H2 headings phrased as questions (e.g., 'What is...?', 'How do I...?'). AI engines map these directly to user queries.",
        )

    question_count = data.h2_question_count
    ratio = question_count / total
    passed = ratio >= 0.5

    rec = None
    if not passed:
        rec = (
            f"Only {question_count} of {total} H2 headings are questions "
            f"({ratio:.0%}). Rephrase H2s as questions to match how users query "
            "AI engines (e.g., 'What is SEO?' instead of 'SEO Overview')."
        )

    return GEORuleResult(
        rule_id="h2_question_format",
        name="H2s use question format",
        passed=passed,
        weight=6,
        points=60 if passed else 0,
        max_points=60,
        category="extractability",
        recommendation=rec,
    )


def _check_sections_self_contained(data: PageGEOData) -> GEORuleResult:
    """>=60% of H2 sections should have a direct answer in the first 2 sentences."""
    sections = data.h2_sections or []
    total = len(sections)

    if total == 0:
        return GEORuleResult(
            rule_id="sections_self_contained",
            name="Sections are self-contained",
            passed=False,
            weight=7,
            points=0,
            max_points=70,
            category="extractability",
            recommendation="Add H2 sections with content that directly addresses the heading topic in the first 1-2 sentences.",
        )

    self_contained = 0
    for section in sections:
        first_sentences = section.get("first_sentences", "")
        if not first_sentences:
            continue
        words = first_sentences.split()
        # A section is self-contained if the first 2 sentences have substance
        # (>10 words) and don't start with filler
        if len(words) >= 10 and not FILLER_OPENINGS.search(first_sentences):
            self_contained += 1

    ratio = self_contained / total
    passed = ratio >= 0.6

    rec = None
    if not passed:
        rec = (
            f"Only {self_contained} of {total} H2 sections answer their heading "
            f"immediately ({ratio:.0%}). Each section should be readable standalone — "
            "AI engines extract individual sections, not full pages."
        )

    return GEORuleResult(
        rule_id="sections_self_contained",
        name="Sections are self-contained",
        passed=passed,
        weight=7,
        points=70 if passed else 0,
        max_points=70,
        category="extractability",
        recommendation=rec,
    )


# ---------------------------------------------------------------------------
# Category: fact_density
# ---------------------------------------------------------------------------


def _check_stat_density(data: PageGEOData) -> GEORuleResult:
    """>=1 statistic/data point per 200 words."""
    wc = data.word_count
    stats = data.stat_pattern_count

    if wc < 100:
        return GEORuleResult(
            rule_id="stat_density",
            name="Statistics density",
            passed=False,
            weight=8,
            points=0,
            max_points=80,
            category="fact_density",
            recommendation="Page has too little content to assess statistic density. Add more content with data points.",
        )

    expected = max(1, wc // 200)
    passed = stats >= expected

    rec = None
    if not passed:
        rec = (
            f"Found {stats} statistics/data points in {wc} words "
            f"(expected {expected}+). Add concrete numbers, percentages, or data "
            "points — AI engines strongly prefer content with verifiable facts."
        )

    return GEORuleResult(
        rule_id="stat_density",
        name="Statistics density",
        passed=passed,
        weight=8,
        points=80 if passed else 0,
        max_points=80,
        category="fact_density",
        recommendation=rec,
    )


def _check_data_tables(data: PageGEOData) -> GEORuleResult:
    """Page contains at least one data table with headers."""
    passed = data.has_data_tables

    return GEORuleResult(
        rule_id="data_tables_present",
        name="Contains data tables",
        passed=passed,
        weight=5,
        points=50 if passed else 0,
        max_points=50,
        category="fact_density",
        recommendation=(
            None
            if passed
            else "Add a data table to present key information. Original data tables "
            "earn 4.1x more AI citations than narrative-only content."
        ),
    )


def _check_source_citations(data: PageGEOData) -> GEORuleResult:
    """>=50% of outbound links point to authority domains."""
    domains = data.outbound_domains or []
    total_external = len(domains)
    authority_count = data.authority_domain_count

    if total_external == 0:
        return GEORuleResult(
            rule_id="source_citations",
            name="Sources cite authorities",
            passed=False,
            weight=7,
            points=0,
            max_points=70,
            category="fact_density",
            recommendation="Add outbound links to authoritative sources (.edu, .gov, research papers, Wikipedia). AI engines weigh content higher when claims link to credible references.",
        )

    ratio = authority_count / total_external
    passed = ratio >= 0.5

    rec = None
    if not passed:
        rec = (
            f"Only {authority_count} of {total_external} outbound links go to "
            f"authority domains ({ratio:.0%}). Link more claims to .edu, .gov, "
            "Wikipedia, or peer-reviewed sources."
        )

    return GEORuleResult(
        rule_id="source_citations",
        name="Sources cite authorities",
        passed=passed,
        weight=7,
        points=70 if passed else 0,
        max_points=70,
        category="fact_density",
        recommendation=rec,
    )


# ---------------------------------------------------------------------------
# Category: authority
# ---------------------------------------------------------------------------


def _check_authority_outbound_links(data: PageGEOData) -> GEORuleResult:
    """>=3 outbound links to authority domains."""
    count = data.authority_domain_count
    passed = count >= 3

    rec = None
    if not passed:
        rec = (
            f"Only {count} authority domain link(s) found. Add links to .edu, .gov, "
            "Wikipedia, or academic sources — AI engines cite pages that reference "
            "credible sources 40% more often."
        )

    return GEORuleResult(
        rule_id="authority_outbound_links",
        name="Authority outbound links",
        passed=passed,
        weight=8,
        points=80 if passed else 0,
        max_points=80,
        category="authority",
        recommendation=rec,
    )


def _check_expert_quotes(data: PageGEOData) -> GEORuleResult:
    """Content contains expert quotations with attribution."""
    has_quotes = data.has_blockquotes or data.quote_attribution_count > 0
    passed = has_quotes

    return GEORuleResult(
        rule_id="expert_quotes",
        name="Expert quotations present",
        passed=passed,
        weight=6,
        points=60 if passed else 0,
        max_points=60,
        category="authority",
        recommendation=(
            None
            if passed
            else "Add expert quotes with attribution (e.g., 'According to [Expert Name], ...'). "
            "Expert quotations boost AI citation likelihood by up to 41%."
        ),
    )


def _check_content_depth(data: PageGEOData) -> GEORuleResult:
    """Content has substantial depth (>=800 words for standard pages)."""
    wc = data.word_count
    # Product pages need less content
    is_product = data.path and (
        "product" in data.path.lower() or "shop" in data.path.lower()
    )
    threshold = 300 if is_product else 800
    passed = wc >= threshold

    rec = None
    if not passed:
        rec = (
            f"Page has {wc} words (need {threshold}+). AI engines prefer "
            "substantial, in-depth content. Expand with more details, examples, "
            "and data points."
        )

    return GEORuleResult(
        rule_id="content_depth",
        name="Content depth",
        passed=passed,
        weight=5,
        points=50 if passed else 0,
        max_points=50,
        category="authority",
        recommendation=rec,
    )


# ---------------------------------------------------------------------------
# Category: freshness
# ---------------------------------------------------------------------------


def _check_date_modified_present(data: PageGEOData) -> GEORuleResult:
    """Article/BlogPosting schema includes dateModified."""
    has_article = data.has_article_schema
    has_date = data.article_has_date_modified

    if not has_article:
        return GEORuleResult(
            rule_id="date_modified_present",
            name="dateModified in schema",
            passed=False,
            weight=7,
            points=0,
            max_points=70,
            category="freshness",
            recommendation="Add Article or BlogPosting schema with a dateModified field. AI engines use this to assess content freshness — 50% of cited content is less than 13 weeks old.",
        )

    passed = has_date

    return GEORuleResult(
        rule_id="date_modified_present",
        name="dateModified in schema",
        passed=passed,
        weight=7,
        points=70 if passed else 0,
        max_points=70,
        category="freshness",
        recommendation=(
            None
            if passed
            else "Add dateModified to your Article schema. AI engines strongly "
            "prefer recently updated content."
        ),
    )


def _check_content_recency(data: PageGEOData) -> GEORuleResult:
    """Content updated within 90 days."""
    updated_at = data.content_updated_at
    if not updated_at:
        return GEORuleResult(
            rule_id="content_recency",
            name="Content updated recently",
            passed=False,
            weight=8,
            points=0,
            max_points=80,
            category="freshness",
            recommendation="No update date found. Add dateModified to schema markup and keep content updated quarterly — pages not updated within 90 days are 3x more likely to lose AI citations.",
        )

    try:
        if isinstance(updated_at, str):
            # Parse ISO date formats
            updated_at_clean = updated_at.replace("Z", "+00:00")
            dt = datetime.fromisoformat(updated_at_clean)
        else:
            dt = updated_at

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        days_old = (now - dt).days
        passed = days_old <= 90

        rec = None
        if not passed:
            rec = (
                f"Content was last updated {days_old} days ago. AI engines "
                "strongly favor content updated within 90 days. Refresh with "
                "current data and update the dateModified field."
            )

        return GEORuleResult(
            rule_id="content_recency",
            name="Content updated recently",
            passed=passed,
            weight=8,
            points=80 if passed else 0,
            max_points=80,
            category="freshness",
            recommendation=rec,
        )
    except (ValueError, TypeError):
        return GEORuleResult(
            rule_id="content_recency",
            name="Content updated recently",
            passed=False,
            weight=8,
            points=0,
            max_points=80,
            category="freshness",
            recommendation="Could not parse the content update date. Ensure dateModified is in ISO 8601 format.",
        )


def _check_stale_references(data: PageGEOData) -> GEORuleResult:
    """Body text doesn't contain year references >2 years old."""
    stale = data.stale_year_references or []
    # Deduplicate
    unique_stale = sorted(set(stale))
    passed = len(unique_stale) == 0

    rec = None
    if not passed:
        years_str = ", ".join(unique_stale[:5])
        rec = (
            f"Found references to outdated years: {years_str}. "
            "Update these with current data or add context (e.g., 'historically' "
            "or 'as of 2026'). Stale content signals reduce AI citation likelihood."
        )

    return GEORuleResult(
        rule_id="no_stale_references",
        name="No stale year references",
        passed=passed,
        weight=4,
        points=40 if passed else 0,
        max_points=40,
        category="freshness",
        recommendation=rec,
    )


# ---------------------------------------------------------------------------
# Category: metadata
# ---------------------------------------------------------------------------


def _check_faq_schema(data: PageGEOData) -> GEORuleResult:
    """FAQPage schema present with >=2 questions."""
    has_faq = data.has_faq_schema
    q_count = data.faq_question_count
    passed = has_faq and q_count >= 2

    rec = None
    if not has_faq:
        rec = (
            "Add FAQPage schema markup with at least 2 questions. FAQPage schema "
            "directly maps to how users query AI engines and increases citations by 28%."
        )
    elif q_count < 2:
        rec = f"FAQPage schema has only {q_count} question(s). Add at least 2 for meaningful coverage."

    return GEORuleResult(
        rule_id="faq_schema",
        name="FAQPage schema present",
        passed=passed,
        weight=8,
        points=80 if passed else 0,
        max_points=80,
        category="metadata",
        recommendation=rec,
    )


def _check_article_schema(data: PageGEOData) -> GEORuleResult:
    """Article schema with author, datePublished, and dateModified."""
    if not data.has_article_schema:
        return GEORuleResult(
            rule_id="article_schema_complete",
            name="Article schema with author",
            passed=False,
            weight=7,
            points=0,
            max_points=70,
            category="metadata",
            recommendation="Add Article or BlogPosting schema with author, datePublished, and dateModified. This helps AI engines attribute and verify your content.",
        )

    has_all = (
        data.article_has_author
        and data.article_has_date_published
        and data.article_has_date_modified
    )

    rec = None
    if not has_all:
        missing = []
        if not data.article_has_author:
            missing.append("author")
        if not data.article_has_date_published:
            missing.append("datePublished")
        if not data.article_has_date_modified:
            missing.append("dateModified")
        rec = f"Article schema is missing: {', '.join(missing)}. Complete all fields for full AI engine trust."

    return GEORuleResult(
        rule_id="article_schema_complete",
        name="Article schema with author",
        passed=has_all,
        weight=7,
        points=70 if has_all else 0,
        max_points=70,
        category="metadata",
        recommendation=rec,
    )


def _check_schema_stack_depth(data: PageGEOData) -> GEORuleResult:
    """Has >=2 distinct schema types."""
    count = data.schema_type_count
    passed = count >= 2

    rec = None
    if not passed:
        rec = (
            f"Only {count} schema type(s) found. Pages with 2+ schema types "
            "(e.g., Article + FAQPage, or Article + BreadcrumbList) receive 1.8x "
            "more AI citations. Add FAQPage, HowTo, or BreadcrumbList schema."
        )

    return GEORuleResult(
        rule_id="schema_stack_depth",
        name="Multiple schema types",
        passed=passed,
        weight=6,
        points=60 if passed else 0,
        max_points=60,
        category="metadata",
        recommendation=rec,
    )


# ---------------------------------------------------------------------------
# Provider class
# ---------------------------------------------------------------------------


_ALL_RULES = [
    # Extractability
    _check_direct_answer_opening,
    _check_h2_question_format,
    _check_sections_self_contained,
    # Fact density
    _check_stat_density,
    _check_data_tables,
    _check_source_citations,
    # Authority
    _check_authority_outbound_links,
    _check_expert_quotes,
    _check_content_depth,
    # Freshness
    _check_date_modified_present,
    _check_content_recency,
    _check_stale_references,
    # Metadata
    _check_faq_schema,
    _check_article_schema,
    _check_schema_stack_depth,
]

# Category groupings for dimension score calculation
_CATEGORIES = [
    "extractability",
    "fact_density",
    "authority",
    "freshness",
    "metadata",
]


class GEORuleScoringProvider(GEOScoringProvider):
    """Rule-based GEO scoring: 15 rules across 5 dimensions."""

    async def score_page(self, data: PageGEOData) -> GEOScoreResult:
        rules: list[GEORuleResult] = []
        for check_fn in _ALL_RULES:
            rules.append(check_fn(data))

        # Calculate total score
        total_points = sum(r.points for r in rules)
        total_max = sum(r.max_points for r in rules)
        score = round(total_points * 100 / total_max) if total_max > 0 else 0

        # Calculate per-dimension scores (0-100)
        dimension_scores: dict[str, int] = {}
        for cat in _CATEGORIES:
            cat_rules = [r for r in rules if r.category == cat]
            cat_points = sum(r.points for r in cat_rules)
            cat_max = sum(r.max_points for r in cat_rules)
            dimension_scores[cat] = (
                round(cat_points * 100 / cat_max) if cat_max > 0 else 0
            )

        return GEOScoreResult(
            score=score,
            rules=rules,
            provider="geo_rule_based",
            dimension_scores=dimension_scores,
        )
