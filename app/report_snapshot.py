from typing import Any, Dict, List, Tuple
from collections import defaultdict
import os

from .models import DomainStats, BoardEscalation
from .llm_client import generate_domain_findings_via_gpt




# --- Helpers for bands ---------------------------------------------------


def _band_name_from_numeric(n: int) -> str:
    """
    Convert our 1–5 numeric bands back to names, mirroring your Excel logic:
      1 -> Very Low
      2 -> Low
      3 -> Medium
      4 -> Medium-High
      5 -> High
    """
    mapping = {
        1: "Very Low",
        2: "Low",
        3: "Medium",
        4: "Medium-High",
        5: "High",
    }
    return mapping.get(n, "Unknown")


def _overall_band_from_domains(domains: List[DomainStats]) -> Tuple[int, str]:
    """
    Compute a simple overall band as the weighted average of domain band_numeric,
    using domain weight as the weight. If weights sum to 0, fall back to simple average.
    """
    if not domains:
        return 0, "Unknown"

    total_weight = sum(d.weight for d in domains)
    if total_weight <= 0:
        # fallback: equal-weight average
        total_weight = len(domains)
        weighted_sum = sum(d.band_numeric for d in domains)
    else:
        weighted_sum = sum(d.band_numeric * d.weight for d in domains)

    avg_band_numeric = weighted_sum / total_weight

    # round to nearest integer band
    overall_numeric = int(round(avg_band_numeric))
    overall_name = _band_name_from_numeric(overall_numeric)
    return overall_numeric, overall_name


def _band_distribution(domains: List[DomainStats]) -> Dict[str, float]:
    """
    Compute how much weight is in each band name; useful for stacked bar / legend.
    Returns dict like {"Very Low": 0.2, "Low": 0.4, ...}.
    """
    out: Dict[str, float] = {}
    total_weight = sum(d.weight for d in domains)
    if total_weight <= 0:
        return out

    for d in domains:
        band = d.band_name
        out[band] = out.get(band, 0.0) + d.weight / total_weight

    return out


# --- Board escalation filtering ------------------------------------------


_NON_ESCALATION_FLAGS = {
    "",
    "no",
    "false",
    "0",
    "no review",  # informational only
}

_REAL_ESCALATION_KEYWORDS = [
    "review required",
    "board review",
    "listing committee",
    "escalate",
    "reject",
]


def _is_real_board_trigger(flag: str) -> bool:
    """
    Same logic as in ddq_parser: treat 'Review Required' etc. as real triggers,
    ignore 'No Review' / empty / informational-only flags.
    """
    if flag is None:
        return False
    f = flag.strip().lower()
    if f in _NON_ESCALATION_FLAGS:
        return False
    return any(k in f for k in _REAL_ESCALATION_KEYWORDS)


