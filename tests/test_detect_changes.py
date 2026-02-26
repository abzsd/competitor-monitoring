"""Tests for detect_changes.py — diffing engine and severity classification."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "competitor-monitoring", "scripts"))

from detect_changes import (
    classify_change_type,
    classify_severity,
    compute_structured_diff,
    compute_text_diff,
    generate_summary,
)
from models import ChangeType, Severity


class TestComputeTextDiff:
    def test_identical_text_produces_empty_diff(self):
        diff = compute_text_diff("Hello world", "Hello world")
        assert diff == ""

    def test_detects_added_lines(self):
        before = "Line 1\nLine 2\n"
        after = "Line 1\nLine 2\nLine 3\n"
        diff = compute_text_diff(before, after)
        assert "+Line 3" in diff

    def test_detects_removed_lines(self):
        before = "Line 1\nLine 2\nLine 3\n"
        after = "Line 1\nLine 3\n"
        diff = compute_text_diff(before, after)
        assert "-Line 2" in diff

    def test_detects_changed_lines(self):
        before = "Price: $79/mo\n"
        after = "Price: $99/mo\n"
        diff = compute_text_diff(before, after)
        assert "-Price: $79/mo" in diff
        assert "+Price: $99/mo" in diff

    def test_empty_before(self):
        diff = compute_text_diff("", "New content\n")
        assert "+New content" in diff

    def test_empty_after(self):
        diff = compute_text_diff("Old content\n", "")
        assert "-Old content" in diff


class TestComputeStructuredDiff:
    def test_no_changes(self):
        data = {"key": "value"}
        diff = compute_structured_diff(data, data)
        assert diff["changed"] == []
        assert diff["added"] == []
        assert diff["removed"] == []

    def test_detects_value_change(self):
        before = {"price": "$79"}
        after = {"price": "$99"}
        diff = compute_structured_diff(before, after)
        assert len(diff["changed"]) == 1
        assert diff["changed"][0]["old_value"] == "$79"
        assert diff["changed"][0]["new_value"] == "$99"

    def test_detects_added_key(self):
        before = {"a": 1}
        after = {"a": 1, "b": 2}
        diff = compute_structured_diff(before, after)
        assert len(diff["added"]) == 1

    def test_detects_removed_key(self):
        before = {"a": 1, "b": 2}
        after = {"a": 1}
        diff = compute_structured_diff(before, after)
        assert len(diff["removed"]) == 1

    def test_empty_inputs(self):
        diff = compute_structured_diff({}, {})
        assert diff == {"changed": [], "added": [], "removed": []}

    def test_nested_change(self):
        before = {"plans": [{"name": "Pro", "price": "$79"}]}
        after = {"plans": [{"name": "Pro", "price": "$99"}]}
        diff = compute_structured_diff(before, after)
        assert len(diff["changed"]) >= 1


class TestClassifyChangeType:
    def test_pricing_page_returns_pricing(self):
        source = {"page_type": "pricing"}
        result = classify_change_type(source, "some diff text")
        assert result == ChangeType.PRICING_CHANGE

    def test_price_keyword_in_diff(self):
        source = {"page_type": "other"}
        result = classify_change_type(source, "The price changed to $99/mo")
        assert result == ChangeType.PRICING_CHANGE

    def test_partnership_page(self):
        source = {"page_type": "partnerships"}
        result = classify_change_type(source, "some diff")
        assert result == ChangeType.PARTNERSHIP_NEW

    def test_partnership_keyword_in_diff(self):
        source = {"page_type": "other"}
        result = classify_change_type(source, "New integration with BigCo")
        assert result == ChangeType.PARTNERSHIP_NEW

    def test_product_page(self):
        source = {"page_type": "product"}
        result = classify_change_type(source, "some diff")
        assert result == ChangeType.PRODUCT_UPDATE

    def test_tech_stack_page(self):
        source = {"page_type": "tech_stack"}
        result = classify_change_type(source, "some diff")
        assert result == ChangeType.TECH_STACK_CHANGE

    def test_generic_content(self):
        source = {"page_type": "blog"}
        result = classify_change_type(source, "Updated blog post about culture")
        assert result == ChangeType.CONTENT_UPDATE


class TestClassifySeverity:
    def test_pricing_with_structured_diff_is_critical(self):
        result = classify_severity(
            ChangeType.PRICING_CHANGE,
            "diff",
            "before",
            "after",
            {"changed": [{"path": "price", "old_value": "$79", "new_value": "$99"}]},
        )
        assert result == Severity.CRITICAL

    def test_pricing_without_structured_diff_is_high(self):
        result = classify_severity(
            ChangeType.PRICING_CHANGE,
            "diff",
            "before",
            "after",
            {"changed": [], "added": [], "removed": []},
        )
        assert result == Severity.HIGH

    def test_partnership_is_high(self):
        result = classify_severity(
            ChangeType.PARTNERSHIP_NEW,
            "diff",
            "before",
            "after",
            {},
        )
        assert result == Severity.HIGH

    def test_major_product_update_is_high(self):
        before = "x" * 100
        after = "y" * 200  # >30% change ratio
        result = classify_severity(
            ChangeType.PRODUCT_UPDATE,
            "diff",
            before,
            after,
            {},
        )
        assert result == Severity.HIGH

    def test_minor_content_update_is_low(self):
        before = "x" * 1000
        after = "x" * 1000 + "y"  # <1% change
        result = classify_severity(
            ChangeType.CONTENT_UPDATE,
            "diff",
            before,
            after,
            {},
        )
        assert result == Severity.LOW


class TestGenerateSummary:
    def test_includes_change_type(self):
        source = {"url": "https://example.com/pricing", "page_type": "pricing"}
        summary = generate_summary(ChangeType.PRICING_CHANGE, "+line1\n-line2\n", source)
        assert "Pricing Change" in summary

    def test_includes_url(self):
        source = {"url": "https://example.com/pricing", "page_type": "pricing"}
        summary = generate_summary(ChangeType.PRICING_CHANGE, "+line1\n-line2\n", source)
        assert "example.com" in summary

    def test_includes_line_counts(self):
        diff = "+added line\n-removed line\n+another add\n"
        source = {"url": "https://example.com", "page_type": "other"}
        summary = generate_summary(ChangeType.CONTENT_UPDATE, diff, source)
        assert "+2" in summary
        assert "-1" in summary
