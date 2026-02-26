"""Tests for detect_partnerships.py — partnership signal detection."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "competitor-monitoring", "scripts"))

from detect_partnerships import (
    PARTNERSHIP_PATTERN,
    classify_partnership_type,
    compute_confidence,
    extract_potential_entity_names,
)
from models import PartnershipType


class TestPartnershipPattern:
    def test_matches_partnership(self):
        assert PARTNERSHIP_PATTERN.search("new partnership with BigCo")

    def test_matches_integration(self):
        assert PARTNERSHIP_PATTERN.search("Acme integrated with Stripe")

    def test_matches_powered_by(self):
        assert PARTNERSHIP_PATTERN.search("Powered by CloudTech")

    def test_matches_acquisition(self):
        assert PARTNERSHIP_PATTERN.search("Company acquired by BigCo")

    def test_matches_works_with(self):
        assert PARTNERSHIP_PATTERN.search("Works with Salesforce")

    def test_no_match_on_irrelevant(self):
        assert not PARTNERSHIP_PATTERN.search("We had a great quarterly earnings call")


class TestExtractEntityNames:
    def test_extracts_company_near_partnership(self):
        text = "We are excited about our partnership with BigCo Inc for enterprise solutions."
        candidates = extract_potential_entity_names(text)
        names = [c["name"] for c in candidates]
        assert any("BigCo" in n for n in names)

    def test_extracts_company_near_integration(self):
        text = "Acme Corp has integrated with Stripe to enable seamless payments."
        candidates = extract_potential_entity_names(text)
        names = [c["name"] for c in candidates]
        assert any("Stripe" in n for n in names)

    def test_ignores_common_words(self):
        text = "The partnership was announced today."
        candidates = extract_potential_entity_names(text)
        names = [c["name"].lower() for c in candidates]
        assert "the" not in names

    def test_empty_text(self):
        candidates = extract_potential_entity_names("")
        assert candidates == []

    def test_no_signals_returns_empty(self):
        text = "This is a normal sentence about nothing special."
        candidates = extract_potential_entity_names(text)
        assert candidates == []


class TestClassifyPartnershipType:
    def test_acquisition_context(self):
        result = classify_partnership_type("Company was acquired by BigCo for $1B")
        assert result == PartnershipType.ACQUISITION

    def test_investment_context(self):
        result = classify_partnership_type("raised $50M in Series B funding")
        assert result == PartnershipType.INVESTMENT

    def test_strategic_context(self):
        result = classify_partnership_type("entered a strategic alliance with Microsoft")
        assert result == PartnershipType.STRATEGIC

    def test_reseller_context(self):
        result = classify_partnership_type("new reseller agreement with distributor")
        assert result == PartnershipType.RESELLER

    def test_integration_context(self):
        result = classify_partnership_type("launched an integration with Slack")
        assert result == PartnershipType.INTEGRATION

    def test_default_is_integration(self):
        result = classify_partnership_type("some vague partnership text")
        assert result == PartnershipType.INTEGRATION


class TestComputeConfidence:
    def test_base_confidence(self):
        score = compute_confidence(0, False, 0)
        assert score == 0.3

    def test_more_signals_increases_confidence(self):
        low = compute_confidence(1, False, 1)
        high = compute_confidence(3, False, 1)
        assert high > low

    def test_structured_data_boosts_confidence(self):
        without = compute_confidence(1, False, 1)
        with_struct = compute_confidence(1, True, 1)
        assert with_struct > without

    def test_high_frequency_boosts_confidence(self):
        low_freq = compute_confidence(1, False, 1)
        high_freq = compute_confidence(1, False, 5)
        assert high_freq > low_freq

    def test_max_confidence_capped(self):
        score = compute_confidence(10, True, 10)
        assert score <= 0.99
