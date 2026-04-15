"""Unit tests for the SEO rescorer background task."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.seo.services.rescorer import rescore_all_pages


@pytest.mark.asyncio
@patch("modules.seo.services.rescorer.get_session_factory")
@patch("modules.seo.services.snapshot_service.take_snapshot", new_callable=AsyncMock)
@patch("modules.seo.services.scoring_service.score_page", new_callable=AsyncMock)
@patch("modules.seo.services.scoring_service._collect_all_paths", new_callable=AsyncMock)
async def test_rescore_all_pages_scores_each_path(
    mock_collect, mock_score, mock_snapshot, mock_factory
):
    """Rescorer should score every collected path."""
    mock_collect.return_value = ["products/a", "products/b", "categories/c"]

    mock_result = MagicMock()
    mock_result.score = 85
    mock_score.return_value = mock_result

    # Setup async context manager for session factory
    mock_session = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_factory.return_value = MagicMock(return_value=mock_cm)

    count = await rescore_all_pages()
    assert count == 3
    assert mock_score.call_count == 3
    assert mock_snapshot.call_count == 3


@pytest.mark.asyncio
@patch("modules.seo.services.rescorer.get_session_factory")
@patch("modules.seo.services.snapshot_service.take_snapshot", new_callable=AsyncMock)
@patch("modules.seo.services.scoring_service.score_page", new_callable=AsyncMock)
@patch("modules.seo.services.scoring_service._collect_all_paths", new_callable=AsyncMock)
async def test_rescore_continues_on_error(
    mock_collect, mock_score, mock_snapshot, mock_factory
):
    """Rescorer should continue scoring other pages if one fails."""
    mock_collect.return_value = ["products/a", "products/fail", "products/b"]

    mock_result = MagicMock()
    mock_result.score = 85

    def side_effect(db, path):
        if path == "products/fail":
            raise Exception("DB error")
        return mock_result

    mock_score.side_effect = side_effect

    mock_session = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_factory.return_value = MagicMock(return_value=mock_cm)

    count = await rescore_all_pages()
    assert count == 2  # 2 succeeded, 1 failed
    assert mock_score.call_count == 3  # All 3 attempted


@pytest.mark.asyncio
@patch("modules.seo.services.rescorer.get_session_factory")
@patch("modules.seo.services.scoring_service._collect_all_paths", new_callable=AsyncMock)
async def test_rescore_empty_paths(mock_collect, mock_factory):
    """Rescorer should handle no pages gracefully."""
    mock_collect.return_value = []

    mock_session = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_factory.return_value = MagicMock(return_value=mock_cm)

    count = await rescore_all_pages()
    assert count == 0