def _build_domain_findings_rule_based(
    domains: List[DomainStats],
    board_escalations: List[BoardEscalation],
) -> List[Dict[str, Any]]:
    """
    Build a simple, deterministic set of domain-level findings from:
      - domain stats (band, avg_score, escalation counts)
      - real board escalation rows (for headlines/watchpoints).

    This is intentionally rule-based (no GPT) for now, so it's:
      - predictable
      - easy to test
      - easy to later upgrade to GPT without changing the JSON shape.
    """
    # Group real escalation rows by domain_code
    real_by_domain: Dict[str, List[BoardEscalation]] = defaultdict(list)
    for esc in board_escalations:
        if _is_real_board_trigger(esc.flag):
            real_by_domain[esc.domain_code].append(esc)

    findings: List[Dict[str, Any]] = []

    for d in domains:
        escalations = real_by_domain.get(d.code, [])

        # --- one_line summary ---------------------------------------------
        if d.has_board_escalation and escalations:
            one_line = (
                f"{d.name}: {d.band_name} risk with "
                f"{d.board_escalation_count} board escalation trigger(s) "
                f"requiring senior review."
            )
        else:
            one_line = (
                f"{d.name}: {d.band_name} risk with no board escalation "
                f"triggers identified in the current assessment."
            )

        # --- strengths ----------------------------------------------------
        strengths: List[str] = []

        if d.band_numeric <= 2:
            strengths.append(
                "Scores cluster in the lower risk bands, indicating relatively "
                "limited concern in this domain on current evidence."
            )
        elif d.band_numeric == 3:
            strengths.append(
                "Scores are broadly in the Medium band, suggesting a balanced "
                "risk profile with meaningful strengths and weaknesses."
            )
        else:
            strengths.append(
                "Despite an elevated risk band, the domain is supported by a "
                "structured due-diligence review and documented controls."
            )

        if not d.has_board_escalation:
            strengths.append(
                "No questions in this domain triggered board-level escalation "
                "flags in the current DDQ run."
            )

        if d.avg_score >= 8:
            strengths.append(
                "Average scores above 8 indicate strong controls or favourable "
                "characteristics in this area relative to peers."
            )

        # --- risks --------------------------------------------------------
        risks: List[str] = []

        if d.band_numeric >= 4:
            risks.append(
                f"The domain is rated {d.band_name}, indicating multiple higher-"
                "concern factors that may require mitigations before listing."
            )
        elif d.band_numeric == 3:
            risks.append(
                "Medium risk band: residual issues and uncertainties remain, "
                "and further comfort may be needed depending on the use-case."
            )
        else:
            # Low/Very Low
            risks.append(
                "While overall risk is in the lower bands, crypto assets remain "
                "inherently volatile and subject to rapid change."
            )

        if d.has_board_escalation and escalations:
            risks.append(
                "One or more DDQ questions triggered a board escalation flag; "
                "these items should be considered individually by the listing "
                "or risk committee."
            )

            # Add short bullets naming what actually triggered
            for esc in escalations:
                risks.append(
                    f"Escalation: {esc.question_id} – {esc.question_text[:90]}..."
                )

        # --- watchpoints --------------------------------------------------
        watchpoints: List[str] = []

        name_lower = d.name.lower()

        if "regulatory" in name_lower or "legal" in name_lower:
            watchpoints.append(
                "Monitor for new regulatory actions, guidance or enforcement "
                "affecting the issuer, token, or comparable projects."
            )
        if "aml" in name_lower or "sanctions" in name_lower:
            watchpoints.append(
                "Keep under review any changes in sanctions regimes, law "
                "enforcement actions or on-chain typologies linked to the asset."
            )
        if "technical" in name_lower or "protocol" in name_lower:
            watchpoints.append(
                "Track protocol upgrades, security advisories and incident "
                "reports that could affect technical risk over time."
            )
        if "market" in name_lower or "liquidity" in name_lower:
            watchpoints.append(
                "Monitor market depth, spreads and derivatives activity, "
                "particularly around stress events and large flows."
            )
        if "strategic" in name_lower or "reputational" in name_lower:
            watchpoints.append(
                "Monitor media coverage, community sentiment and major "
                "partnerships that could alter the project’s risk profile."
            )
        if not watchpoints:
            watchpoints.append(
                "Revisit this domain periodically as part of ongoing monitoring "
                "to capture new information or emerging risks."
            )

        findings.append(
            {
                "domain_code": d.code,
                "domain_name": d.name,
                "band_name": d.band_name,
                "band_numeric": d.band_numeric,
                "avg_score": d.avg_score,
                "has_board_escalation": d.has_board_escalation,
                "board_escalation_count": d.board_escalation_count,
                "one_line": one_line,
                "strengths": strengths,
                "risks": risks,
                "watchpoints": watchpoints,
            }
        )

    return findings

