"""Tests for scrape.py — content extraction and structured data parsing."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "competitor-monitoring", "scripts"))

from scrape import extract_text, extract_structured_data


class TestExtractText:
    def test_strips_nav_and_footer(self, sample_html_v1):
        text = extract_text(sample_html_v1)
        assert "Navigation here" not in text
        assert "Footer content" not in text

    def test_strips_script_and_style(self):
        html = "<html><body><script>alert('x')</script><style>.a{}</style><p>Hello</p></body></html>"
        text = extract_text(html)
        assert "alert" not in text
        assert ".a{}" not in text
        assert "Hello" in text

    def test_extracts_main_content(self, sample_html_v1):
        text = extract_text(sample_html_v1)
        assert "Pricing Plans" in text
        assert "Starter" in text
        assert "$29/mo" in text
        assert "Pro" in text
        assert "$79/mo" in text

    def test_removes_boilerplate_classes(self):
        html = """
        <html><body>
        <div class="cookie-consent">Accept cookies</div>
        <div class="newsletter-subscribe">Subscribe!</div>
        <p>Real content here</p>
        </body></html>
        """
        text = extract_text(html)
        assert "Accept cookies" not in text
        assert "Subscribe" not in text
        assert "Real content here" in text

    def test_collapses_blank_lines(self):
        html = "<html><body><p>Line 1</p><br><br><br><br><p>Line 2</p></body></html>"
        text = extract_text(html)
        assert "\n\n\n" not in text

    def test_empty_html(self):
        text = extract_text("")
        assert text == ""

    def test_html_comments_removed(self):
        html = "<html><body><!-- secret comment --><p>Visible</p></body></html>"
        text = extract_text(html)
        assert "secret comment" not in text
        assert "Visible" in text


class TestExtractStructuredData:
    def test_pricing_page_extracts_plans(self, sample_html_v1):
        data = extract_structured_data(sample_html_v1, "pricing")
        assert "plans" in data
        assert len(data["plans"]) >= 1
        # Check at least one plan has a name and price
        plan = data["plans"][0]
        assert "name" in plan or "price" in plan

    def test_pricing_page_v2_has_more_plans(self, sample_html_v2):
        data = extract_structured_data(sample_html_v2, "pricing")
        assert "plans" in data
        assert len(data["plans"]) >= 2

    def test_meta_description_extracted(self, sample_html_v1):
        data = extract_structured_data(sample_html_v1, "other")
        assert "meta_description" in data
        assert "Acme" in data["meta_description"]

    def test_page_title_extracted(self, sample_html_v1):
        data = extract_structured_data(sample_html_v1, "other")
        assert "page_title" in data
        assert "Acme Corp Pricing" in data["page_title"]

    def test_partnerships_page_extracts_partners(self, sample_partnership_html):
        data = extract_structured_data(sample_partnership_html, "partnerships")
        assert "partners" in data
        partner_names = data["partners"]
        assert any("BigCo" in p for p in partner_names)

    def test_unknown_page_type_still_gets_meta(self):
        html = '<html><head><title>Test</title></head><body><p>Content</p></body></html>'
        data = extract_structured_data(html, "other")
        assert data.get("page_title") == "Test"

    def test_empty_html_returns_empty(self):
        data = extract_structured_data("", "pricing")
        assert isinstance(data, dict)
