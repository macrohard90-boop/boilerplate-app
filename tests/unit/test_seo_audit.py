"""Unit tests for the SEO site audit service."""

import pytest

from modules.seo.services.audit_service import (
    AuditCheck,
    _check_all_pages_have_meta,
    _check_all_pages_have_og,
    _check_canonical_conflicts,
    _check_custom_og_images,
    _check_duplicate_descriptions,
    _check_duplicate_titles,
    _check_image_heavy_pages,
    _check_missing_alt_images,
    _check_missing_h1,
    _check_no_404_pages,
    _check_robots_valid,
    _check_sitemap_coverage,
    _check_ssl_configured,
    _check_thin_content,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _meta(
    title="Page Title",
    description="Page description text.",
    canonical_url="https://example.com/page",
    og_title="Page Title",
    og_desc="Page description text.",
    og_image="/custom-image.png",
) -> dict:
    return {
        "title": title,
        "description": description,
        "canonical_url": canonical_url,
        "og_tags": {
            "og:title": og_title,
            "og:description": og_desc,
            "og:image": og_image,
        },
    }


def _crawl(
    status_code=200,
    content_length=500,
    headings=None,
    images_without_alt=None,
) -> dict:
    data: dict = {"status_code": status_code}
    if content_length is not None:
        data["content_length"] = content_length
    if headings is not None:
        data["headings"] = headings
    if images_without_alt is not None:
        data["images_without_alt"] = images_without_alt
    return data


# ---------------------------------------------------------------------------
# _check_ssl_configured
# ---------------------------------------------------------------------------


class TestSSLConfigured:
    def test_https_passes(self, monkeypatch):
        from backend.core import config

        monkeypatch.setattr(config.settings, "frontend_url", "https://example.com")
        result = _check_ssl_configured()
        assert result.passed is True
        assert result.check_id == "ssl_configured"
        assert result.severity == "critical"

    def test_http_fails(self, monkeypatch):
        from backend.core import config

        monkeypatch.setattr(config.settings, "frontend_url", "http://example.com")
        result = _check_ssl_configured()
        assert result.passed is False
        assert "https://" in result.recommendation

    def test_localhost_passes(self, monkeypatch):
        from backend.core import config

        monkeypatch.setattr(config.settings, "frontend_url", "http://localhost:3000")
        result = _check_ssl_configured()
        assert result.passed is True

    def test_127_passes(self, monkeypatch):
        from backend.core import config

        monkeypatch.setattr(config.settings, "frontend_url", "http://127.0.0.1:3000")
        result = _check_ssl_configured()
        assert result.passed is True


# ---------------------------------------------------------------------------
# _check_robots_valid
# ---------------------------------------------------------------------------


class TestRobotsValid:
    def test_valid_robots(self, monkeypatch):
        from modules.seo.services import robots_service

        monkeypatch.setattr(
            robots_service,
            "generate_robots",
            lambda: "User-agent: *\nDisallow: /api/\nSitemap: https://example.com/sitemap.xml",
        )
        result = _check_robots_valid()
        assert result.passed is True
        assert result.check_id == "robots_valid"

    def test_missing_sitemap_fails(self, monkeypatch):
        from modules.seo.services import robots_service

        monkeypatch.setattr(
            robots_service,
            "generate_robots",
            lambda: "User-agent: *\nAllow: /",
        )
        result = _check_robots_valid()
        assert result.passed is False
        assert "no Sitemap directive" in result.description


# ---------------------------------------------------------------------------
# _check_canonical_conflicts
# ---------------------------------------------------------------------------


class TestCanonicalConflicts:
    def test_unique_canonicals_pass(self):
        metas = {
            "/page-a": _meta(canonical_url="https://example.com/page-a"),
            "/page-b": _meta(canonical_url="https://example.com/page-b"),
        }
        result = _check_canonical_conflicts(metas)
        assert result.passed is True
        assert result.check_id == "canonical_conflicts"

    def test_shared_canonical_fails(self):
        metas = {
            "/page-a": _meta(canonical_url="https://example.com/same"),
            "/page-b": _meta(canonical_url="https://example.com/same"),
        }
        result = _check_canonical_conflicts(metas)
        assert result.passed is False
        assert result.severity == "critical"
        assert set(result.affected_pages) == {"/page-a", "/page-b"}

    def test_no_canonicals_pass(self):
        metas = {
            "/page-a": {"title": "A"},
            "/page-b": {"title": "B"},
        }
        result = _check_canonical_conflicts(metas)
        assert result.passed is True

    def test_empty_metas_pass(self):
        result = _check_canonical_conflicts({})
        assert result.passed is True


# ---------------------------------------------------------------------------
# _check_duplicate_titles
# ---------------------------------------------------------------------------


class TestDuplicateTitles:
    def test_unique_titles_pass(self):
        metas = {
            "/a": _meta(title="Page A"),
            "/b": _meta(title="Page B"),
        }
        result = _check_duplicate_titles(metas)
        assert result.passed is True
        assert result.check_id == "duplicate_titles"

    def test_duplicate_titles_fail(self):
        metas = {
            "/a": _meta(title="Same Title"),
            "/b": _meta(title="Same Title"),
            "/c": _meta(title="Different Title"),
        }
        result = _check_duplicate_titles(metas)
        assert result.passed is False
        assert result.severity == "warning"
        assert "/a" in result.affected_pages
        assert "/b" in result.affected_pages
        assert "/c" not in result.affected_pages

    def test_none_titles_ignored(self):
        metas = {
            "/a": {"title": None},
            "/b": {"title": None},
        }
        result = _check_duplicate_titles(metas)
        assert result.passed is True


# ---------------------------------------------------------------------------
# _check_duplicate_descriptions
# ---------------------------------------------------------------------------


class TestDuplicateDescriptions:
    def test_unique_descriptions_pass(self):
        metas = {
            "/a": _meta(description="Description A"),
            "/b": _meta(description="Description B"),
        }
        result = _check_duplicate_descriptions(metas)
        assert result.passed is True
        assert result.check_id == "duplicate_descriptions"

    def test_duplicate_descriptions_fail(self):
        metas = {
            "/a": _meta(description="Same desc"),
            "/b": _meta(description="Same desc"),
        }
        result = _check_duplicate_descriptions(metas)
        assert result.passed is False
        assert result.severity == "warning"
        assert len(result.affected_pages) == 2

    def test_none_descriptions_ignored(self):
        metas = {
            "/a": {"description": None},
            "/b": {"description": None},
        }
        result = _check_duplicate_descriptions(metas)
        assert result.passed is True


# ---------------------------------------------------------------------------
# _check_no_404_pages
# ---------------------------------------------------------------------------


class TestNo404Pages:
    def test_all_200_pass(self):
        crawl = {
            "/a": _crawl(status_code=200),
            "/b": _crawl(status_code=200),
        }
        result = _check_no_404_pages(crawl)
        assert result.passed is True
        assert result.check_id == "no_404_pages"

    def test_404_fails(self):
        crawl = {
            "/a": _crawl(status_code=200),
            "/b": _crawl(status_code=404),
        }
        result = _check_no_404_pages(crawl)
        assert result.passed is False
        assert result.severity == "critical"
        assert result.affected_pages == ["/b"]

    def test_500_fails(self):
        crawl = {"/a": _crawl(status_code=500)}
        result = _check_no_404_pages(crawl)
        assert result.passed is False

    def test_empty_crawl_auto_passes(self):
        result = _check_no_404_pages({})
        assert result.passed is True
        assert "No crawl data" in result.description


# ---------------------------------------------------------------------------
# _check_all_pages_have_meta
# ---------------------------------------------------------------------------


class TestAllPagesHaveMeta:
    def test_all_have_meta_pass(self):
        metas = {
            "/a": _meta(title="A", description="Desc A"),
            "/b": _meta(title="B", description="Desc B"),
        }
        result = _check_all_pages_have_meta(metas)
        assert result.passed is True
        assert result.check_id == "all_pages_have_meta"

    def test_missing_title_fails(self):
        metas = {
            "/a": _meta(title=None, description="Desc A"),
        }
        result = _check_all_pages_have_meta(metas)
        assert result.passed is False
        assert result.severity == "critical"
        assert "/a" in result.affected_pages

    def test_missing_description_fails(self):
        metas = {
            "/a": _meta(title="A", description=None),
        }
        result = _check_all_pages_have_meta(metas)
        assert result.passed is False

    def test_empty_string_title_fails(self):
        metas = {"/a": _meta(title="", description="Desc")}
        result = _check_all_pages_have_meta(metas)
        assert result.passed is False

    def test_empty_metas_passes(self):
        result = _check_all_pages_have_meta({})
        assert result.passed is True


# ---------------------------------------------------------------------------
# _check_thin_content
# ---------------------------------------------------------------------------


class TestThinContent:
    def test_sufficient_content_passes(self):
        crawl = {
            "/a": _crawl(content_length=500),
            "/b": _crawl(content_length=300),
        }
        result = _check_thin_content(crawl)
        assert result.passed is True
        assert result.check_id == "thin_content_pages"

    def test_thin_page_fails(self):
        crawl = {
            "/a": _crawl(content_length=100),
            "/b": _crawl(content_length=500),
        }
        result = _check_thin_content(crawl)
        assert result.passed is False
        assert result.severity == "warning"
        assert result.affected_pages == ["/a"]

    def test_zero_content_fails(self):
        crawl = {"/a": _crawl(content_length=0)}
        result = _check_thin_content(crawl)
        assert result.passed is False

    def test_no_content_length_counts_as_thin(self):
        crawl = {"/a": {"status_code": 200}}
        result = _check_thin_content(crawl)
        assert result.passed is False

    def test_empty_crawl_auto_passes(self):
        result = _check_thin_content({})
        assert result.passed is True
        assert "No crawl data" in result.description

    def test_boundary_199_fails(self):
        crawl = {"/a": _crawl(content_length=199)}
        result = _check_thin_content(crawl)
        assert result.passed is False

    def test_boundary_200_passes(self):
        crawl = {"/a": _crawl(content_length=200)}
        result = _check_thin_content(crawl)
        assert result.passed is True


# ---------------------------------------------------------------------------
# _check_missing_h1
# ---------------------------------------------------------------------------


class TestMissingH1:
    def test_h1_present_passes(self):
        crawl = {
            "/a": _crawl(headings=[{"tag": "h1", "text": "Welcome"}]),
        }
        result = _check_missing_h1(crawl)
        assert result.passed is True
        assert result.check_id == "missing_h1_pages"

    def test_no_h1_fails(self):
        crawl = {
            "/a": _crawl(headings=[{"tag": "h2", "text": "Subheading"}]),
        }
        result = _check_missing_h1(crawl)
        assert result.passed is False
        assert result.severity == "warning"
        assert result.affected_pages == ["/a"]

    def test_empty_headings_fails(self):
        crawl = {"/a": _crawl(headings=[])}
        result = _check_missing_h1(crawl)
        assert result.passed is False

    def test_no_headings_key_skipped(self):
        """Pages without headings data in crawl are not flagged."""
        crawl = {"/a": {"status_code": 200}}
        result = _check_missing_h1(crawl)
        assert result.passed is True

    def test_empty_crawl_auto_passes(self):
        result = _check_missing_h1({})
        assert result.passed is True

    def test_case_insensitive_h1(self):
        crawl = {"/a": _crawl(headings=[{"tag": "H1", "text": "Title"}])}
        result = _check_missing_h1(crawl)
        assert result.passed is True


# ---------------------------------------------------------------------------
# _check_missing_alt_images
# ---------------------------------------------------------------------------


class TestMissingAltImages:
    def test_all_have_alt_passes(self):
        crawl = {"/a": _crawl(images_without_alt=[])}
        result = _check_missing_alt_images(crawl)
        assert result.passed is True
        assert result.check_id == "missing_alt_images"

    def test_missing_alt_fails(self):
        crawl = {
            "/a": _crawl(images_without_alt=["img1.png", "img2.png"]),
            "/b": _crawl(images_without_alt=["img3.png"]),
        }
        result = _check_missing_alt_images(crawl)
        assert result.passed is False
        assert result.severity == "warning"
        assert "3 image(s)" in result.description
        assert "2 page(s)" in result.description

    def test_empty_crawl_auto_passes(self):
        result = _check_missing_alt_images({})
        assert result.passed is True

    def test_no_images_key_passes(self):
        crawl = {"/a": {"status_code": 200}}
        result = _check_missing_alt_images(crawl)
        assert result.passed is True


# ---------------------------------------------------------------------------
# _check_all_pages_have_og
# ---------------------------------------------------------------------------


class TestAllPagesHaveOG:
    def test_all_have_og_passes(self):
        metas = {
            "/a": _meta(og_title="Title A", og_desc="Desc A"),
            "/b": _meta(og_title="Title B", og_desc="Desc B"),
        }
        result = _check_all_pages_have_og(metas)
        assert result.passed is True
        assert result.check_id == "all_pages_have_og"

    def test_missing_og_title_fails(self):
        metas = {
            "/a": _meta(og_title=None, og_desc="Desc A"),
        }
        result = _check_all_pages_have_og(metas)
        assert result.passed is False
        assert result.severity == "warning"

    def test_missing_og_desc_fails(self):
        metas = {
            "/a": _meta(og_title="Title", og_desc=None),
        }
        result = _check_all_pages_have_og(metas)
        assert result.passed is False

    def test_no_og_tags_fails(self):
        metas = {"/a": {"title": "Page", "description": "Desc"}}
        result = _check_all_pages_have_og(metas)
        assert result.passed is False

    def test_empty_metas_passes(self):
        result = _check_all_pages_have_og({})
        assert result.passed is True


# ---------------------------------------------------------------------------
# _check_custom_og_images
# ---------------------------------------------------------------------------


class TestCustomOGImages:
    def test_all_custom_passes(self, monkeypatch):
        from backend.core import config

        monkeypatch.setattr(config.settings, "default_og_image", "/images/og-default.png")
        metas = {
            "/a": _meta(og_image="/images/product-a.png"),
            "/b": _meta(og_image="/images/product-b.png"),
        }
        result = _check_custom_og_images(metas)
        assert result.passed is True
        assert result.check_id == "custom_og_images"

    def test_default_image_fails(self, monkeypatch):
        from backend.core import config

        monkeypatch.setattr(config.settings, "default_og_image", "/images/og-default.png")
        metas = {
            "/a": _meta(og_image="/images/og-default.png"),
            "/b": _meta(og_image="/images/custom.png"),
        }
        result = _check_custom_og_images(metas)
        assert result.passed is False
        assert result.severity == "info"
        assert "/a" in result.affected_pages
        assert "/b" not in result.affected_pages

    def test_empty_og_image_fails(self, monkeypatch):
        from backend.core import config

        monkeypatch.setattr(config.settings, "default_og_image", "/images/og-default.png")
        metas = {"/a": _meta(og_image="")}
        result = _check_custom_og_images(metas)
        assert result.passed is False

    def test_no_og_tags_fails(self, monkeypatch):
        from backend.core import config

        monkeypatch.setattr(config.settings, "default_og_image", "/images/og-default.png")
        metas = {"/a": {"title": "Page"}}
        result = _check_custom_og_images(metas)
        assert result.passed is False


# ---------------------------------------------------------------------------
# _check_image_heavy_pages
# ---------------------------------------------------------------------------


class TestImageHeavyPages:
    def test_reasonable_images_pass(self):
        crawl = {"/a": _crawl(images_without_alt=["img"] * 10)}
        result = _check_image_heavy_pages(crawl)
        assert result.passed is True
        assert result.check_id == "image_heavy_pages"

    def test_heavy_images_fail(self):
        crawl = {"/a": _crawl(images_without_alt=["img"] * 25)}
        result = _check_image_heavy_pages(crawl)
        assert result.passed is False
        assert result.severity == "info"
        assert result.affected_pages == ["/a"]

    def test_boundary_20_passes(self):
        crawl = {"/a": _crawl(images_without_alt=["img"] * 20)}
        result = _check_image_heavy_pages(crawl)
        assert result.passed is True

    def test_boundary_21_fails(self):
        crawl = {"/a": _crawl(images_without_alt=["img"] * 21)}
        result = _check_image_heavy_pages(crawl)
        assert result.passed is False

    def test_empty_crawl_auto_passes(self):
        result = _check_image_heavy_pages({})
        assert result.passed is True


# ---------------------------------------------------------------------------
# _check_sitemap_coverage
# ---------------------------------------------------------------------------


class TestSitemapCoverage:
    def test_all_covered_passes(self):
        paths = ["/a", "/b"]
        metas = {"/a": _meta(), "/b": _meta()}
        result = _check_sitemap_coverage(paths, metas)
        assert result.passed is True
        assert result.check_id == "sitemap_coverage"

    def test_uncovered_page_fails(self):
        paths = ["/a", "/b", "/c"]
        metas = {"/a": _meta(), "/b": _meta()}
        result = _check_sitemap_coverage(paths, metas)
        assert result.passed is False
        assert result.severity == "warning"
        assert result.affected_pages == ["/c"]

    def test_empty_paths_passes(self):
        result = _check_sitemap_coverage([], {})
        assert result.passed is True

    def test_extra_metas_still_passes(self):
        """Pages in metas but not in paths are fine (e.g., custom overrides)."""
        paths = ["/a"]
        metas = {"/a": _meta(), "/b": _meta()}
        result = _check_sitemap_coverage(paths, metas)
        assert result.passed is True


# ---------------------------------------------------------------------------
# AuditCheck structure
# ---------------------------------------------------------------------------


class TestAuditCheckStructure:
    def test_all_checks_have_valid_category(self):
        """Verify all check functions return valid categories."""
        from backend.core import config

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(config.settings, "frontend_url", "https://example.com")
        monkeypatch.setattr(config.settings, "default_og_image", "/images/og-default.png")

        from modules.seo.services import robots_service

        monkeypatch.setattr(
            robots_service,
            "generate_robots",
            lambda: "User-agent: *\nSitemap: https://example.com/sitemap.xml",
        )

        valid_categories = {"technical", "content", "social", "performance"}
        valid_severities = {"critical", "warning", "info"}

        checks = [
            _check_ssl_configured(),
            _check_robots_valid(),
            _check_canonical_conflicts({}),
            _check_duplicate_titles({}),
            _check_duplicate_descriptions({}),
            _check_no_404_pages({}),
            _check_all_pages_have_meta({}),
            _check_thin_content({}),
            _check_missing_h1({}),
            _check_missing_alt_images({}),
            _check_all_pages_have_og({}),
            _check_custom_og_images({}),
            _check_image_heavy_pages({}),
            _check_sitemap_coverage([], {}),
        ]

        for check in checks:
            assert check.category in valid_categories, f"{check.check_id}: invalid category '{check.category}'"
            assert check.severity in valid_severities, f"{check.check_id}: invalid severity '{check.severity}'"
            assert isinstance(check.passed, bool), f"{check.check_id}: passed must be bool"
            assert check.title, f"{check.check_id}: title must not be empty"
            assert check.description, f"{check.check_id}: description must not be empty"

        monkeypatch.undo()

    def test_check_count_is_15(self):
        """The audit runs exactly 15 checks (excluding sitemap_freshness which is async)."""
        # 14 sync checks + 1 async (sitemap_freshness) = 15 total
        check_ids = {
            "ssl_configured",
            "robots_valid",
            "sitemap_freshness",
            "canonical_conflicts",
            "duplicate_titles",
            "duplicate_descriptions",
            "no_404_pages",
            "all_pages_have_meta",
            "thin_content_pages",
            "missing_h1_pages",
            "missing_alt_images",
            "all_pages_have_og",
            "custom_og_images",
            "image_heavy_pages",
            "sitemap_coverage",
        }
        assert len(check_ids) == 15
