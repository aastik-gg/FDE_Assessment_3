from __future__ import annotations

import json
from html import escape
from pathlib import Path

import streamlit as st

from src.solution import handle_request

ROOT = Path(__file__).resolve().parent
REQUESTS = json.loads((ROOT / "data" / "requests.json").read_text(encoding="utf-8"))
BY_ID = {request["request_id"]: request for request in REQUESTS}

st.set_page_config(page_title="Procurement Copilot", page_icon="◈", layout="wide")
st.markdown(
    """
    <style>
      .stApp { background: #f5f7f8; color: #172b3a; }
      .block-container { max-width: 1480px; padding-top: 5rem; padding-bottom: 3rem; }
      [data-testid="stSidebar"] { background: #102b3e; }
      [data-testid="stSidebar"] * { color: #f4f8f9; }
      [data-testid="stSidebar"] .stRadio label { border: 1px solid rgba(255,255,255,.22); border-radius: .45rem; padding: .35rem .5rem; }
      .eyebrow { color: #178d86; font-size: .76rem; font-weight: 750; letter-spacing: .12em; text-transform: uppercase; margin-bottom: .35rem; }
      .page-title { color: #102b3e; font-size: clamp(2rem, 4vw, 3.2rem); font-weight: 760; letter-spacing: -.045em; line-height: 1; margin: 0; }
      .subtle { color: #58707d; font-size: 1rem; margin-top: .6rem; }
      .guardrail { margin: 1.8rem 0 1.2rem; padding: .85rem 1rem; border-left: 4px solid #d49629; background: #fff9ed; color: #5c460f; border-radius: .2rem; }
      .panel { background: #ffffff; border: 1px solid #dce5e9; border-radius: .55rem; padding: 1.2rem; min-height: 7rem; color: #102b3e; }
      .panel h2 { font-size: 1rem; color: #102b3e; margin: 0 0 .85rem; }
      .request-metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; margin: 0 0 1rem; }
      .request-metric { border-left: 3px solid #d49629; padding-left: .65rem; }
      .request-metric span { display: block; color: #5d7280; font-size: .78rem; font-weight: 650; }
      .request-metric strong { color: #102b3e; font-size: 1.5rem; letter-spacing: -.02em; }
      .request-name { color: #102b3e; font-weight: 730; margin: .25rem 0; }
      .request-detail { color: #5d7280; font-size: .86rem; margin: .25rem 0 .9rem; }
      .request-copy { color: #243b47; line-height: 1.5; margin: 0; }
      .workflow-copy { color: #243b47; line-height: 1.55; margin: 0 0 .9rem; }
      .workflow-detail { color: #5d7280; font-size: .86rem; line-height: 1.45; margin: 0; }
      .decision { background: #0f5560; color: #fff; border-radius: .55rem; padding: 1.35rem; min-height: 13rem; }
      .decision .label { color: #a8e6df; font-size: .72rem; font-weight: 750; letter-spacing: .1em; text-transform: uppercase; }
      .decision .text { font-size: 1.45rem; font-weight: 680; letter-spacing: -.02em; line-height: 1.18; margin: .5rem 0 1rem; }
      .decision .next { color: #e6f5f3; font-size: .93rem; line-height: 1.45; }
      .chip { display: inline-block; padding: .3rem .55rem; border-radius: 999px; margin: 0 .35rem .35rem 0; background: #edf3f4; color: #234856; font-size: .84rem; font-weight: 650; }
      .chip-risk { background: #fff0ed; color: #9a3a28; }
      .metric-wrap { display: flex; gap: .75rem; flex-wrap: wrap; margin-top: .85rem; }
      .metric { padding: .62rem .75rem; border: 1px solid #dce5e9; background: #f9fbfb; border-radius: .45rem; min-width: 7rem; }
      .metric b { display:block; color:#102b3e; font-size: 1.05rem; }
      .metric span { color:#5d7280; font-size:.76rem; }
      .evidence { padding: .75rem 0; border-bottom: 1px solid #e6edef; }
      .evidence:last-child { border-bottom: 0; }
      .source { color: #178d86; font-size: .75rem; font-weight: 750; letter-spacing: .04em; text-transform: uppercase; }
      .finding { color:#243b47; line-height:1.45; margin-top:.2rem; }
      .reference { color:#6c7e87; font-size:.8rem; margin-top:.2rem; }
      .stButton > button { background: #db9b2d; border: 0; color: #182e38; font-weight: 750; border-radius: .4rem; min-height: 2.7rem; }
      .stButton > button:hover { background: #c8871c; color: #102b3e; }
      @media (max-width: 800px) { .block-container { padding: 4.5rem 1rem 2rem; } .request-metrics { grid-template-columns: 1fr; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def money(value: object) -> str:
    return "Not supplied" if value is None else f"${float(value):,.0f}"


def chips(values: list[str], risk: bool = False) -> str:
    if not values:
        return "<span class='subtle'>None</span>"
    css_class = "chip chip-risk" if risk else "chip"
    return "".join(f"<span class='{css_class}'>{value.replace('_', ' ')}</span>" for value in values)


def request_card(request: dict) -> str:
    integrations = ", ".join(request["requested_integrations"]) or "No integrations requested"
    return f"""
    <section class="panel" aria-label="Purchase request details">
      <h2>Purchase request</h2>
      <div class="request-metrics">
        <div class="request-metric"><span>Annual cost</span><strong>{escape(money(request['annual_cost_usd']))}</strong></div>
        <div class="request-metric"><span>Licenses</span><strong>{escape(str(request['user_count'] or 'Not supplied'))}</strong></div>
      </div>
      <p class="request-name">{escape(request['product_name'])} · {escape(request['vendor_name'])}</p>
      <p class="request-detail">{escape(request['category'])} · Data access: {escape(request['data_access_level'].replace('_', ' '))} · {escape(integrations)}</p>
      <p class="request-copy">{escape(request['business_justification'])}</p>
    </section>
    """


with st.sidebar:
    st.markdown("## ◈ Aegis")
    st.caption("Procurement request copilot")
    st.divider()
    architecture = st.radio(
        "Analysis architecture",
        options=["single", "staged"],
        format_func=lambda option: "Single coordinator" if option == "single" else "Staged review",
        help="Both versions use the same policy guardrails and read-only evidence tools.",
    )
    request_id = st.selectbox(
        "Request to review",
        options=list(BY_ID),
        format_func=lambda rid: f"{rid} · {BY_ID[rid]['product_name']}",
    )
    run = st.button("Analyze request", type="primary", use_container_width=True)
    st.divider()
    st.caption("Recommendations are advisory. A human owns every approval, exception, and purchase.")

request = BY_ID[request_id]
st.markdown("<p class='eyebrow'>Procurement controls workspace</p>", unsafe_allow_html=True)
st.markdown("<h1 class='page-title'>Evidence before approval.</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtle'>A grounded recommendation for software and service requests—without automating a sensitive decision.</p>", unsafe_allow_html=True)
st.markdown("<div class='guardrail'>Human control is permanent: this copilot can collect evidence and recommend the next step, but it cannot approve spend, sign terms, or purchase software.</div>", unsafe_allow_html=True)

left, right = st.columns([1.05, 1], gap="large")
with left:
    st.markdown(request_card(request), unsafe_allow_html=True)
with right:
    st.markdown("""
    <section class="panel" aria-label="Workflow">
      <h2>Workflow</h2>
      <p class="workflow-copy"><b>1.</b> Capture request &nbsp; → &nbsp; <b>2.</b> Gather tool evidence &nbsp; → &nbsp; <b>3.</b> Apply deterministic rules &nbsp; → &nbsp; <b>4.</b> Human review</p>
      <p class="workflow-detail">The staged variant hands an immutable evidence pack from the Evidence Analyst to the Policy Reviewer.</p>
    </section>
    """, unsafe_allow_html=True)

if run:
    with st.spinner("Gathering evidence and applying procurement controls..."):
        try:
            result = handle_request(request_id, architecture=architecture)
        except Exception as error:
            st.error(f"Analysis could not complete: {type(error).__name__}: {error}")
        else:
            st.session_state["result"] = result
            st.session_state["result_key"] = (request_id, architecture)

if st.session_state.get("result_key") != (request_id, architecture):
    st.info("Choose an architecture and select **Analyze request** to produce a recommendation.")
else:
    result = st.session_state["result"]
    st.markdown("<p class='eyebrow' style='margin-top:1.8rem'>Copilot output</p>", unsafe_allow_html=True)
    outcome, controls = st.columns([1.1, .9], gap="large")
    with outcome:
        st.markdown(f"<div class='decision'><div class='label'>Recommended next action</div><div class='text'>{result.recommendation}</div><div class='next'><b>Next:</b> {result.next_step}</div></div>", unsafe_allow_html=True)
    with controls:
        st.markdown("<div class='panel'><h2>Human review controls</h2><b>Required approvals</b>", unsafe_allow_html=True)
        st.markdown(chips(result.required_approvals), unsafe_allow_html=True)
        st.markdown("**Risk flags**", unsafe_allow_html=True)
        st.markdown(chips(result.risk_flags, risk=True), unsafe_allow_html=True)
        if result.missing_information:
            st.markdown("**Missing information**", unsafe_allow_html=True)
            st.markdown(chips(result.missing_information, risk=True), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    evidence_tab, trace_tab = st.tabs(["Evidence", "Run trace"])
    with evidence_tab:
        st.markdown("<div class='panel'><h2>Grounded evidence</h2>", unsafe_allow_html=True)
        for item in result.evidence:
            reference = f"<div class='reference'>Reference: {item.reference}</div>" if item.reference else ""
            st.markdown(f"<div class='evidence'><div class='source'>{item.source.replace('_', ' ')}</div><div class='finding'>{item.finding}</div>{reference}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with trace_tab:
        telemetry = result.telemetry
        st.markdown("<div class='panel'><h2>Bounded execution</h2>", unsafe_allow_html=True)
        st.markdown(f"<div class='metric-wrap'><div class='metric'><b>{architecture.title()}</b><span>architecture</span></div><div class='metric'><b>{telemetry.tool_calls if telemetry else 0}</b><span>read-only tool calls</span></div><div class='metric'><b>{telemetry.llm_calls if telemetry else 0}</b><span>approval-making LLM calls</span></div></div>", unsafe_allow_html=True)
        if result.ai_summary:
            st.markdown("**AI synthesis (advisory)**")
            st.write(result.ai_summary)
        if telemetry and telemetry.llm_errors:
            st.caption("LLM fallback: " + telemetry.llm_errors[-1])
        st.caption("Tool evidence and written policy control every approval, even when an LLM is configured.")
        st.code("\n".join(telemetry.tool_names if telemetry else []), language=None)
        st.markdown("</div>", unsafe_allow_html=True)
