"""Tests for the page discovery service."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from modules.seo.services.page_discovery_service import (
    _EXCLUDED_PREFIXES,
    scan_frontend_pages,
    collect_all_paths,
)


# ── scan_frontend_pages tests ───────────────────────────────


def _create_page_tree(base: Path, routes: list[str]) -> None:
    """Create a mock Next.js app directory with page.tsx files."""
    for route in routes:
        page_dir = base / route if route else base
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "page.tsx").write_text("export default function Page() {}")


@patch("modules.seo.services.page_discovery_service.settings")
def test_scan_discovers_static_pages(mock_settings):
    with tempfile.TemporaryDirectory() as tmpdir:
        app_dir = Path(tmpdir)
        mock_settings.frontend_app_dir = str(app_dir)

        _create_page_tree(app_dir, ["", "about", "contact", "events", "courses"])

        pages = scan_frontend_pages()
        paths = {p["path"] for p in pages}

        assert "" in paths  # homepage
        assert "about" in paths
        assert "contact" in paths
        assert "events" in paths
        assert "courses" in paths


@patch("modules.seo.services.page_discovery_service.settings")
def test_scan_discovers_nested_pages(mock_settings):
    with tempfile.TemporaryDirectory() as tmpdir:
        app_dir = Path(tmpdir)
        mock_settings.frontend_app_dir = str(app_dir)

        _create_page_tree(app_dir, ["", "products", "products/featured"])

        pages = scan_frontend_pages()
        paths = {p["path"] for p in pages}

        assert "products" in paths
        assert "products/featured" in paths


@patch("modules.seo.services.page_discovery_service.settings")
def test_scan_excludes_admin_auth_dashboard(mock_settings):
    with tempfile.TemporaryDirectory() as tmpdir:
        app_dir = Path(tmpdir)
        mock_settings.frontend_app_dir = str(app_dir)

        _create_page_tree(
            app_dir,
            [
                "",
                "about",
                "admin",
                "admin/users",
                "admin/seo/overview",
                "auth/login",
                "auth/register",
                "dashboard",
                "dashboard/profile",
                "merchant/register",
                "protected",
                "orders/123/pay",
                "cart",
                "checkout",
            ],
        )

        pages = scan_frontend_pages()
        paths = {p["path"] for p in pages}

        # Public pages should be included
        assert "" in paths
        assert "about" in paths

        # All excluded prefixes should be filtered out
        for prefix in _EXCLUDED_PREFIXES:
            excluded = [p for p in paths if p == prefix or p.startswith(f"{prefix}/")]
            assert len(excluded) == 0, f"Expected '{prefix}' to be excluded, found: {excluded}"


@patch("modules.seo.services.page_discovery_service.settings")
def test_scan_marks_dynamic_routes(mock_settings):
    with tempfile.TemporaryDirectory() as tmpdir:
        app_dir = Path(tmpdir)
        mock_settings.frontend_app_dir = str(app_dir)

        _create_page_tree(
            app_dir,
            [
                "",
                "products",
                "products/[slug]",
                "categories/[slug]",
            ],
        )

        pages = scan_frontend_pages()
        by_path = {p["path"]: p for p in pages}

        assert by_path[""]["is_dynamic"] is False
        assert by_path["products"]["is_dynamic"] is False
        assert by_path["products/[slug]"]["is_dynamic"] is True
        assert by_path["categories/[slug]"]["is_dynamic"] is True


@patch("modules.seo.services.page_discovery_service.settings")
def test_scan_handles_missing_directory(mock_settings):
    mock_settings.frontend_app_dir = "/nonexistent/path/frontend/app"
    pages = scan_frontend_pages()
    assert pages == []


@patch("modules.seo.services.page_discovery_service.settings")
def test_scan_returns_sorted(mock_settings):
    with tempfile.TemporaryDirectory() as tmpdir:
        app_dir = Path(tmpdir)
        mock_settings.frontend_app_dir = str(app_dir)

        _create_page_tree(app_dir, ["", "zebra", "about", "contact"])

        pages = scan_frontend_pages()
        paths = [p["path"] for p in pages]

        assert paths == sorted(paths)


# ── collect_all_paths tests ─────────────────────────────────


@pytest.mark.asyncio
async def test_collect_all_paths_returns_non_dynamic():
    """collect_all_paths queries the registry for non-dynamic pages."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        "", "about", "contact", "events", "products/shoe-1"
    ]
    mock_db.execute.return_value = mock_result

    paths = await collect_all_paths(mock_db)

    assert paths == ["", "about", "contact", "events", "products/shoe-1"]
    # Verify the query filters by is_dynamic = FALSE
    call_args = mock_db.execute.call_args
    query_text = str(call_args[0][0].text)
    assert "is_dynamic = FALSE" in query_text


@pytest.mark.asyncio
async def test_collect_all_paths_empty_registry():
    """collect_all_paths returns empty list when registry is empty."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    paths = await collect_all_paths(mock_db)
    assert paths == []
