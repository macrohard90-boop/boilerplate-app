"""SEO module interfaces."""

from modules.seo.interfaces.scoring_provider import (
    PageSEOData,
    RuleResult,
    ScoreResult,
    ScoringProvider,
)

__all__ = ["ScoringProvider", "PageSEOData", "ScoreResult", "RuleResult"]
