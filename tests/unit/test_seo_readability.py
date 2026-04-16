"""Unit tests for the SEO readability service and keyword density analysis."""

import pytest

from modules.seo.services.readability_service import (
    ReadabilityResult,
    analyze_content,
    count_syllables,
)
from modules.seo.services.keyword_service import analyze_keyword_density


# ---------------------------------------------------------------------------
# Syllable counting
# ---------------------------------------------------------------------------


class TestCountSyllables:
    def test_one_syllable_words(self):
        assert count_syllables("cat") == 1
        assert count_syllables("dog") == 1
        assert count_syllables("the") == 1
        assert count_syllables("run") == 1

    def test_two_syllable_words(self):
        assert count_syllables("hello") == 2
        assert count_syllables("water") == 2
        assert count_syllables("happy") == 2

    def test_three_syllable_words(self):
        assert count_syllables("beautiful") == 3
        assert count_syllables("already") == 3

    def test_empty_string(self):
        assert count_syllables("") == 0

    def test_short_words(self):
        assert count_syllables("a") == 1
        assert count_syllables("an") == 1
        assert count_syllables("the") == 1

    def test_silent_e(self):
        assert count_syllables("take") == 1
        assert count_syllables("make") == 1
        assert count_syllables("like") == 1

    def test_minimum_one(self):
        """Every non-empty word has at least 1 syllable."""
        assert count_syllables("gym") == 1
        assert count_syllables("myth") == 1


# ---------------------------------------------------------------------------
# Readability analysis
# ---------------------------------------------------------------------------


class TestAnalyzeContent:
    def test_empty_content(self):
        result = analyze_content("")
        assert result.word_count == 0
        assert result.sentence_count == 0
        assert result.flesch_reading_ease == 0
        assert result.quality == "very difficult"

    def test_simple_sentence(self):
        result = analyze_content("The cat sat on the mat.")
        assert result.word_count == 6
        assert result.sentence_count == 1
        assert result.avg_sentence_length == 6.0
        assert result.flesch_reading_ease > 80  # Simple text = easy
        assert result.quality in ("very easy", "easy")

    def test_multiple_sentences(self):
        text = "This is sentence one. This is sentence two. And this is three."
        result = analyze_content(text)
        assert result.sentence_count == 3
        assert result.word_count > 10

    def test_complex_text_scores_lower(self):
        simple = "The dog ran fast. The cat sat down."
        complex_text = (
            "The epistemological implications of postmodernist deconstructionism "
            "fundamentally challenge conventional hermeneutical methodologies "
            "throughout contemporary philosophical discourse."
        )
        simple_result = analyze_content(simple)
        complex_result = analyze_content(complex_text)
        assert simple_result.flesch_reading_ease > complex_result.flesch_reading_ease

    def test_quality_labels(self):
        # Very easy text: short words, short sentences
        very_easy = "I am a cat. I like to nap. I sit on a mat."
        result = analyze_content(very_easy)
        assert result.quality in ("very easy", "easy")

    def test_result_is_dataclass(self):
        result = analyze_content("Hello world.")
        assert isinstance(result, ReadabilityResult)
        assert isinstance(result.word_count, int)
        assert isinstance(result.flesch_reading_ease, float)

    def test_score_bounded_0_100(self):
        # Very complex text shouldn't go below 0
        hard = "Antidisestablishmentarianism. " * 10
        result = analyze_content(hard)
        assert 0 <= result.flesch_reading_ease <= 100

        # Very simple text shouldn't go above 100
        easy = "I am. " * 50
        result2 = analyze_content(easy)
        assert 0 <= result2.flesch_reading_ease <= 100

    def test_avg_syllables_per_word(self):
        result = analyze_content("The cat sat on the mat.")
        assert result.avg_syllables_per_word >= 1.0
        assert result.avg_syllables_per_word < 3.0

    def test_single_word(self):
        result = analyze_content("Hello")
        assert result.word_count == 1
        assert result.sentence_count >= 1


# ---------------------------------------------------------------------------
# Keyword density analysis
# ---------------------------------------------------------------------------


class TestAnalyzeKeywordDensity:
    def test_empty_content(self):
        result = analyze_keyword_density("", ["test"])
        assert result == []

    def test_empty_keywords(self):
        result = analyze_keyword_density("some content here", [])
        assert result == []

    def test_keyword_present(self):
        content = "SEO tools are great. The best SEO tools help you rank."
        result = analyze_keyword_density(content, ["seo tools"])
        assert len(result) == 1
        assert result[0]["keyword"] == "seo tools"
        assert result[0]["count"] == 2
        assert result[0]["density"] > 0

    def test_keyword_absent(self):
        content = "This is a normal paragraph about cooking recipes and ingredients."
        result = analyze_keyword_density(content, ["blockchain"])
        assert result[0]["count"] == 0
        assert result[0]["status"] == "absent"

    def test_good_density(self):
        # Create content with ~1% density
        words = ["word"] * 100
        words[10] = "target"
        words[50] = "target"
        content = " ".join(words)
        result = analyze_keyword_density(content, ["target"])
        assert result[0]["status"] == "good"

    def test_stuffing_detected(self):
        # ~5% density = stuffing
        words = ["word"] * 20
        for i in range(0, 20, 4):
            words[i] = "keyword"
        content = " ".join(words)
        result = analyze_keyword_density(content, ["keyword"])
        assert result[0]["status"] in ("high", "stuffing")

    def test_multiple_keywords(self):
        content = "SEO and marketing are important for digital marketing success."
        result = analyze_keyword_density(content, ["seo", "marketing"])
        assert len(result) == 2
        assert result[0]["keyword"] == "seo"
        assert result[1]["keyword"] == "marketing"
        assert result[1]["count"] == 2  # "marketing" appears twice

    def test_case_insensitive(self):
        content = "SEO Tools are the best Seo tools for optimization."
        result = analyze_keyword_density(content, ["seo tools"])
        assert result[0]["count"] == 2

    def test_multi_word_keyword(self):
        content = "Energy conference Calgary is the best energy conference in Calgary this year."
        result = analyze_keyword_density(content, ["energy conference calgary"])
        assert result[0]["count"] == 1

    def test_density_percentage(self):
        # 10 words, keyword appears once (1 word), density should be ~10%
        content = "the quick brown fox jumped over the lazy keyword dog"
        result = analyze_keyword_density(content, ["keyword"])
        assert result[0]["density"] == pytest.approx(10.0, abs=1.0)
