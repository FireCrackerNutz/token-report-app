"""DDQ question registry.

Why this exists
--------------
Your DDQ workbook evolves (question IDs get renumbered, moved, or renamed).
To keep deterministic inference maintainable, we centralise *all* signal → question
lookups in one place.

When you change the DDQ
-----------------------
Update this module only:
  - Add aliases (old id -> new id) to `QUESTION_ID_ALIASES`.
  - Update `SIGNAL_SOURCES` for the signals you care about.

Inference code should never hard-code question IDs directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence


@dataclass(frozen=True)
class SignalSource:
    sheet: str
    question_ids: Sequence[str]


QUESTION_ID_ALIASES: Dict[str, List[str]] = {
    # Add renumbered IDs here later, e.g.:
    # "B1.1": ["B1.1", "B1.1_NEW"],
}


def expand_qids(qid: str) -> List[str]:
    qid = (qid or "").strip()
    if not qid:
        return []
    alts = QUESTION_ID_ALIASES.get(qid, None)
    if alts:
        return list(dict.fromkeys([*alts]))
    return [qid]


SIGNAL_SOURCES: Dict[str, List[SignalSource]] = {
    # --- Governance / privileged control -------------------------------------------------
    "privileged_functions_scope": [SignalSource(sheet="Technical & Protocol Security", question_ids=expand_qids("B3.1"))],
    "emergency_pause_controls": [SignalSource(sheet="Technical & Protocol Security", question_ids=expand_qids("B3.2"))],
    "privileged_roles_disclosure": [SignalSource(sheet="Technical & Protocol Security", question_ids=expand_qids("C1.1"))],
    "timelock_present": [SignalSource(sheet="Technical & Protocol Security", question_ids=expand_qids("C3.1"))],

    # --- Upgradeability -------------------------------------------------------------------
    "upgradeability_profile": [SignalSource(sheet="Technical & Protocol Security", question_ids=expand_qids("A4.3"))],

    # --- Oracle / external dependency -----------------------------------------------------
    "oracle_reliability": [SignalSource(sheet="Technical & Protocol Security", question_ids=expand_qids("A4.2"))],

    # --- Audits ---------------------------------------------------------------------------
    "audit_coverage": [SignalSource(sheet="Technical & Protocol Security", question_ids=expand_qids("A1.1"))],
    "audit_firm_quality": [SignalSource(sheet="Technical & Protocol Security", question_ids=expand_qids("A1.2"))],
    "audit_recency": [SignalSource(sheet="Technical & Protocol Security", question_ids=expand_qids("A1.3"))],
    "audit_reaudit_after_changes": [SignalSource(sheet="Technical & Protocol Security", question_ids=expand_qids("A1.4"))],
    "audit_max_severity": [SignalSource(sheet="Technical & Protocol Security", question_ids=expand_qids("A1.5"))],

    # --- Market integrity / liquidity -----------------------------------------------------
    "liquidity_concentration": [SignalSource(sheet="Market & Liquidity Integrity", question_ids=expand_qids("A2.3"))],
    "exit_feasibility": [SignalSource(sheet="Market & Liquidity Integrity", question_ids=expand_qids("A2.2"))],
    "wash_trading_flags": [SignalSource(sheet="Market & Liquidity Integrity", question_ids=expand_qids("B2.1"))],

    # --- Tokenomics / allocations ---------------------------------------------------------
    "team_allocation_pct": [SignalSource(sheet="Token Fundamentals & Governance", question_ids=expand_qids("E2.1"))],
    "investor_allocation_pct": [SignalSource(sheet="Token Fundamentals & Governance", question_ids=expand_qids("E2.2"))],
    "treasury_allocation_pct": [SignalSource(sheet="Token Fundamentals & Governance", question_ids=expand_qids("E2.3"))],
    "unlock_schedule_disclosed": [SignalSource(sheet="Token Fundamentals & Governance", question_ids=expand_qids("E2.4"))],
    "unlock_next_6m_pct": [SignalSource(sheet="Token Fundamentals & Governance", question_ids=expand_qids("E2.5"))],
    "unlock_pacing_style": [SignalSource(sheet="Token Fundamentals & Governance", question_ids=expand_qids("E3.2"))],
    "unlocks_milestone_link": [SignalSource(sheet="Token Fundamentals & Governance", question_ids=expand_qids("E3.3"))],

    # --- Governance disclosure / disputes -------------------------------------------------
    "governance_described_in_whitepaper": [SignalSource(sheet="Token Fundamentals & Governance", question_ids=expand_qids("D3"))],
    "prior_governance_disputes": [SignalSource(sheet="Token Fundamentals & Governance", question_ids=expand_qids("B2.7"))],

    # --- Sanctions / AML ------------------------------------------------------------------
    "sanctions_designated_wallets": [SignalSource(sheet="AML & Sanctions Risk", question_ids=expand_qids("B1.1"))],
    "sanctions_enforcement_actions": [SignalSource(sheet="AML & Sanctions Risk", question_ids=expand_qids("B1.2"))],
    "sanctions_high_risk_geo_volume": [SignalSource(sheet="AML & Sanctions Risk", question_ids=expand_qids("B2.1"))],
    "sanctions_structural_exposure": [SignalSource(sheet="AML & Sanctions Risk", question_ids=expand_qids("B2.3"))],
    "sanctions_screening_controls": [SignalSource(sheet="AML & Sanctions Risk", question_ids=expand_qids("D1.2"))],
}


def get_sources(signal_name: str) -> List[SignalSource]:
    return SIGNAL_SOURCES.get(signal_name, [])
