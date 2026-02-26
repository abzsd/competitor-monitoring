"""Tests for format_slack.py — Slack Block Kit message formatting."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "competitor-monitoring", "scripts"))

from format_slack import format_analysis_alert, format_change_alert, format_report_summary


class TestFormatChangeAlert:
    def test_produces_blocks(self, sample_change):
        payload = format_change_alert(sample_change)
        assert "blocks" in payload
        assert len(payload["blocks"]) > 0

    def test_header_contains_severity(self, sample_change):
        payload = format_change_alert(sample_change)
        header = payload["blocks"][0]
        assert header["type"] == "header"

    def test_includes_summary(self, sample_change):
        payload = format_change_alert(sample_change)
        blocks_text = str(payload)
        assert sample_change["summary"] in blocks_text or "Pricing" in blocks_text

    def test_includes_structured_diff(self):
        change = {
            "severity": "critical",
            "change_type": "pricing_change",
            "competitor": "Acme",
            "source_url": "https://acme.com/pricing",
            "detected_at": "2025-06-02T00:00:00",
            "summary": "Price raised",
            "text_diff": "+$99/mo\n-$79/mo\n",
            "structured_diff": {
                "changed": [{"path": "price", "old_value": "$79/mo", "new_value": "$99/mo"}],
                "added": [],
                "removed": [],
            },
        }
        payload = format_change_alert(change)
        blocks_text = str(payload)
        assert "$79/mo" in blocks_text
        assert "$99/mo" in blocks_text

    def test_handles_minimal_change(self):
        change = {
            "severity": "low",
            "change_type": "content_update",
            "summary": "Minor update",
        }
        payload = format_change_alert(change)
        assert "blocks" in payload


class TestFormatAnalysisAlert:
    def test_produces_blocks(self, sample_analysis):
        payload = format_analysis_alert(sample_analysis)
        assert "blocks" in payload

    def test_includes_insights(self, sample_analysis):
        payload = format_analysis_alert(sample_analysis)
        blocks_text = str(payload)
        assert "comparison page" in blocks_text or "Recommended" in blocks_text

    def test_includes_summary_text(self, sample_analysis):
        payload = format_analysis_alert(sample_analysis)
        blocks_text = str(payload)
        assert "Pro plan" in blocks_text or "Acme" in blocks_text


class TestFormatReportSummary:
    def test_produces_blocks(self):
        report = {
            "period": "Last 7 days",
            "summary": {
                "total_changes": 5,
                "total_analyses": 3,
                "total_partnerships_discovered": 1,
                "total_alerts_sent": 2,
                "severity_breakdown": {"critical": 0, "high": 2, "medium": 2, "low": 1},
            },
            "competitors": [
                {
                    "competitor_name": "Acme Corp",
                    "total_changes": 3,
                    "critical_changes": 0,
                    "high_changes": 2,
                    "changes": [
                        {"severity": "high", "summary": "Price raised"},
                        {"severity": "medium", "summary": "New feature added"},
                    ],
                }
            ],
            "top_actionable_insights": ["Update pricing page"],
        }
        payload = format_report_summary(report)
        assert "blocks" in payload
        assert len(payload["blocks"]) > 3

    def test_handles_empty_report(self):
        report = {
            "period": "Last 7 days",
            "summary": {
                "total_changes": 0,
                "total_analyses": 0,
                "total_partnerships_discovered": 0,
                "total_alerts_sent": 0,
                "severity_breakdown": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            },
            "competitors": [],
            "top_actionable_insights": [],
        }
        payload = format_report_summary(report)
        assert "blocks" in payload
