"""Tests for analyze_sentiment.py — keyword-based sentiment scoring."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "competitor-monitoring", "scripts"))

from analyze_sentiment import score_text


class TestScoreText:
    def test_positive_text(self):
        text = "Company reports record growth and successful launch of innovative product"
        result = score_text(text)
        assert result["positive_count"] > 0
        assert result["score"] > 0

    def test_negative_text(self):
        text = "Company faces lawsuit after major data breach and outage"
        result = score_text(text)
        assert result["negative_count"] > 0
        assert result["score"] < 0

    def test_neutral_text(self):
        text = "The company released a statement about their quarterly report"
        result = score_text(text)
        assert result["score"] == 0.0

    def test_opportunity_signals(self):
        text = "Company announces layoffs amid struggling sales and customer exodus"
        result = score_text(text)
        assert len(result["opportunity_signals"]) > 0
        assert "layoffs" in result["opportunity_signals"]

    def test_mixed_sentiment(self):
        text = "Despite lawsuit controversy the company achieved growth milestone"
        result = score_text(text)
        assert result["positive_count"] > 0
        assert result["negative_count"] > 0

    def test_empty_text(self):
        result = score_text("")
        assert result["score"] == 0.0
        assert result["positive_count"] == 0
        assert result["negative_count"] == 0

    def test_score_range(self):
        # Score should always be between -1 and 1
        for text in [
            "growth success innovation",
            "failure breach scandal",
            "normal regular text",
        ]:
            result = score_text(text)
            assert -1.0 <= result["score"] <= 1.0

    def test_positive_words_returned(self):
        text = "The company's innovative growth and successful launch"
        result = score_text(text)
        assert "innovative" in result["positive_words"] or "growth" in result["positive_words"]

    def test_negative_words_returned(self):
        text = "Major outage caused by critical vulnerability"
        result = score_text(text)
        assert "outage" in result["negative_words"] or "vulnerability" in result["negative_words"]
