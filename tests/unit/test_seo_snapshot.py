"""Unit tests for the SEO snapshot service diff computation."""

import json

from modules.seo.services.snapshot_service import _compute_diff


def test_no_diff_when_identical():
    """Identical snapshots should produce no diff."""
    snap = {
        "title": "Test",
        "description": "Desc",
        "robots": "index, follow",
        "canonical_url": "https://example.com",
        "og_tags": {"og:title": "Test"},
        "twitter_tags": {"twitter:card": "summary"},
        "structured_data": [{"@type": "Organization"}],
        "score": 85,
        "is_custom": False,
    }
    assert _compute_diff(snap, snap) is None


def test_diff_on_title_change():
    prev = {"title": "Old Title", "description": "Same", "robots": "index, follow",
            "canonical_url": None, "og_tags": None, "twitter_tags": None,
            "structured_data": None, "score": 50, "is_custom": False}
    current = {**prev, "title": "New Title"}
    diff = _compute_diff(prev, current)
    assert diff is not None
    assert "title" in diff
    assert diff["title"]["old"] == "Old Title"
    assert diff["title"]["new"] == "New Title"


def test_diff_on_score_change():
    prev = {"title": "T", "description": "D", "robots": "index, follow",
            "canonical_url": None, "og_tags": None, "twitter_tags": None,
            "structured_data": None, "score": 50, "is_custom": False}
    current = {**prev, "score": 75}
    diff = _compute_diff(prev, current)
    assert diff is not None
    assert "score" in diff
    assert diff["score"]["old"] == 50
    assert diff["score"]["new"] == 75


def test_diff_on_og_tags_change():
    prev = {"title": "T", "description": "D", "robots": "index, follow",
            "canonical_url": None, "og_tags": {"og:title": "Old"},
            "twitter_tags": None, "structured_data": None,
            "score": None, "is_custom": False}
    current = {**prev, "og_tags": {"og:title": "New"}}
    diff = _compute_diff(prev, current)
    assert diff is not None
    assert "og_tags" in diff


def test_diff_multiple_fields():
    prev = {"title": "A", "description": "B", "robots": "index, follow",
            "canonical_url": None, "og_tags": None, "twitter_tags": None,
            "structured_data": None, "score": 40, "is_custom": False}
    current = {**prev, "title": "C", "description": "D", "score": 80}
    diff = _compute_diff(prev, current)
    assert diff is not None
    assert "title" in diff
    assert "description" in diff
    assert "score" in diff
    assert "robots" not in diff  # unchanged


def test_diff_none_to_value():
    prev = {"title": None, "description": None, "robots": "index, follow",
            "canonical_url": None, "og_tags": None, "twitter_tags": None,
            "structured_data": None, "score": None, "is_custom": False}
    current = {**prev, "title": "New Title", "score": 60}
    diff = _compute_diff(prev, current)
    assert diff is not None
    assert diff["title"]["old"] is None
    assert diff["title"]["new"] == "New Title"


def test_diff_structured_data_change():
    prev = {"title": "T", "description": "D", "robots": "index, follow",
            "canonical_url": None, "og_tags": None, "twitter_tags": None,
            "structured_data": [{"@type": "Organization"}],
            "score": None, "is_custom": False}
    current = {**prev, "structured_data": [
        {"@type": "Organization"}, {"@type": "Product"}
    ]}
    diff = _compute_diff(prev, current)
    assert diff is not None
    assert "structured_data" in diff
