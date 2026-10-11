"""Output verification pipeline.

Structural checks and configured acceptance criteria are deterministic. They do
not prove semantic truth. Independent review is only reported when a real
reviewer callback runs and returns an explicit decision.
"""
import json
from .accuracy import validate_source_record


def _decode_output(output):
    try:
        value = json.loads(output)
    except (ValueError, TypeError):
        return {}, output
    if not isinstance(value, dict):
        return {}, output
    inner = value.get("content", value)
    if isinstance(inner, str):
        try:
            decoded = json.loads(inner)
            if isinstance(decoded, dict):
                inner = decoded
        except (ValueError, TypeError):
            pass
    return value, inner


def verify_task_output(task: dict, require_evidence: bool = False,
                       success_criteria=None, provenance=None,
                       independent_reviewer=None) -> dict:
    """Verify output shape, provenance, evidence records and explicit criteria.

    Supported criteria:
      - required_phrases: every phrase must occur in output text (case-insensitive)
      - min_output_chars: minimum length of output text
      - required_fields: fields required in a decoded JSON content object
      - require_sources: require at least one structurally valid source record
    """
    output = task.get("output", "")
    criteria = success_criteria if success_criteria is not None else task.get("success_criteria", {})
    if not isinstance(criteria, dict):
        criteria = {}
    result = {"task_id": task.get("id"), "accepted": False, "status": "rejected",
              "checks": [], "evidence_count": 0, "simulated": False,
              "provenance": provenance or "unknown", "independent_review": "not_run",
              "verified_truth": False}
    if not isinstance(output, str) or not output.strip():
        result["checks"].append({"name": "non_empty_output", "passed": False})
        return result
    result["checks"].append({"name": "non_empty_output", "passed": True})
    envelope, inner = _decode_output(output)
    simulated = envelope.get("simulated", False)
    result["simulated"] = simulated is True
    reported_provenance = provenance or (
        "simulated" if simulated is True else
        "executor_reported_live" if simulated is False and "simulated" in envelope else "unknown"
    )
    result["provenance"] = reported_provenance
    content_text = inner if isinstance(inner, str) else json.dumps(inner, ensure_ascii=False)
    sources = inner.get("accepted_evidence", inner.get("sources", [])) if isinstance(inner, dict) else []
    if not isinstance(sources, list):
        sources = []
    valid = [source for source in sources
             if isinstance(source, dict) and validate_source_record(source)[0]]
    result["evidence_count"] = len(valid)
    need_sources = require_evidence or bool(criteria.get("require_sources", False))
    source_ok = not need_sources or bool(valid)
    result["checks"].append({"name": "source_structure", "passed": source_ok})
    if need_sources and result["simulated"]:
        result["checks"].append({"name": "non_simulated_evidence", "passed": False})
    if criteria.get("required_phrases") is not None:
        phrases = criteria["required_phrases"]
        if not isinstance(phrases, list) or any(not isinstance(p, str) or not p.strip() for p in phrases):
            result["checks"].append({"name": "required_phrases_config", "passed": False})
        else:
            missing = [p for p in phrases if p.casefold() not in content_text.casefold()]
            result["checks"].append({"name": "required_phrases", "passed": not missing,
                                     "missing": missing})
    if criteria.get("min_output_chars") is not None:
        minimum = criteria["min_output_chars"]
        valid_min = isinstance(minimum, int) and not isinstance(minimum, bool) and 0 <= minimum <= 20000
        result["checks"].append({"name": "min_output_chars",
                                 "passed": valid_min and len(content_text.strip()) >= minimum,
                                 "configured_minimum": minimum})
    if criteria.get("required_fields") is not None:
        fields = criteria["required_fields"]
        field_ok = isinstance(fields, list) and all(isinstance(field, str) for field in fields)
        missing = [field for field in fields if field not in inner] if field_ok and isinstance(inner, dict) else list(fields) if field_ok else []
        result["checks"].append({"name": "required_fields", "passed": field_ok and not missing,
                                 "missing": missing})
    if criteria.get("expected_provenance") is not None:
        expected = criteria["expected_provenance"]
        result["checks"].append({"name": "expected_provenance",
                                 "passed": isinstance(expected, list) and reported_provenance in expected,
                                 "expected": expected})
    result["accepted"] = all(item["passed"] for item in result["checks"])
    if independent_reviewer is not None:
        try:
            review = independent_reviewer(task, {
                "output": output, "criteria": criteria,
                "provenance": reported_provenance, "evidence_count": len(valid),
            })
            if isinstance(review, dict) and review.get("decision") in {"accept", "reject", "revise"}:
                result["independent_review"] = review["decision"]
                result["review_rationale"] = str(review.get("rationale", ""))[:1000]
                result["accepted"] = result["accepted"] and review["decision"] == "accept"
                result["checks"].append({"name": "independent_review",
                                         "passed": review["decision"] == "accept"})
            else:
                result["independent_review"] = "invalid_response"
                result["accepted"] = False
                result["checks"].append({"name": "independent_review", "passed": False})
        except Exception as exc:
            result["independent_review"] = "error"
            result["review_error"] = type(exc).__name__
            result["accepted"] = False
            result["checks"].append({"name": "independent_review", "passed": False})
    result["status"] = "accepted_for_next_stage" if result["accepted"] else "rejected"
    result["verification_note"] = "Structural checks and reviewer decisions do not independently prove source truth unless the review process itself is trustworthy."
    return result
