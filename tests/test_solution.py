from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from evals.run_public_evals import evaluate
from src.solution import handle_request

ROOT = Path(__file__).resolve().parents[1]
RISK = json.loads((ROOT / "data" / "vendor_risk.json").read_text(encoding="utf-8"))
CASES = json.loads((ROOT / "evals" / "public_cases.json").read_text(encoding="utf-8"))


def risk_response(vendor: str) -> dict:
    record = RISK[vendor]
    if record.get("force_error"):
        raise RuntimeError(record["error_message"])
    return {"vendor_name": vendor, **record}


class ProcurementSolutionTests(unittest.TestCase):
    def setUp(self):
        """Keep ordinary tests offline even when a developer has configured .env."""
        self.llm_environment = patch.dict(
            os.environ,
            {
                "MODEL_NAME": "",
                "OPENAI_API_KEY": "",
                "ANTHROPIC_API_KEY": "",
                "GEMINI_API_KEY": "",
                "GOOGLE_API_KEY": "",
            },
            clear=False,
        )
        self.llm_environment.start()

    def tearDown(self):
        self.llm_environment.stop()

    def test_public_expectations_for_both_architectures(self):
        with patch("src.tools.get_vendor_risk", side_effect=risk_response):
            for architecture in ("single", "staged"):
                for case in CASES:
                    decision = handle_request(case["request_id"], architecture=architecture)
                    self.assertEqual(evaluate(decision, case["expectations"]), [], case["case_id"])

    def test_prompt_injection_is_flagged_but_never_authorizes_purchase(self):
        with patch("src.tools.get_vendor_risk", side_effect=risk_response):
            decision = handle_request("REQ-1006")
        self.assertIn("prompt_injection_detected", decision.risk_flags)
        self.assertTrue(decision.human_review_required)
        self.assertIn("Annual cost or annual price estimate", decision.missing_information)

    def test_conflicting_vendor_evidence_routes_to_security(self):
        with patch("src.tools.get_vendor_risk", side_effect=risk_response):
            decision = handle_request("REQ-1007")
        self.assertIn("conflicting_vendor_evidence", decision.risk_flags)
        self.assertIn("Security", decision.required_approvals)

    def test_llm_enabled_single_and_staged_paths_have_expected_call_counts(self):
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"summary":"Grounded advisory summary."}'))])
        with (
            patch("src.tools.get_vendor_risk", side_effect=risk_response),
            patch("litellm.completion", return_value=response) as completion,
            patch.dict(os.environ, {"MODEL_NAME": "openai/test-model", "OPENAI_API_KEY": "test-key"}, clear=False),
        ):
            single = handle_request("REQ-1001", architecture="single")
            staged = handle_request("REQ-1001", architecture="staged")
        self.assertEqual(single.telemetry.llm_calls, 1)
        self.assertEqual(staged.telemetry.llm_calls, 2)
        self.assertEqual(completion.call_count, 3)
        self.assertEqual(single.ai_summary, "Grounded advisory summary.")


if __name__ == "__main__":
    unittest.main()