def _build_domain_findings_gpt(
    domains: List[DomainStats],
    board_escalations: List[BoardEscalation],
    model: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Build domain findings using GPT for narrative fields, keeping the same JSON shape
    as the rule-based version.

    IMPORTANT: We use *all* narrative Q&As (BoardEscalation rows) for that domain
    as context, even if flag == "No Review". The 'Review Required' ones are just
    treated as higher-salience by the model.
    """
    findings: List[Dict[str, Any]] = []

    # Group ALL escalation/narrative rows by domain_name (not just Review Required)
    by_domain: Dict[str, List[BoardEscalation]] = defaultdict(list)
    for esc in board_escalations:
        by_domain[esc.domain_name].append(esc)

    for d in domains:
        domain_escalations = by_domain.get(d.name, [])

        try:
            gpt_fields = generate_domain_findings_via_gpt(d, domain_escalations, model=model)
        except Exception as e:
            # Log + fallback so the report still works
            print(f"[WARN] GPT domain findings failed for '{d.name}': {e}")
            # Use your existing rule-based helper for this one domain
            rb = _build_domain_findings_rule_based([d], board_escalations)
            if rb:
                findings.append(rb[0])
            continue

        findings.append(
            {
                "domain_code": d.code,
                "domain_name": d.name,
                "band_name": d.band_name,
                "band_numeric": d.band_numeric,
                "avg_score": d.avg_score,
                "has_board_escalation": d.has_board_escalation,
                "board_escalation_count": d.board_escalation_count,
                "one_line": gpt_fields.get("one_line", ""),
                "strengths": gpt_fields.get("strengths", []),
                "risks": gpt_fields.get("risks", []),
                "watchpoints": gpt_fields.get("watchpoints", []),
            }
        )

    return findings



# --- Public API ----------------------------------------------------------


def build_report_snapshot(parsed_ddq: Dict[str, Any]) -> Dict[str, Any]:
    """
    Take the raw parsed DDQ output (from parse_ddq) and build a higher-level
    snapshot object that the HTML/PDF renderer can consume.

    For now this includes:
      - risk_dashboard: overall band, per-domain cards, band distribution
      - board_escalations: list of escalation cards (real triggers only)
    """
    domain_stats: List[DomainStats] = parsed_ddq.get("domain_stats", [])
    board_escalations: List[BoardEscalation] = parsed_ddq.get("board_escalations", [])

    # --- Risk dashboard (top panel) --------------------------------------

    overall_band_numeric, overall_band_name = _overall_band_from_domains(domain_stats)
    band_distribution = _band_distribution(domain_stats)

    domains_payload: List[Dict[str, Any]] = []
    for d in domain_stats:
        domains_payload.append(
            {
                "code": d.code,
                "name": d.name,
                "weight": d.weight,
                "avg_score": d.avg_score,
                "band_name": d.band_name,
                "band_numeric": d.band_numeric,
                "has_board_escalation": d.has_board_escalation,
                "board_escalation_count": d.board_escalation_count,
            }
        )

    risk_dashboard = {
        "overall_band": {
            "numeric": overall_band_numeric,
            "name": overall_band_name,
        },
        "band_distribution": band_distribution,  # for a stacked bar / legend
        "domains": domains_payload,
    }

    # --- Board escalation cards ------------------------------------------

    escalation_cards: List[Dict[str, Any]] = []
    for esc in board_escalations:
        if not _is_real_board_trigger(esc.flag):
            # Skip informational "No Review" narratives
            continue

        escalation_cards.append(
            {
                "id": esc.id,
                "domain_code": esc.domain_code,
                "domain_name": esc.domain_name,
                "question_id": esc.question_id,
                "question_text": esc.question_text,
                "flag": esc.flag,
                "trigger_rule": esc.trigger_rule,
                "raw_narrative": esc.raw_narrative,
                "most_recent_source_date": esc.most_recent_source_date,
                "staleness_class": esc.staleness_class,
                "citations": esc.citations,
            }
        )

    # --- Domain findings (GPT, with rule-based fallback) -----------------

    use_gpt = os.getenv("USE_GPT_DOMAIN_FINDINGS", "1") == "1"
    if use_gpt:
        domain_findings = _build_domain_findings_gpt(domain_stats, board_escalations)
    else:
        domain_findings = _build_domain_findings_rule_based(domain_stats, board_escalations)



    snapshot = {
        "risk_dashboard": risk_dashboard,
        "board_escalations": escalation_cards,
        "domain_findings": domain_findings,
        "asset_specific_risks": [],
        "listing_requirements": [],
        "token_fact_sheet": {},
        "executive_summary": {},
    }


    return snapshot
