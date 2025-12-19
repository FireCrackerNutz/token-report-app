from __future__ import annotations

from typing import Any, Dict, List, Set

from .models import DomainStats, BoardEscalation


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


def _is_real_board_trigger(flag: str | None) -> bool:
    if flag is None:
        return False
    f = flag.strip().lower()
    if f in _NON_ESCALATION_FLAGS:
        return False
    return any(k in f for k in _REAL_ESCALATION_KEYWORDS)


def infer_risk_tags_from_ddq(parsed_ddq: Dict[str, Any]) -> List[str]:
    """
    Very conservative v1:
    - Only infer tags from *real* board-escalation flags.
    - No 'domain band >= 4' heuristics.
    - Anything tagged here should represent a genuine, outsized risk.
    """
    domain_stats: List[DomainStats] = parsed_ddq.get("domain_stats", [])
    board_escalations: List[BoardEscalation] = parsed_ddq.get("board_escalations", [])

    tags: Set[str] = set()

    def is_real_trigger(flag: str | None) -> bool:
        if not flag:
            return False
        f = flag.strip().lower()
        if f in {"", "no", "false", "0", "no review"}:
            return False
        return any(k in f for k in ["review required", "board", "escalat", "listing committee", "reject"])

    for esc in board_escalations:
        if not is_real_trigger(esc.flag):
            continue

        qid = (esc.question_id or "").strip()
        dom = (esc.domain_name or "").lower()

        # --- Technical & Protocol Security --------------------------------
        if "technical" in dom or "protocol" in dom:
            # Bridge / cross-chain dependency
            if qid.startswith("B2."):
                tags.add("bridge_dependency_risk")

            # Privileged roles / admin key concentration
            if qid.startswith("C1.") or qid.startswith("C2.") or qid.startswith("C3."):
                tags.add("admin_key_centralisation_risk")

            # Architectural complexity / tricky design
            if qid.startswith("B1."):
                tags.add("complex_protocol_design_risk")

        # --- Market & Liquidity Integrity ---------------------------------
        if "market" in dom or "liquidity" in dom:
            # Depth / fragmentation / exit feasibility issues
            if qid.startswith("A1.") or qid.startswith("A2."):
                tags.add("low_liquidity_risk")

            # Volatility / drawdown questions
            if qid.startswith("D1.") or qid.startswith("D2."):
                tags.add("high_volatility_risk")

        # --- Strategic, Reputational & ESG --------------------------------
        if "strategic" in dom or "reputational" in dom or "esg" in dom:
            # Big treasury / foundation / insider concentration concerns
            if qid.startswith("B2."):
                tags.add("treasury_concentration_risk")

    # Return deterministic ordering
    return sorted(tags)