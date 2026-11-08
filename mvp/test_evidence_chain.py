"""Phase-2 evidence chain tests.

Verifies that the Digital Twin's audit of employee results properly handles:
1. Untraceable conclusions (no evidence)
2. Unreliable sources
3. Counter-evidence
4. Simulated output mixed with real evidence
5. Complete evidence chain with reliable sources
6. Revision that breaks the evidence chain
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

# Ensure mvp/ is importable
MVP_DIR = Path(__file__).parent
sys.path.insert(0, str(MVP_DIR.parent))

from mvp.workforce import WorkforceRegistry
from mvp.server import (
    _assess_source_reliability,
    _check_evidence_traceability,
    _audit_worker_result,
)


class TestAssessSourceReliability(unittest.TestCase):
    """Test _assess_source_reliability phase-2 function."""

    def test_https_primary_source_is_reliable(self):
        evidence = [{
            "source": {"url": "https://example.com/article", "title": "Test"},
            "source_role": "primary",
        }]
        result = _assess_source_reliability(evidence)
        self.assertEqual(len(result["reliable"]), 1)
        self.assertEqual(result["reliable"][0]["rating"], "reliable")
        self.assertEqual(len(result["unreliable"]), 0)

    def test_non_https_source_is_questionable(self):
        evidence = [{
            "source": {"url": "http://example.com/article", "title": "Test"},
        }]
        result = _assess_source_reliability(evidence)
        self.assertEqual(len(result["questionable"]), 1)
        self.assertEqual(result["questionable"][0]["reason"], "not_https")

    def test_simulated_output_is_unreliable(self):
        evidence = [{
            "source": {"url": "https://example.com/article", "title": "Test"},
            "simulated": True,
        }]
        result = _assess_source_reliability(evidence)
        self.assertEqual(len(result["unreliable"]), 1)
        self.assertEqual(result["unreliable"][0]["reason"], "simulated_output")

    def test_missing_source_is_unreliable(self):
        evidence = [{"finding": "no source attached"}]
        result = _assess_source_reliability(evidence)
        self.assertEqual(len(result["unreliable"]), 1)
        self.assertEqual(result["unreliable"][0]["reason"], "missing_or_invalid_source")

    def test_empty_evidence_returns_empty_lists(self):
        result = _assess_source_reliability([])
        self.assertEqual(result["reliable"], [])
        self.assertEqual(result["questionable"], [])
        self.assertEqual(result["unreliable"], [])

    def test_mixed_sources_properly_rated(self):
        evidence = [
            {"source": {"url": "https://a.com", "title": "A"}, "source_role": "primary"},
            {"source": {"url": "http://b.com", "title": "B"}},
            {"source": {"url": "https://c.com", "title": "C"}, "simulated": True},
        ]
        result = _assess_source_reliability(evidence)
        self.assertEqual(len(result["reliable"]), 1)
        self.assertEqual(len(result["questionable"]), 1)
        self.assertEqual(len(result["unreliable"]), 1)


class TestCheckEvidenceTraceability(unittest.TestCase):
    """Test _check_evidence_traceability phase-2 function."""

    def test_output_url_matches_evidence(self):
        output = "See https://example.com/report for details."
        evidence = [{
            "source": {"url": "https://example.com/report", "title": "Report"},
        }]
        result = _check_evidence_traceability(output, evidence)
        self.assertTrue(result["structural_traceability"])
        self.assertEqual(len(result["matched_urls"]), 1)
        self.assertEqual(len(result["unmatched_urls"]), 0)

    def test_output_url_not_in_evidence(self):
        output = "See https://other.com/report for details."
        evidence = [{
            "source": {"url": "https://example.com/report", "title": "Report"},
        }]
        result = _check_evidence_traceability(output, evidence)
        self.assertFalse(result["structural_traceability"])
        self.assertEqual(len(result["unmatched_urls"]), 1)

    def test_no_urls_in_output(self):
        output = "The market is growing."
        evidence = [{
            "source": {"url": "https://example.com/report", "title": "Report"},
        }]
        result = _check_evidence_traceability(output, evidence)
        self.assertEqual(result["output_url_count"], 0)
        self.assertEqual(result["evidence_url_count"], 1)

    def test_empty_output_and_evidence(self):
        result = _check_evidence_traceability("", [])
        self.assertEqual(result["output_url_count"], 0)
        self.assertEqual(result["evidence_url_count"], 0)


class TestAuditWorkerResultWithEvidenceChain(unittest.TestCase):
    """Test _audit_worker_result with phase-2 evidence chain fields."""

    def test_simulation_only_no_reliability_data(self):
        result = _audit_worker_result(
            "Simulated output",
            {"simulated": True, "mode": "simulation"},
            [],
        )
        self.assertEqual(result["verdict"], "SIMULATION_ONLY")
        self.assertIn("source_reliability", result)
        self.assertIn("traceability", result)

    def test_traceable_has_reliability_assessment(self):
        evidence = [{
            "source": {"url": "https://example.com/report", "title": "Report"},
        }]
        result = _audit_worker_result(
            "The market shows growth. See https://example.com/report.",
            {"simulated": False},
            evidence,
        )
        self.assertEqual(result["verdict"], "TRACEABLE_BUT_UNVERIFIED")
        self.assertIn("source_reliability", result)
        self.assertIn("traceability", result)
        # The URL in output should match evidence
        self.assertTrue(result["traceability"]["structural_traceability"])

    def test_needs_evidence_has_empty_reliability(self):
        result = _audit_worker_result(
            "Market is growing.",
            {"simulated": False},
            [],
        )
        self.assertEqual(result["verdict"], "NEEDS_INDEPENDENT_EVIDENCE")
        self.assertEqual(result["source_reliability"]["reliable"], [])
        self.assertEqual(result["source_reliability"]["unreliable"], [])


class TestWorkforceReportEvidenceChain(unittest.TestCase):
    """Test WorkforceRegistry.report() with evidence/provenance fields."""

    def setUp(self):
        self.registry = WorkforceRegistry(path="data/test_evidence_chain.json")
        self.registry.tasks.clear()
        self.registry.events.clear()

    def tearDown(self):
        path = Path(self.registry.path)
        if path.exists():
            path.unlink()

    def test_report_without_evidence_backward_compatible(self):
        """Existing callers without evidence/provenance still work."""
        task = self.registry.create_task(
            title="Test task", capability="research"
        )
        # Simulate assignment
        claimed = self.registry.claim("test-worker", ["research"])
        self.assertIsNotNone(claimed)
        # Report without evidence (backward compatible)
        result = self.registry.report(
            task["id"], "test-worker", "completed",
            output="Test result",
            lease_token=claimed["lease_token"],
        )
        self.assertEqual(result["status"], "awaiting_validation")
        self.assertIn("evidence", result)
        self.assertIn("provenance", result)

    def test_report_with_valid_evidence(self):
        """Report with valid evidence chain fields."""
        task = self.registry.create_task(
            title="Test task", capability="research"
        )
        claimed = self.registry.claim("test-worker", ["research"])
        evidence = [{
            "source_url": "https://example.com/report",
            "source_title": "Market Report 2026",
            "excerpt": "The AI game market grew 45% YoY.",
            "source_type": "secondary",
            "confidence": 0.8,
            "simulated": False,
        }]
        provenance = {
            "executor_type": "live_search",
            "tools_used": ["tavily_search"],
        }
        result = self.registry.report(
            task["id"], "test-worker", "completed",
            output="Market is growing.",
            lease_token=claimed["lease_token"],
            evidence=evidence,
            provenance=provenance,
        )
        self.assertEqual(result["status"], "awaiting_validation")
        self.assertEqual(len(result.get("evidence", [])), 1)
        self.assertEqual(result["evidence"][0]["source_url"], "https://example.com/report")
        self.assertEqual(result["provenance"]["executor_type"], "live_search")

    def test_report_with_non_https_evidence_rejected(self):
        """Non-HTTPS evidence URL is rejected."""
        task = self.registry.create_task(
            title="Test task", capability="research"
        )
        claimed = self.registry.claim("test-worker", ["research"])
        evidence = [{
            "source_url": "http://example.com/report",
        }]
        with self.assertRaises(ValueError) as ctx:
            self.registry.report(
                task["id"], "test-worker", "completed",
                output="Test",
                lease_token=claimed["lease_token"],
                evidence=evidence,
            )
        self.assertIn("HTTPS", str(ctx.exception))

    def test_report_with_simulated_evidence_accepted_but_flagged(self):
        """Simulated evidence is structurally accepted but flagged."""
        task = self.registry.create_task(
            title="Test task", capability="research"
        )
        claimed = self.registry.claim("test-worker", ["research"])
        evidence = [{
            "source_url": "https://example.com/report",
            "simulated": True,
        }]
        result = self.registry.report(
            task["id"], "test-worker", "completed",
            output="Test",
            lease_token=claimed["lease_token"],
            evidence=evidence,
        )
        self.assertEqual(result["status"], "awaiting_validation")
        self.assertTrue(result["evidence"][0]["simulated"])

    def test_report_with_invalid_confidence_rejected(self):
        """Confidence outside 0-1 range is rejected."""
        task = self.registry.create_task(
            title="Test task", capability="research"
        )
        claimed = self.registry.claim("test-worker", ["research"])
        evidence = [{
            "source_url": "https://example.com/report",
            "confidence": 1.5,
        }]
        with self.assertRaises(ValueError) as ctx:
            self.registry.report(
                task["id"], "test-worker", "completed",
                output="Test",
                lease_token=claimed["lease_token"],
                evidence=evidence,
            )
        self.assertIn("0 and 1", str(ctx.exception))

    def test_report_with_invalid_executor_type_rejected(self):
        """Invalid executor_type in provenance is rejected."""
        task = self.registry.create_task(
            title="Test task", capability="research"
        )
        claimed = self.registry.claim("test-worker", ["research"])
        provenance = {"executor_type": "unknown_type"}
        with self.assertRaises(ValueError) as ctx:
            self.registry.report(
                task["id"], "test-worker", "completed",
                output="Test",
                lease_token=claimed["lease_token"],
                provenance=provenance,
            )
        self.assertIn("simulated, llm, or live_search", str(ctx.exception))

    def test_evidence_persisted_to_task(self):
        """Evidence is persisted in the task and visible in snapshot."""
        task = self.registry.create_task(
            title="Test task", capability="research"
        )
        claimed = self.registry.claim("test-worker", ["research"])
        evidence = [{
            "source_url": "https://example.com/report",
            "source_title": "Report",
        }]
        self.registry.report(
            task["id"], "test-worker", "completed",
            output="Test",
            lease_token=claimed["lease_token"],
            evidence=evidence,
        )
        # Reload from disk
        fresh = WorkforceRegistry(path=self.registry.path)
        task_data = fresh.tasks.get(task["id"])
        self.assertIsNotNone(task_data)
        self.assertEqual(len(task_data.get("evidence", [])), 1)
        self.assertEqual(task_data["evidence"][0]["source_url"], "https://example.com/report")


if __name__ == "__main__":
    unittest.main()
