"""Content readability analysis service.

Pure Python implementation of Flesch-Kincaid Reading Ease scoring.
No external dependencies required.
"""

import re
from dataclasses import dataclass


@dataclass
class ReadabilityResult:
    """Result of a readability analysis."""

    word_count: int
    sentence_count: int
    avg_sentence_length: float
    syllable_count: int
    avg_syllables_per_word: float
    flesch_reading_ease: float  # 0-100, higher = easier
    quality: str  # "very easy", "easy", "moderate", "difficult", "very difficult"


# Common English suffixes that don't add syllables
_SILENT_E = re.compile(r"[^aeiou]e$", re.IGNORECASE)
_ES_SUFFIX = re.compile(r"(es|ed)$", re.IGNORECASE)
_VOWEL_GROUP = re.compile(r"[aeiouy]+", re.IGNORECASE)


def count_syllables(word: str) -> int:
    """Estimate syllable count for an English word.

    Uses vowel-group counting with adjustments for common English patterns.
    """
    word = word.lower().strip()
    if not word:
        return 0
    if len(word) <= 3:
        return 1

    # Count vowel groups
    vowel_groups = _VOWEL_GROUP.findall(word)
    count = len(vowel_groups)

    # Adjust for silent 'e' at end
    if _SILENT_E.search(word):
        count -= 1

    # Adjust for -es, -ed endings that don't add a syllable
    if _ES_SUFFIX.search(word) and count > 1:
        # "liked" is 1 syllable, "created" is 3
        # Only subtract if the ending isn't its own vowel group
        if not re.search(r"[aeiouy]ed$", word):
            count -= 1

    return max(count, 1)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # Split on sentence-ending punctuation followed by space or end
    sentences = re.split(r"[.!?]+(?:\s|$)", text)
    return [s.strip() for s in sentences if s.strip()]


def _split_words(text: str) -> list[str]:
    """Split text into words (alphanumeric tokens)."""
    return re.findall(r"[a-zA-Z]+", text)


def analyze_content(text: str) -> ReadabilityResult:
    """Analyze the readability of text content.

    Returns word/sentence/syllable counts and Flesch-Kincaid Reading Ease score.

    Flesch Reading Ease scale:
        90-100: Very easy (5th grade)
        80-89:  Easy (6th grade)
        70-79:  Fairly easy (7th grade)
        60-69:  Moderate (8th-9th grade)
        50-59:  Fairly difficult (10th-12th grade)
        30-49:  Difficult (college level)
        0-29:   Very difficult (graduate level)
    """
    words = _split_words(text)
    sentences = _split_sentences(text)

    word_count = len(words)
    sentence_count = max(len(sentences), 1)

    if word_count == 0:
        return ReadabilityResult(
            word_count=0,
            sentence_count=0,
            avg_sentence_length=0,
            syllable_count=0,
            avg_syllables_per_word=0,
            flesch_reading_ease=0,
            quality="very difficult",
        )

    total_syllables = sum(count_syllables(w) for w in words)
    avg_sentence_length = word_count / sentence_count
    avg_syllables_per_word = total_syllables / word_count

    # Flesch Reading Ease formula
    score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
    score = max(0, min(100, score))

    # Quality label
    if score >= 90:
        quality = "very easy"
    elif score >= 80:
        quality = "easy"
    elif score >= 60:
        quality = "moderate"
    elif score >= 30:
        quality = "difficult"
    else:
        quality = "very difficult"

    return ReadabilityResult(
        word_count=word_count,
        sentence_count=sentence_count,
        avg_sentence_length=round(avg_sentence_length, 1),
        syllable_count=total_syllables,
        avg_syllables_per_word=round(avg_syllables_per_word, 2),
        flesch_reading_ease=round(score, 1),
        quality=quality,
    )
