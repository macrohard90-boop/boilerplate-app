"""SEO adapter factories."""

from modules.seo.interfaces.scoring_provider import ScoringProvider


def get_scoring_provider() -> ScoringProvider:
    """Return the configured scoring provider."""
    from modules.seo.adapters.rule_scoring_provider import RuleScoringProvider

    return RuleScoringProvider()
