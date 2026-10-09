"""Audit citations in generated research synthesis without claiming semantic truth."""
from __future__ import annotations
import re

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？])|(?<=[.!?])\s+|\n+")
_CITATION = re.compile(r"\[(S\d+)\]")

def audit_synthesis(text: str, sources: list[dict]) -> dict:
    """Check citation IDs and sentence-level citation coverage.

    This is a structural audit only: a valid citation may still fail to support
    the sentence semantically, so every cited claim remains review-required.
    """
    source_ids = {str(item.get("source_id", "")) for item in sources if item.get("source_id")}
    sentences = [part.strip() for part in _SENTENCE_SPLIT.split(str(text or "")) if part.strip()]
    audited = []
    for sentence in sentences:
        cited_ids = _CITATION.findall(sentence)
        unknown_ids = sorted(set(cited_ids) - source_ids)
        valid_ids = sorted(set(cited_ids) & source_ids)
        if unknown_ids:
            status = "invalid_citation_id"
        elif not cited_ids:
            status = "missing_citation"
        else:
            status = "citation_present_semantic_review_required"
        audited.append({
            "sentence": sentence,
            "citation_ids": valid_ids,
            "unknown_citation_ids": unknown_ids,
            "status": status,
            "semantic_support_verified": False,
        })
    counts = {key: sum(1 for row in audited if row["status"] == key) for key in (
        "invalid_citation_id", "missing_citation", "citation_present_semantic_review_required"
    )}
    return {
        "status": "review_required" if any(row["status"] != "citation_present_semantic_review_required" for row in audited) else "citations_structurally_valid_review_required",
        "total_sentences": len(audited),
        "counts": counts,
        "all_claims_semantically_verified": False,
        "sentences": audited,
    }