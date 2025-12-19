from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .llm_client import generate_executive_summary_via_gpt


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _headline_for_posture(posture: str | None) -> str:
    p = (posture or "").strip().lower()
    if p == "heightened":
        return "Heightened risk – committee judgment required"
    if p == "intermediate":
        return "Suitable for listing with enhanced monitoring"
    if p == "benign":
        return "Suitable for listing with standard monitoring"
    return "Committee decision required"


def _compact_requirements(listing_requirements: List[Dict[str, Any]], max_items: int = 6) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in listing_requirements or []:
        out.append({"id": r.get("id"), "severity": r.get("severity"), "title": r.get("title")})
        if len(out) >= max_items:
            break
    return out


def _rule_based_summary(
    *,
    token_fact_sheet: Dict[str, Any],
    risk_dashboard: Dict[str, Any],
    domain_findings: List[Dict[str, Any]],
    board_escalations: List[Dict[str, Any]],
    asset_specific_risks: List[Dict[str, Any]],
    listing_requirements: List[Dict[str, Any]],
    listing_ctx: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    listing_ctx = listing_ctx or {}
    posture = listing_ctx.get("posture")
    overall = (risk_dashboard.get("overall_band") or {})
    band_name = overall.get("name") or "Unknown"
    band_num = overall.get("numeric") or 0

    esc_count = len(board_escalations or [])

    # Positives: take up to 3 strongest "strengths" statements from domains that are not in the highest bands.
    positives: List[str] = []
    for d in domain_findings or []:
        if int(d.get("band_numeric") or 0) <= 3:
            for s in (d.get("strengths") or [])[:2]:
                if s and s not in positives:
                    positives.append(s)
                if len(positives) >= 4:
                    break
        if len(positives) >= 4:
            break
    positives = positives[:4]

    # Risks/mitigations: use listing requirements as the "mitigation" anchor.
    risks_and_mitigations: List[Dict[str, str]] = []
    top_risk_texts: List[str] = []
    for cat in asset_specific_risks or []:
        for item in (cat.get("items") or [])[:2]:
            txt = (item.get("text") or "").strip()
            if txt and txt not in top_risk_texts:
                top_risk_texts.append(txt)
            if len(top_risk_texts) >= 4:
                break
        if len(top_risk_texts) >= 4:
            break

    req_texts = [r.get("text") for r in (listing_requirements or []) if r.get("text")]
    default_mitigation = "Apply the listed internal controls and monitoring actions, and schedule re-review after material events."
    for i, risk_txt in enumerate(top_risk_texts[:4]):
        mitigation = default_mitigation
        if i < len(req_texts):
            mitigation = req_texts[i]
        risks_and_mitigations.append({"risk": risk_txt, "mitigation": mitigation})

    # Notable escalations: take up to 2
    notable = []
    for e in (board_escalations or [])[:2]:
        domain = e.get("domain_name")
        issue = (e.get("question_text") or "").strip()
        if issue:
            issue = (issue[:110] + "...") if len(issue) > 113 else issue
        notable.append({"domain": domain, "issue": issue})

    # Narrative
    name = ((token_fact_sheet.get("asset") or {}).get("name") or "This token")
    narrative = (
        f"{name} is assessed as {band_name} overall (band {band_num}/5). "
        f"{esc_count} DDQ item(s) triggered board-level escalation flags requiring senior review. "
        "The recommended approach is to list only with controls proportionate to the identified risk drivers, "
        "and to treat material protocol, governance, or reputational developments as re-review triggers."
    )

    open_questions: List[str] = []
    if listing_ctx.get("has_hard_control"):
        open_questions.append(
            "Confirm who can exercise privileged control (admin keys, upgrades, governance) and what oversight applies post-listing."
        )
    if listing_ctx.get("has_speculative_profile"):
        open_questions.append(
            "Confirm whether additional retail guard-rails (exposure caps, stricter appropriateness) are required for this asset profile."
        )
    if not open_questions:
        open_questions.append("Confirm the monitoring and reassessment cadence to maintain an up-to-date risk view post-listing.")

    return {
        "headline_decision_view": _headline_for_posture(posture),
        "overall_posture": posture,
        "one_paragraph_narrative": narrative,
        "key_positives": positives,
        "key_risks_and_mitigations": risks_and_mitigations,
        "board_escalations_summary": {"count": esc_count, "notable": notable},
        "recommended_listing_requirements": _compact_requirements(listing_requirements),
        "open_questions_for_committee": open_questions[:4],
        "generation": {"method": "rule_based", "model": None, "timestamp_utc": _utc_now_iso()},
    }


def build_executive_summary(
    *,
    token_fact_sheet: Dict[str, Any],
    risk_dashboard: Dict[str, Any],
    domain_findings: List[Dict[str, Any]],
    board_escalations: List[Dict[str, Any]],
    asset_specific_risks: List[Dict[str, Any]],
    listing_requirements: List[Dict[str, Any]],
    listing_ctx: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build an executive summary.

    GPT is optional. Toggle with USE_GPT_EXECUTIVE_SUMMARY=1.
    If GPT fails for any reason, we fall back to a deterministic summary.
    """

    use_gpt = os.getenv("USE_GPT_EXECUTIVE_SUMMARY", "1") == "1"
    listing_ctx = listing_ctx or {}

    if not use_gpt:
        return _rule_based_summary(
            token_fact_sheet=token_fact_sheet,
            risk_dashboard=risk_dashboard,
            domain_findings=domain_findings,
            board_escalations=board_escalations,
            asset_specific_risks=asset_specific_risks,
            listing_requirements=listing_requirements,
            listing_ctx=listing_ctx,
        )

    # Curated payload for the model (avoid dumping the full DDQ)
    payload = {
        "asset": token_fact_sheet.get("asset"),
        "classification": token_fact_sheet.get("classification"),
        "overall_band": risk_dashboard.get("overall_band"),
        "top_domains": (token_fact_sheet.get("risk_highlights") or {}).get("top_domains"),
        "top_risk_tags": (token_fact_sheet.get("risk_highlights") or {}).get("top_risk_tags"),
        "board_escalations": (board_escalations or [])[:6],
        "domain_findings_one_line": [
            {
                "domain": d.get("domain_name"),
                "band": d.get("band_name"),
                "one_line": d.get("one_line"),
            }
            for d in (domain_findings or [])
        ],
        "listing_requirements": _compact_requirements(listing_requirements, max_items=8),
        "posture": listing_ctx.get("posture"),
        "flags": {
            "has_speculative_profile": bool(listing_ctx.get("has_speculative_profile")),
            "has_hard_control": bool(listing_ctx.get("has_hard_control")),
        },
    }

    try:
        out = generate_executive_summary_via_gpt(payload)
        out.setdefault("generation", {})
        out["generation"].setdefault("method", "gpt")
        out["generation"].setdefault("model", os.getenv("OPENAI_EXEC_SUMMARY_MODEL") or os.getenv("OPENAI_DOMAIN_MODEL"))
        out["generation"].setdefault("timestamp_utc", _utc_now_iso())
        return out
    except Exception as e:
        # Hard fallback: report still renders.
        rb = _rule_based_summary(
            token_fact_sheet=token_fact_sheet,
            risk_dashboard=risk_dashboard,
            domain_findings=domain_findings,
            board_escalations=board_escalations,
            asset_specific_risks=asset_specific_risks,
            listing_requirements=listing_requirements,
            listing_ctx=listing_ctx,
        )
        rb["generation"]["method"] = "rule_based"
        rb["generation"]["model"] = None
        rb["generation"]["error"] = str(e)
        return rb
