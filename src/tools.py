"""Read-only tools used by both copilot architectures.

Requester text and vendor notes are always returned as data. They are never
executed as instructions or used to override the policy engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.contracts import EvidenceItem
from src.data_access import (
    get_request,
    load_budgets,
    load_employees,
    load_policy_text,
    load_software_catalog,
    load_vendors,
)
from src.telemetry import RunTelemetryCounter
from src.vendor_client import get_vendor_risk


@dataclass
class EvidencePack:
    request: dict[str, Any]
    requester: dict[str, Any] | None
    budget: dict[str, Any] | None
    catalog_matches: list[dict[str, Any]]
    vendor_registry: dict[str, Any] | None
    vendor_risk: dict[str, Any] | None
    vendor_risk_error: str | None
    policy_text: str
    evidence: list[EvidenceItem]


def _records(frame) -> list[dict[str, Any]]:
    return frame.fillna("").to_dict(orient="records")


def _find_first(records: list[dict[str, Any]], field: str, value: str) -> dict[str, Any] | None:
    target = value.casefold()
    return next((record for record in records if str(record[field]).casefold() == target), None)


def gather_evidence(request_id: str, telemetry: RunTelemetryCounter) -> EvidencePack:
    """Retrieve the facts required by the policy. All tools are read-only."""
    telemetry.record_tool_call("request_context_tool")
    request = get_request(request_id)

    telemetry.record_tool_call("organization_budget_tool")
    requester = _find_first(_records(load_employees()), "employee_id", request["requester_id"])
    budget = None
    if requester:
        budget = _find_first(_records(load_budgets()), "department", str(requester["department"]))

    telemetry.record_tool_call("software_catalog_tool")
    catalog = _records(load_software_catalog())
    category = str(request.get("category", "")).casefold()
    product = str(request.get("product_name", "")).casefold()
    vendor = str(request.get("vendor_name", "")).casefold()
    catalog_matches = [
        item
        for item in catalog
        if str(item["category"]).casefold() == category
        or str(item["vendor_name"]).casefold() == vendor
        or str(item["product_name"]).casefold() == product
    ]

    telemetry.record_tool_call("vendor_registry_tool")
    vendor_registry = _find_first(_records(load_vendors()), "vendor_name", request["vendor_name"])

    telemetry.record_tool_call("vendor_risk_api_tool")
    vendor_risk: dict[str, Any] | None = None
    vendor_risk_error: str | None = None
    try:
        vendor_risk = get_vendor_risk(request["vendor_name"])
    except Exception as exc:  # A failed tool is unknown, never favorable.
        vendor_risk_error = f"{type(exc).__name__}: {exc}"

    telemetry.record_tool_call("policy_tool")
    policy_text = load_policy_text()

    evidence = [
        EvidenceItem(
            source="request_context_tool",
            finding=(
                f"{request['product_name']} requested from {request['vendor_name']} for "
                f"{request.get('annual_cost_usd') if request.get('annual_cost_usd') is not None else 'an unspecified amount'} annually."
            ),
            reference=request_id,
        ),
        EvidenceItem(
            source="organization_budget_tool",
            finding=(
                f"Requester department: {requester['department']}; available software budget: "
                f"${int(budget['available_usd']):,}."
                if requester and budget
                else "Requester department or budget record could not be resolved."
            ),
            reference=str(requester["employee_id"]) if requester else None,
        ),
        EvidenceItem(
            source="software_catalog_tool",
            finding=(
                "Potential existing options: "
                + ", ".join(f"{item['product_name']} ({item['vendor_name']})" for item in catalog_matches)
                if catalog_matches
                else "No same-vendor, same-product, or same-category catalog item found."
            ),
            reference=", ".join(str(item["software_id"]) for item in catalog_matches) or None,
        ),
        EvidenceItem(
            source="vendor_registry_tool",
            finding=(
                f"Registry status: {vendor_registry['procurement_status']}; security: {vendor_registry['security_status']}; "
                f"legal terms: {vendor_registry['legal_terms_status']}."
                if vendor_registry
                else "No internal vendor registry record found."
            ),
            reference=str(vendor_registry["vendor_id"]) if vendor_registry else None,
        ),
        EvidenceItem(
            source="vendor_risk_api_tool",
            finding=(
                f"External security status: {vendor_risk.get('security_review_status')}; "
                f"last review: {vendor_risk.get('last_review_date') or 'not supplied'}; "
                f"risk: {vendor_risk.get('risk_level', 'unknown')}."
                if vendor_risk
                else f"Vendor-risk API could not be verified: {vendor_risk_error}"
            ),
            reference=request["vendor_name"],
        ),
        EvidenceItem(
            source="policy_tool",
            finding="Policy version 2026.09 applied with the 2026-09-30 reference date.",
            reference="procurement_policy.md",
        ),
    ]
    return EvidencePack(
        request=request,
        requester=requester,
        budget=budget,
        catalog_matches=catalog_matches,
        vendor_registry=vendor_registry,
        vendor_risk=vendor_risk,
        vendor_risk_error=vendor_risk_error,
        policy_text=policy_text,
        evidence=evidence,
    )
