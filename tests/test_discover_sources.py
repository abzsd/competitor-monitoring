"""Tests for discover_sources.py — URL classification and filtering."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "competitor-monitoring", "scripts"))

from discover_sources import classify_url, extract_sitemap_urls, is_relevant_url
from models import PageType


class TestClassifyUrl:
    def test_pricing_url(self):
        assert classify_url("https://acme.com/pricing") == PageType.PRICING

    def test_plans_url(self):
        assert classify_url("https://acme.com/plans") == PageType.PRICING

    def test_product_url(self):
        assert classify_url("https://acme.com/product") == PageType.PRODUCT

    def test_features_url(self):
        assert classify_url("https://acme.com/features") == PageType.PRODUCT

    def test_partners_url(self):
        assert classify_url("https://acme.com/partners") == PageType.PARTNERSHIPS

    def test_integrations_url(self):
        assert classify_url("https://acme.com/integrations") == PageType.PARTNERSHIPS

    def test_blog_url(self):
        assert classify_url("https://acme.com/blog") == PageType.BLOG

    def test_changelog_url(self):
        assert classify_url("https://acme.com/changelog") == PageType.CHANGELOG

    def test_careers_url(self):
        assert classify_url("https://acme.com/careers") == PageType.CAREERS

    def test_irrelevant_url_returns_none(self):
        assert classify_url("https://acme.com/some-random-page") is None

    def test_nested_pricing_url(self):
        assert classify_url("https://acme.com/en/pricing/details") == PageType.PRICING


class TestIsRelevantUrl:
    def test_same_domain_relevant(self):
        assert is_relevant_url("https://acme.com/pricing", "acme.com")

    def test_different_domain_irrelevant(self):
        assert not is_relevant_url("https://other.com/pricing", "acme.com")

    def test_asset_urls_irrelevant(self):
        assert not is_relevant_url("https://acme.com/assets/logo.png", "acme.com")
        assert not is_relevant_url("https://acme.com/static/main.css", "acme.com")
        assert not is_relevant_url("https://acme.com/js/app.js", "acme.com")

    def test_wp_admin_irrelevant(self):
        assert not is_relevant_url("https://acme.com/wp-admin/edit.php", "acme.com")

    def test_api_urls_irrelevant(self):
        assert not is_relevant_url("https://acme.com/api/v1/users", "acme.com")

    def test_login_irrelevant(self):
        assert not is_relevant_url("https://acme.com/login", "acme.com")

    def test_file_extensions_irrelevant(self):
        assert not is_relevant_url("https://acme.com/sitemap.xml", "acme.com")
        assert not is_relevant_url("https://acme.com/data.json", "acme.com")

    def test_subdomain_relevant(self):
        assert is_relevant_url("https://www.acme.com/pricing", "acme.com")


class TestExtractSitemapUrls:
    def test_extracts_sitemap_urls(self):
        robots = """
User-agent: *
Disallow: /admin/

Sitemap: https://acme.com/sitemap.xml
Sitemap: https://acme.com/sitemap-blog.xml
"""
        urls = extract_sitemap_urls(robots)
        assert len(urls) == 2
        assert "https://acme.com/sitemap.xml" in urls
        assert "https://acme.com/sitemap-blog.xml" in urls

    def test_empty_robots(self):
        assert extract_sitemap_urls("") == []

    def test_no_sitemaps(self):
        robots = "User-agent: *\nDisallow: /admin/"
        assert extract_sitemap_urls(robots) == []

    def test_case_insensitive(self):
        robots = "SITEMAP: https://acme.com/sitemap.xml"
        urls = extract_sitemap_urls(robots)
        assert len(urls) == 1
