"""Independent structural checks for worker outputs; does not prove semantic truth."""
import json
from .accuracy import validate_source_record


def verify_task_output(task: dict, require_evidence: bool = False) -> dict:
    output = task.get("output", "")
    result = {"task_id": task.get("id"), "accepted": False, "status": "rejected",
              "checks": [], "evidence_count": 0, "simulated": False,
              "verified_truth": False}
    if not isinstance(output, str) or not output.strip():
        result["checks"].append({"name": "non_empty_output", "passed": False})
        return result
    result["checks"].append({"name": "non_empty_output", "passed": True})
    try:
        envelope = json.loads(output)
        if not isinstance(envelope, dict):
            envelope = {}
    except (ValueError, TypeError):
        envelope = {}
    result["simulated"] = bool(envelope.get("simulated", False))
    inner = envelope.get("content", envelope)
    if isinstance(inner, str):
        try:
            inner = json.loads(inner)
        except (ValueError, TypeError):
            inner = {}
    if not isinstance(inner, dict):
        inner = {}
    sources = inner.get("accepted_evidence", inner.get("sources", []))
    if not isinstance(sources, list):
        sources = []
    valid = []
    for source in sources:
        if isinstance(source, dict) and validate_source_record(source)[0]:
            valid.append(source)
    result["evidence_count"] = len(valid)
    source_check = not require_evidence or bool(valid)
    result["checks"].append({"name": "source_structure", "passed": source_check})
    if require_evidence and result["simulated"]:
        result["checks"].append({"name": "non_simulated_evidence", "passed": False})
    result["accepted"] = all(item["passed"] for item in result["checks"])
    result["status"] = "accepted_for_next_stage" if result["accepted"] else "rejected"
    result["verification_note"] = "Structural checks do not prove source truth or semantic support."
    return result
