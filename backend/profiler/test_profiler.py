import pytest

import profiler.sources as profile_sources

from profiler.comments import select_comments
from profiler.gemini import validate_identification, validate_profile
from profiler.prompt import MEASURES
from profiler.resolver import resolve_protagonist_name
from profiler.sources.webnovel import parse_webnovel_reviews, validate_webnovel_url
from profiler.sources.royalroad import parse_royalroad_reviews, validate_royalroad_url
from profiler.sources.wattpad import (
    extract_part_urls,
    parse_wattpad_comments,
    validate_wattpad_url,
)


def test_select_comments_deduplicates_and_prioritizes_relevant_text():
    comments = [
        "A generic comment that is long enough.",
        "Fang Yuan is calculated rather than reckless or impulsive.",
        "fang yuan is calculated rather than reckless or impulsive.",
    ]
    selected = select_comments(comments, "Fang Yuan", limit=2)
    assert selected[0].startswith("Fang Yuan")
    assert len(selected) == 2


def test_validate_profile_accepts_exact_six_scores():
    profile = validate_profile({
        "scores": {measure: 10 for measure in MEASURES},
        "confidence": 75,
        "evidence_summary": "The available evidence is consistent.",
    })
    assert profile["scores"]["impulsivity"] == 10


def test_validate_profile_rejects_out_of_range_score():
    scores = {measure: 10 for measure in MEASURES}
    scores["impulsivity"] = 101
    with pytest.raises(ValueError):
        validate_profile({
            "scores": scores,
            "confidence": 75,
            "evidence_summary": "Invalid score.",
        })


def test_parse_webnovel_reviews_deduplicates_review_nodes():
    html = """
    <p class="m-comment-bd j_book_review_content">Fang Yuan is calculated and patient.</p>
    <p class="m-comment-bd j_book_review_content">Fang Yuan is calculated and patient.</p>
    <p class="m-comment-bd j_book_review_content">He disregards friendship and romance.</p>
    """
    assert parse_webnovel_reviews(html) == [
        "Fang Yuan is calculated and patient.",
        "He disregards friendship and romance.",
    ]


def test_webnovel_collector_rejects_other_hosts():
    with pytest.raises(ValueError):
        validate_webnovel_url("https://example.com/book/1")


def test_resolve_protagonist_uses_existing_profile():
    novel = {"protagonist_profiles": [{"protagonist_name": "Fang Yuan"}]}
    assert resolve_protagonist_name(novel, None) == "Fang Yuan"


def test_resolve_protagonist_returns_none_when_unknown():
    assert resolve_protagonist_name({"protagonist_profiles": []}, None) is None


def test_validate_protagonist_identification():
    result = validate_identification({
        "protagonist_name": "Zorian Kazinski",
        "confidence": 96,
        "evidence_summary": "The synopsis identifies him as the viewpoint character.",
    })
    assert result["protagonist_name"] == "Zorian Kazinski"


def test_validate_protagonist_identification_rejects_unknown():
    with pytest.raises(ValueError):
        validate_identification({
            "protagonist_name": "unknown",
            "confidence": 10,
            "evidence_summary": "Insufficient evidence.",
        })


def test_parse_royalroad_reviews():
    html = """
    <div class="review-inner"><h4>Title</h4><p>Zorian begins irritable but grows.</p></div>
    <div class="review-inner"><p>He develops meaningful friendships over time.</p></div>
    """
    assert parse_royalroad_reviews(html) == [
        "Zorian begins irritable but grows.",
        "He develops meaningful friendships over time.",
    ]


def test_royalroad_collector_rejects_other_hosts():
    with pytest.raises(ValueError):
        validate_royalroad_url("https://example.com/fiction/1")


def test_extract_wattpad_part_urls_and_comments():
    story_html = """
    <a href="/123456789-first-part">Start reading</a>
    <a href="https://www.wattpad.com/987654321-second-part?x=1">Next</a>
    """
    assert extract_part_urls(story_html, "https://www.wattpad.com/story/10-title") == [
        "https://www.wattpad.com/123456789-first-part",
        "https://www.wattpad.com/987654321-second-part",
    ]
    comments_html = """
    <div data-testid="comment-body">She is fiercely loyal to her friend.</div>
    <div data-testid="comment-body">She is fiercely loyal to her friend.</div>
    """
    assert parse_wattpad_comments(comments_html) == [
        "She is fiercely loyal to her friend."
    ]


def test_wattpad_collector_rejects_other_hosts():
    with pytest.raises(ValueError):
        validate_wattpad_url("https://example.com/story/1")


def test_wattpad_missing_comments_falls_back_without_crashing(monkeypatch, capsys):
    def no_comments(_url):
        raise RuntimeError("Wattpad did not expose public inline comments")

    monkeypatch.setattr(profile_sources, "collect_wattpad_comments", no_comments)
    comments, sources = profile_sources.collect_public_comments([
        {
            "platform": "Wattpad",
            "url": "https://www.wattpad.com/story/10-example",
        }
    ])

    assert comments == []
    assert sources == ["Wattpad (comments unavailable; synopsis/tags only)"]
    assert "Continuing without Wattpad comments" in capsys.readouterr().out
