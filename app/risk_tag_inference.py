from __future__ import annotations

"""Deterministic (rule-based) risk tag inference.

Design goals
------------
1) Be *repeatable* and *auditable* (same DDQ → same tags).
2) Prefer objective "signals" over naive keyword matching.
3) Be conservative: tags here are meant to represent material, disclosure-worthy risks.

The inference produces a list of tag IDs (strings).
For debugging, we also attach evidence to `parsed_ddq["_tag_evidence"]`.
"""

from dataclasses import asdict
from typing import Any, Dict, List, Optional, Set

from .ddq_signals import SignalAnswer, get_signal_answer, has_negative_cues, normalise_raw_response
from .token_type import canonical_token_type_from_ddq


def _is_unknownish(ans: Optional[SignalAnswer]) -> bool:
    if not ans:
        return True
    return ans.response_norm in {"unknown", "na"} or normalise_raw_response(ans.raw_response) == "unknown"


def _pct(ans: Optional[SignalAnswer]) -> Optional[float]:
    if not ans:
        return None
    return ans.numeric


def infer_risk_tags_from_ddq(parsed_ddq: Dict[str, Any]) -> List[str]:
    tags: Set[str] = set()
    evidence: Dict[str, List[Dict[str, Any]]] = {}

    def add(tag: str, *ans: Optional[SignalAnswer], note: str = "") -> None:
        tags.add(tag)
        ev: List[Dict[str, Any]] = []
        for a in ans:
            if a:
                d = asdict(a)
                if note:
                    d["note"] = note
                ev.append(d)
        if ev:
            evidence.setdefault(tag, []).extend(ev)

    token_type, token_type_meta = canonical_token_type_from_ddq(parsed_ddq.get("token_category"))
    parsed_ddq["_token_type_inferred"] = {"token_type": token_type, **token_type_meta}

    privileged_scope = get_signal_answer(parsed_ddq, "privileged_functions_scope")
    pause_controls = get_signal_answer(parsed_ddq, "emergency_pause_controls")
    privileged_disclosure = get_signal_answer(parsed_ddq, "privileged_roles_disclosure")
    timelock = get_signal_answer(parsed_ddq, "timelock_present")
    upgradeability = get_signal_answer(parsed_ddq, "upgradeability_profile")
    oracle_rel = get_signal_answer(parsed_ddq, "oracle_reliability")

    liquidity_conc = get_signal_answer(parsed_ddq, "liquidity_concentration")
    exit_feas = get_signal_answer(parsed_ddq, "exit_feasibility")
    wash_flags = get_signal_answer(parsed_ddq, "wash_trading_flags")

    team_alloc = get_signal_answer(parsed_ddq, "team_allocation_pct")
    inv_alloc = get_signal_answer(parsed_ddq, "investor_allocation_pct")
    tres_alloc = get_signal_answer(parsed_ddq, "treasury_allocation_pct")
    unlock_disclosed = get_signal_answer(parsed_ddq, "unlock_schedule_disclosed")
    unlock_next6 = get_signal_answer(parsed_ddq, "unlock_next_6m_pct")
    unlock_milestone = get_signal_answer(parsed_ddq, "unlocks_milestone_link")

    gov_whitepaper = get_signal_answer(parsed_ddq, "governance_described_in_whitepaper")
    gov_disputes = get_signal_answer(parsed_ddq, "prior_governance_disputes")

    # --- Sanctions / AML signals -------------------------------------------------------
    sanc_designated = get_signal_answer(parsed_ddq, "sanctions_designated_wallets")
    sanc_enforcement = get_signal_answer(parsed_ddq, "sanctions_enforcement_actions")
    sanc_geo_volume = get_signal_answer(parsed_ddq, "sanctions_high_risk_geo_volume")
    sanc_structural = get_signal_answer(parsed_ddq, "sanctions_structural_exposure")
    sanc_screening = get_signal_answer(parsed_ddq, "sanctions_screening_controls")

    # --- Governance & control --------------------------------------------------------

    if (
        _is_unknownish(privileged_scope)
        or _is_unknownish(privileged_disclosure)
        or _is_unknownish(pause_controls)
        or (privileged_disclosure and privileged_disclosure.response_norm in {"partial"})
    ):
        add(
            "admin_key_centralisation_risk",
            privileged_scope,
            privileged_disclosure,
            pause_controls,
            note="Privileged controls exist but scope/disclosure/controls are incomplete or unclear.",
        )

    if upgradeability and upgradeability.response_norm in {"yes", "partial", "other"}:
        add("upgradeability_risk", upgradeability, timelock, note="Contracts appear upgradeable (even if limited).")
        if timelock and timelock.response_norm in {"no", "unknown", "partial"}:
            add("timelock_absence_risk", timelock, note="Upgrade/parameter changes may not be adequately timelocked.")

    if gov_disputes and gov_disputes.response_norm == "yes":
        add("governance_dispute_history_risk", gov_disputes)

    # --- Technical & protocol --------------------------------------------------------

    if token_type in {"defi", "governance", "governance_utility", "utility"}:
        add("smart_contract_risk")  # evidence will be backfilled in the report layer if needed

    if oracle_rel and oracle_rel.response_norm not in {"na"}:
        low = oracle_rel.raw_response.lower()
        if "no oracle" not in low and "not oracle" not in low:
            add("oracle_dependency_risk", oracle_rel)
            if oracle_rel.response_norm in {"partial", "unknown"}:
                add("defi_liquidation_mechanism_risk", oracle_rel, note="Oracle design/reliability may affect liquidations.")

    if (
        (oracle_rel and any(k in oracle_rel.raw_response.lower() for k in ["mixed", "custom", "multi", "oracle-agnostic"]))
        or (_is_unknownish(privileged_scope) and _is_unknownish(pause_controls))
    ):
        add("complex_protocol_design_risk", oracle_rel, privileged_scope, pause_controls)

    # --- Market integrity & liquidity ------------------------------------------------

    if liquidity_conc and any(k in liquidity_conc.raw_response.lower() for k in ["concentrated", "few"]):
        add("liquidity_concentration_risk", liquidity_conc)

    if exit_feas and any(k in exit_feas.raw_response.lower() for k in ["significant care", "difficult", "limited"]):
        add("low_liquidity_risk", exit_feas)

    if wash_flags:
        low = wash_flags.raw_response.lower()
        if any(k in low for k in ["significant", "concern", "flags", "elevated"]) and "no significant" not in low:
            add("wash_trading_risk", wash_flags)

    # --- Tokenomics & supply overhang -------------------------------------------------

    t = _pct(team_alloc) or 0.0
    i = _pct(inv_alloc) or 0.0
    r = _pct(tres_alloc) or 0.0

    if r >= 25:
        add("treasury_concentration_risk", tres_alloc, note="Large treasury/foundation allocation suggests concentration risk.")

    if (t + i + r) >= 60 or max(t, i, r) >= 35:
        add(
            "tokenomics_concentration_risk",
            team_alloc,
            inv_alloc,
            tres_alloc,
            note="Large insider/treasury allocations may increase concentration and supply overhang risk.",
        )

    if unlock_disclosed and unlock_disclosed.response_norm in {"no", "unknown"}:
        add("unlock_schedule_uncertainty_risk", unlock_disclosed)
    if unlock_next6 and unlock_next6.response_norm in {"unknown"}:
        add("unlock_schedule_uncertainty_risk", unlock_next6, note="Near-term unlock percentage is unclear.")
    if unlock_milestone and unlock_milestone.response_norm == "no":
        add("insider_unlocks_risk", unlock_milestone, note="Unlocks are not tied to adoption milestones.")

    # --- Disclosure & transparency ----------------------------------------------------

    if gov_whitepaper and gov_whitepaper.response_norm == "no":
        add("governance_documentation_gaps_risk", gov_whitepaper)

    unknown_count = sum(
        1
        for a in [privileged_scope, pause_controls, privileged_disclosure, oracle_rel, unlock_next6]
        if _is_unknownish(a)
    )
    if unknown_count >= 2:
        add("poor_disclosure_quality_risk", note="Multiple key DDQ controls/metrics are unknown or unclear.")

    for a in [privileged_scope, pause_controls, privileged_disclosure, oracle_rel]:
        if a and has_negative_cues(a.narrative):
            add("poor_disclosure_quality_risk", a)

    # --- Sanctions / financial crime --------------------------------------------------

    # Known designated wallets/entities is a strong signal.
    if sanc_designated and sanc_designated.response_norm in {"yes", "partial"}:
        add("sanctions_designated_wallets_risk", sanc_designated, note="Token/project has been linked to designated wallets/entities.")

    # Public enforcement/regulatory actions referencing sanctions issues.
    if sanc_enforcement and sanc_enforcement.response_norm in {"yes", "partial"}:
        add("sanctions_enforcement_watch_risk", sanc_enforcement, note="Public enforcement / regulatory actions referencing sanctions risk.")

    # Structural exposure (e.g., dependence on high-risk venues/bridges) or high-risk geo volume.
    if sanc_structural:
        low = sanc_structural.raw_response.lower()
        if any(k in low for k in ["high", "structural", "material"]) or sanc_structural.response_norm in {"yes", "partial", "unknown"}:
            add("sanctions_exposure_risk", sanc_structural, note="DDQ indicates structural sanctions / high-risk ecosystem exposure.")

    if sanc_geo_volume:
        low = sanc_geo_volume.raw_response.lower()
        if any(k in low for k in ["high", "material", "meaningful", "unknown"]) or sanc_geo_volume.response_norm in {"partial", "unknown"}:
            add("sanctions_exposure_risk", sanc_geo_volume, note="DDQ indicates non-trivial or uncertain exposure to high-risk jurisdictions.")

    # Weak/partial sanctions screening controls amplifies risk.
    if sanc_screening and sanc_screening.response_norm in {"no", "partial", "unknown"}:
        add("sanctions_screening_controls_risk", sanc_screening, note="Sanctions screening controls appear partial/unclear or absent.")

    parsed_ddq["_tag_evidence"] = evidence
    return sorted(tags)
