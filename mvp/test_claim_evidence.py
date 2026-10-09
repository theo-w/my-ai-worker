"""Tests for structural citation audits; semantic support remains unverified."""
from mvp.claim_evidence import audit_synthesis

def test_audit_accepts_known_citation_ids_but_requires_semantic_review():
    result = audit_synthesis("Revenue increased [S1].", [{"source_id": "S1", "url": "https://example.com"}])
    assert result["status"] == "citations_structurally_valid_review_required"
    assert result["all_claims_semantically_verified"] is False
    assert result["sentences"][0]["status"] == "citation_present_semantic_review_required"

def test_audit_flags_missing_and_unknown_citations():
    result = audit_synthesis("A claim without a source. Another claim [S99].", [{"source_id": "S1"}])
    assert result["counts"]["missing_citation"] == 1
    assert result["counts"]["invalid_citation_id"] == 1
    assert result["status"] == "review_required"

def test_audit_handles_empty_synthesis():
    result = audit_synthesis("", [{"source_id": "S1"}])
    assert result["total_sentences"] == 0
    assert result["all_claims_semantically_verified"] is False