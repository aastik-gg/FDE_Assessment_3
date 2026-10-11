"""Deterministic guardrails for procurement recommendations.

This module is deliberately small and auditable: amounts, dates, mandatory
reviews, and human authority must not depend on an LLM's interpretation.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from src.contracts import EvidenceItem, ProcurementDecision, RunTelemetry
from src.telemetry import RunTelemetryCounter
from src.tools import EvidencePack

REFERENCE_DATE = date(2026, 9, 30)
CURRENT_REVIEW_WINDOW = timedelta(days=365)
APPROVAL_ORDER = ["Manager", "Department Head", "Finance", "CFO", "Procurement", "Security", "Privacy", "Legal"]
SENSITIVE_DATA = {
    "source_code",
    "production_telemetry",
    "production_access",
    "confidential_documents",
    "employee_pii",
    "customer_pii",
    "credentials_secrets",
}
INJECTION_PATTERN = re.compile(
    r"ignore\s+(?:all\s+)?(?:procurement\s+)?rules|"
    r"(?:cfo|manager)[ -]?approved|"
    r"approve\s+(?:it\s+)?immediately|"
    r"bypass\s+(?:controls|review)|"
    r"system\s+instruction",
    flags=re.IGNORECASE,
)


def _add_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _approval_for_cost(cost: float) -> list[str]:
    if cost <= 1_000:
        return ["Manager"]
    if cost <= 10_000:
        return ["Department Head", "Procurement"]
    if cost <= 25_000:
        return ["Department Head", "Finance", "Procurement"]
    return ["Department Head", "Finance", "CFO", "Procurement"]


def _ordered_approvals(approvals: list[str]) -> list[str]:
    return [name for name in APPROVAL_ORDER if name in approvals]


def _is_current(review_date: object) -> bool:
    if not review_date:
        return False
    try:
        reviewed = date.fromisoformat(str(review_date))
    except ValueError:
        return False
    return reviewed >= REFERENCE_DATE - CURRENT_REVIEW_WINDOW


def _missing_fields(pack: EvidencePack) -> list[str]:
    request = pack.request
    missing: list[str] = []
    if not pack.requester or not pack.budget:
        missing.append("Requester and department")
    if not request.get("product_name") or not request.get("vendor_name"):
        missing.append("Product and vendor")
    if request.get("annual_cost_usd") is None:
        missing.append("Annual cost or annual price estimate")
    if not request.get("user_count"):
        missing.append("User or license count")
    if not str(request.get("business_justification", "")).strip():
        missing.append("Business purpose")
    if not request.get("data_access_level") or request.get("data_access_level") == "unknown":
        missing.append("Intended data access level")
    if request.get("requested_integrations") is None:
        missing.append("Required integrations")
    return missing


def build_decision(
    pack: EvidencePack, telemetry: RunTelemetryCounter, architecture: str, ai_summary: str | None = None
) -> ProcurementDecision:
    """Apply the written policy to an evidence pack; never infer missing facts."""
    request = pack.request
    evidence = list(pack.evidence)
    approvals: list[str] = []
    flags: list[str] = []
    missing = _missing_fields(pack)

    if missing:
        _add_once(flags, "missing_information")
        _add_once(approvals, "Procurement")
        evidence.append(EvidenceItem(
            source="deterministic_required_fields_check",
            finding="Request is incomplete: " + "; ".join(missing) + ".",
            reference="Policy section 1",
        ))

    cost = request.get("annual_cost_usd")
    if cost is not None:
        cost = float(cost)
        for approval in _approval_for_cost(cost):
            _add_once(approvals, approval)
        evidence.append(EvidenceItem(
            source="deterministic_approval_threshold_check",
            finding=f"Annual amount ${cost:,.0f} maps to the minimum business approval tier.",
            reference="Policy section 4",
        ))
        if pack.budget:
            available = float(pack.budget["available_usd"])
            if cost > available:
                _add_once(flags, "budget_insufficient")
                _add_once(approvals, "Finance")
                evidence.append(EvidenceItem(
                    source="deterministic_budget_check",
                    finding=f"Requested ${cost:,.0f} exceeds the available ${available:,.0f} department budget.",
                    reference="Policy section 2",
                ))
            else:
                evidence.append(EvidenceItem(
                    source="deterministic_budget_check",
                    finding=f"Requested ${cost:,.0f} is within the available ${available:,.0f} department budget.",
                    reference="Policy section 2",
                ))

    if pack.catalog_matches:
        _add_once(flags, "existing_tool_overlap")
        evidence.append(EvidenceItem(
            source="deterministic_overlap_check",
            finding="Existing catalog capacity or an equivalent category must be reviewed before a new purchase.",
            reference="Policy section 3",
        ))

    data_level = str(request.get("data_access_level", "")).casefold()
    integrations = " ".join(str(item).casefold() for item in request.get("requested_integrations") or [])
    security_needed = data_level in SENSITIVE_DATA or "production" in integrations or "cloud account" in integrations
    privacy_needed = data_level in {"employee_pii", "customer_pii"}
    legal_needed = False

    registry = pack.vendor_registry
    external = pack.vendor_risk
    if not registry:
        security_needed = True
        legal_needed = True
        _add_once(flags, "vendor_registry_missing")
    else:
        if str(registry.get("procurement_status", "")).casefold() != "approved":
            _add_once(flags, "new_vendor")
        if str(registry.get("legal_terms_status", "")).casefold() != "approved":
            legal_needed = True
        if (
            str(registry.get("procurement_status", "")).casefold() != "approved"
            and cost is not None
            and cost >= 10_000
        ):
            legal_needed = True

    if external is None:
        security_needed = True
        _add_once(flags, "vendor_risk_unavailable")
        evidence.append(EvidenceItem(
            source="deterministic_tool_failure_check",
            finding="Required external vendor-security evidence is unavailable; no favorable status was inferred.",
            reference="Policy section 10",
        ))
    else:
        external_status = str(external.get("security_review_status", "")).casefold()
        review_current = _is_current(external.get("last_review_date"))
        if external_status != "approved" or not review_current:
            security_needed = True
            _add_once(flags, "vendor_review_expired" if external_status == "expired" or not review_current else "security_review_required")
        if external.get("stores_data_outside_region") and data_level in SENSITIVE_DATA:
            privacy_needed = True
            legal_needed = True
        if registry and str(registry.get("security_status", "")).casefold() != external_status:
            security_needed = True
            _add_once(flags, "conflicting_vendor_evidence")
            evidence.append(EvidenceItem(
                source="deterministic_vendor_conflict_check",
                finding="Internal vendor registry and external vendor-risk status disagree; Security must reconcile the conflict.",
                reference="Policy section 5",
            ))

    if security_needed:
        _add_once(flags, "security_review_required")
        _add_once(approvals, "Security")
    if privacy_needed:
        _add_once(flags, "privacy_review_required")
        _add_once(approvals, "Privacy")
    if legal_needed:
        _add_once(flags, "legal_review_required")
        _add_once(approvals, "Legal")

    untrusted_text = " ".join(
        str(request.get(field, "")) for field in ("business_justification", "product_name", "vendor_name")
    )
    if INJECTION_PATTERN.search(untrusted_text):
        _add_once(flags, "prompt_injection_detected")
        evidence.append(EvidenceItem(
            source="untrusted_content_guard",
            finding="Instruction-like text in the request was treated as untrusted business data and did not change policy execution.",
            reference="Policy section 9",
        ))

    if missing:
        recommendation = "Request clarification before approval review"
        next_step = "Return the missing fields to the requester, then send the completed evidence package to Procurement."
    elif "budget_insufficient" in flags:
        recommendation = "Do not approve from the current department budget; route for a budget exception review"
        next_step = "Send the evidence package to Finance and the listed human reviewers for an exception decision."
    elif "vendor_risk_unavailable" in flags:
        recommendation = "Hold for manual vendor-risk verification"
        next_step = "Security must verify the vendor assessment outside the unavailable service before Procurement proceeds."
    elif "existing_tool_overlap" in flags:
        recommendation = "Review the existing approved tool before creating a new purchase"
        next_step = "Procurement and the business owner should document the capacity gap or exception, then collect the listed approvals."
    else:
        recommendation = "Route to the required human approval workflow"
        next_step = "Share the evidence package with the listed reviewers; no purchase is authorized by this recommendation."

    evidence.append(EvidenceItem(
        source="workflow",
        finding=(
            "Single coordinator produced the decision from tool evidence."
            if architecture == "single"
            else "Evidence Analyst handed a structured evidence pack to the Policy Reviewer."
        ),
        reference=f"architecture:{architecture}",
    ))
    return ProcurementDecision(
        request_id=request["request_id"],
        recommendation=recommendation,
        evidence=evidence,
        required_approvals=_ordered_approvals(approvals),
        missing_information=missing,
        risk_flags=flags,
        next_step=next_step,
        human_review_required=True,
        ai_summary=ai_summary,
        telemetry=RunTelemetry(
            llm_calls=telemetry.llm_calls,
            tool_calls=telemetry.tool_calls,
            tool_names=telemetry.tool_names,
            llm_model=telemetry.llm_model,
            llm_errors=telemetry.llm_errors,
        ),
    )
