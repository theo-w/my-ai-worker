"""Trust labels and verification policy for mixed LLM/rule/tool workflows.

This module does not claim to prove truth. It records provenance and prevents
unverified model text from silently becoming accepted factual evidence.
"""
from __future__ import annotations

from urllib.parse import urlparse

TRUST_LEVELS = {"simulated", "model_generated_unverified", "tool_output_unverified", "source_backed_unverified", "quality_gated_source"}

def classify_output(mode: str, *, simulated: bool = False, source_backed: bool = False, quality_accepted: bool = False) -> dict:
    if simulated or mode == "simulation":
        level = "simulated"
    elif quality_accepted and source_backed:
        level = "quality_gated_source"
    elif source_backed:
        level = "source_backed_unverified"
    elif mode in {"llm", "model"}:
        level = "model_generated_unverified"
    else:
        level = "tool_output_unverified"
    return {
        "trust_level": level,
        "verified_truth": False,
        "usable_as_factual_evidence": level == "quality_gated_source",
        "verification_note": {
            "simulated": "Demo-only output; not evidence.",
            "model_generated_unverified": "Model-generated content; verify material claims independently.",
            "tool_output_unverified": "Tool output is traceable but may be stale, incomplete, or erroneous.",
            "source_backed_unverified": "A source is attached, but the claim has not passed the evidence gate.",
            "quality_gated_source": "Passed mechanical evidence checks; this does not prove the source or claim is true.",
        }[level],
    }

def validate_source_record(source: dict) -> tuple[bool, list[str]]:
    """Conservative structural checks only; never equate URL validity with truth."""
    reasons = []
    url = str(source.get("url", "")).strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        reasons.append("source URL must be an absolute HTTPS URL")
    if not str(source.get("title", "")).strip():
        reasons.append("source title is missing")
    if not str(source.get("snippet", source.get("description", ""))).strip():
        reasons.append("source excerpt is missing")
    return not reasons, reasons

def decision_gate(*, required_evidence: int, accepted_evidence: int, all_evidence_simulated: bool, policy_checks_passed: bool) -> dict:
    """Fail-closed deterministic gate for evidence-dependent decisions."""
    if not policy_checks_passed:
        return {"allowed": False, "status": "blocked_policy", "reason": "A deterministic policy check failed."}
    if all_evidence_simulated:
        return {"allowed": False, "status": "demo_only", "reason": "Simulated evidence cannot authorize a real-world decision."}
    if accepted_evidence < required_evidence:
        return {"allowed": False, "status": "hold_for_evidence", "reason": "Insufficient evidence passed the configured quality gate."}
    return {"allowed": True, "status": "evidence_threshold_met", "reason": "Configured evidence threshold met; human review may still be required."}
