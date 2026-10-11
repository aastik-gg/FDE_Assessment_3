"""Public adapter for the procurement copilot architectures.

The decision path intentionally keeps policy and approval logic deterministic.
An LLM can be added later to summarize a completed evidence pack, but it is
not allowed to decide thresholds, invent evidence, or approve a purchase.
"""
from __future__ import annotations

from src.contracts import Architecture, ProcurementDecision
from src.llm_advisor import LlmAdvisor
from src.policy_engine import build_decision
from src.telemetry import RunTelemetryCounter
from src.tools import EvidencePack, gather_evidence


class ProcurementAgent:
    """Architecture A: one coordinator gathers evidence then applies policy."""

    def run(self, request_id: str, telemetry: RunTelemetryCounter) -> ProcurementDecision:
        evidence = gather_evidence(request_id, telemetry)
        ai_summary = LlmAdvisor().synthesize(evidence, "single procurement coordinator", telemetry)
        return build_decision(evidence, telemetry, architecture="single", ai_summary=ai_summary)


class EvidenceAnalyst:
    """First stage of Architecture B. It has read-only access to the tools."""

    def gather(self, request_id: str, telemetry: RunTelemetryCounter) -> tuple[EvidencePack, str | None]:
        evidence = gather_evidence(request_id, telemetry)
        summary = LlmAdvisor().synthesize(evidence, "evidence analyst", telemetry)
        return evidence, summary


class PolicyReviewer:
    """Second stage of Architecture B. It receives facts, never raw tool access."""

    def review(
        self, evidence: EvidencePack, evidence_summary: str | None, telemetry: RunTelemetryCounter
    ) -> ProcurementDecision:
        reviewer_summary = LlmAdvisor().synthesize(evidence, "policy and risk reviewer", telemetry)
        return build_decision(
            evidence,
            telemetry,
            architecture="staged",
            ai_summary=reviewer_summary or evidence_summary,
        )


def handle_request(request_id: str, architecture: Architecture = "single") -> ProcurementDecision:
    """Analyze a request and return an advisory, human-controlled decision.

    This function is the stable assessment boundary used by the supplied and
    hidden evaluation harnesses. It does not purchase, approve, or mutate data.
    """
    telemetry = RunTelemetryCounter()
    if architecture == "single":
        return ProcurementAgent().run(request_id, telemetry)
    if architecture == "staged":
        evidence, evidence_summary = EvidenceAnalyst().gather(request_id, telemetry)
        return PolicyReviewer().review(evidence, evidence_summary, telemetry)
    raise ValueError(f"Unknown architecture: {architecture}")
