# app/listing_requirements.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class ListingRequirementRule:
    id: str
    title: str
    severity: str  # "Informational", "Recommended", or "Required"
    text: str
    conditions: Dict[str, Any]


def _extract_effective_tag_ids(refined_risk_tags: List[Dict[str, Any]]) -> List[str]:
    """
    Take the refined tag objects and return the set of tag_ids that are actually
    included (include == True).
    """
    ids: set[str] = set()
    for t in refined_risk_tags or []:
        if not bool(t.get("include", True)):
            continue
        tag_id = (t.get("id") or "").strip()
        if not tag_id:
            continue
        ids.add(tag_id)
    return sorted(ids)


def _is_real_escalation_flag(flag: Any) -> bool:
    """
    Treat only 'real' escalation flags as triggers for requirement logic.

    This MUST align with what we render as escalation cards in the report; otherwise
    requirement thresholds (e.g. committee sign-off) can trigger off informational /
    'No review' rows.
    """
    s = (str(flag) if flag is not None else "").strip().lower()
    if not s:
        return False

    non_triggers = {
        "no review",
        "no-review",
        "none",
        "n/a",
        "na",
        "informational",
        "info",
        "information only",
        "ok",
        "okay",
        "pass",
    }
    return s not in non_triggers


def _build_context(
    overall_band_numeric: int,
    board_escalations: List[Any] | None,
    refined_risk_tags: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build a simple context object from the high-level risk picture.

    Keys we expose to the rules:
      - tags: set of effective tag_ids
      - overall_band: int (1–5)
      - total_escalations: int   (REAL triggers only; excludes "No review"/info rows)
      - esg_escalations: int     (REAL triggers only)
      - technical_escalations: int
      - governance_escalations: int
      - reg_escalations: int
      - has_speculative_profile: bool (memecoin/“story”/unlock-heavy)
      - has_hard_control: bool (admin keys / upgradeability / smart-contract control)
      - posture: "benign" | "intermediate" | "heightened"
    """
    tags = set(_extract_effective_tag_ids(refined_risk_tags))
    escs = board_escalations or []

    # Count only REAL escalation triggers (aligns with report cards)
    total_escalations = 0
    esg_escalations = 0
    technical_escalations = 0
    governance_escalations = 0
    reg_escalations = 0

    for esc in escs:
        # Support both dataclass-style and dict-style access
        flag = getattr(esc, "flag", None)
        if flag is None and isinstance(esc, dict):
            flag = esc.get("flag")

        if not _is_real_escalation_flag(flag):
            continue

        total_escalations += 1

        domain_name = getattr(esc, "domain_name", None)
        if domain_name is None and isinstance(esc, dict):
            domain_name = esc.get("domain_name")
        domain = (domain_name or "").lower()

        if "strategic" in domain or "esg" in domain or "reputational" in domain:
            esg_escalations += 1
        elif "technical" in domain or "protocol" in domain:
            technical_escalations += 1
        elif "token fundamentals" in domain or "governance" in domain:
            governance_escalations += 1
        elif "regulatory" in domain or "legal" in domain:
            reg_escalations += 1

    # Heuristics for “story / speculative” and “hard control”
    speculative_tags = {
        "memecoin_hype_dependency_risk",
        "memecoin_no_utility_risk",
        "unsustainable_yield_risk",
        "behavioural_risk",
        "insider_unlocks_risk",
    }
    hard_control_tags = {
        "admin_key_centralisation_risk",
        "upgradeability_risk",
        "smart_contract_risk",
        "gov_token_governance_concentration_risk",
    }

    has_speculative_profile = not tags.isdisjoint(speculative_tags)
    has_hard_control = not tags.isdisjoint(hard_control_tags)

    # Simple posture classification
    band = int(overall_band_numeric or 0)
    posture: str
    if (
        band >= 4
        or total_escalations >= 6
        or esg_escalations >= 2
        or (has_speculative_profile and has_hard_control)
    ):
        posture = "heightened"
    elif band >= 3 and (total_escalations >= 3 or has_hard_control):
        posture = "intermediate"
    else:
        posture = "benign"

    return {
        "tags": tags,
        "overall_band": band,
        "total_escalations": total_escalations,
        "esg_escalations": esg_escalations,
        "technical_escalations": technical_escalations,
        "governance_escalations": governance_escalations,
        "reg_escalations": reg_escalations,
        "has_speculative_profile": has_speculative_profile,
        "has_hard_control": has_hard_control,
        "posture": posture,
    }


def _rule_matches(rule: ListingRequirementRule, ctx: Dict[str, Any]) -> bool:
    """
    Supported condition keys:
      - min_overall_band: int
      - max_overall_band: int
      - any_tag: [tag_id, ...]
      - all_tags: [tag_id, ...]
      - min_total_escalations: int
      - min_esg_escalations: int
      - min_posture: "benign" | "intermediate" | "heightened"
      - requires_speculative_profile: bool
      - requires_governance_centralisation: bool
    """
    cond = rule.conditions or {}

    tags: set[str] = ctx["tags"]
    band: int = ctx["overall_band"]
    total_escalations: int = ctx["total_escalations"]
    esg_escalations: int = ctx["esg_escalations"]
    posture: str = ctx["posture"]
    has_speculative_profile: bool = ctx["has_speculative_profile"]
    has_hard_control: bool = ctx["has_hard_control"]

    # Bands
    if "min_overall_band" in cond and band < int(cond["min_overall_band"]):
        return False
    if "max_overall_band" in cond and band > int(cond["max_overall_band"]):
        return False

    # Escalations
    if "min_total_escalations" in cond and total_escalations < int(
        cond["min_total_escalations"]
    ):
        return False
    if "min_esg_escalations" in cond and esg_escalations < int(
        cond["min_esg_escalations"]
    ):
        return False

    # Tags
    any_tag = cond.get("any_tag") or []
    if any_tag and tags.isdisjoint(any_tag):
        return False

    all_tags = cond.get("all_tags") or []
    if all_tags and not set(all_tags).issubset(tags):
        return False

    # Posture
    if "min_posture" in cond:
        order = {"benign": 1, "intermediate": 2, "heightened": 3}
        if order[posture] < order[cond["min_posture"]]:
            return False

    # Speculative profile needed?
    if cond.get("requires_speculative_profile") and not has_speculative_profile:
        return False

    # Strong governance/admin-centralisation profile needed?
    if cond.get("requires_governance_centralisation") and not has_hard_control:
        return False

    return True


# ---------------------------------------------------------------------------
# Rule catalogue
# ---------------------------------------------------------------------------

LISTING_REQUIREMENT_RULES: List[ListingRequirementRule] = [
    # 1) Complex / upgradeable / smart-contract dependent assets
    ListingRequirementRule(
        id="enhanced_structural_monitoring",
        title="Treat this asset as a complex protocol in monitoring",
        severity="Recommended",
        text=(
            "Classify this asset in your higher-complexity protocol tier and ensure it "
            "is included in existing monitoring for major upgrades, security incidents "
            "and governance changes, with clear internal triggers for re-review if a "
            "serious incident occurs."
        ),
        conditions={
            "any_tag": [
                "complex_protocol_design_risk",
                "upgradeability_risk",
                "smart_contract_risk",
                "bridge_dependency_risk",
            ],
            # applies from benign upwards
            "min_posture": "benign",
        },
    ),

    # 2) Treasury / reserve concentration (foundations, company treasuries, etc.)
    ListingRequirementRule(
        id="treasury_concentration_watch",
        title="Watch treasury and reserve activity",
        severity="Recommended",
        text=(
            "Track public disclosures and significant on-chain movements relating to "
            "the project’s treasury or reserves, and treat adverse developments "
            "(for example large unexplained sales or governance controversy) as "
            "triggers for risk re-review."
        ),
        conditions={
            "any_tag": ["treasury_concentration_risk"],
            "min_posture": "benign",
        },
    ),

    # 3) Strong admin-key / governance centralisation – only kicks in once things
    #    look at least 'intermediate' overall.
    ListingRequirementRule(
        id="governance_and_admin_controls",
        title="Document admin-key and governance controls",
        severity="Recommended",
        text=(
            "Maintain a documented internal view of admin-key holders, upgrade "
            "processes and governance controls for this asset, and ensure client "
            "disclosures explain that a small group can materially influence or "
            "interrupt token behaviour."
        ),
        conditions={
            "any_tag": [
                "admin_key_centralisation_risk",
                "gov_token_governance_concentration_risk",
            ],
            "min_posture": "heightened",
            "min_total_escalations": 1,
        },
    ),

    # 4) Speculative / unlock-driven / “story” assets – *only* in heightened posture
    ListingRequirementRule(
        id="speculative_profile_retail_controls",
        title="Tighter guard-rails for speculative profile",
        severity="Required",
        text=(
            "For this asset, apply tighter guard-rails for retail and smaller "
            "institutional clients (for example lower exposure caps, stricter "
            "appropriateness thresholds and clearer front-end warnings) reflecting "
            "its speculative, controversy-prone profile and concentration of control."
        ),
        conditions={
            "requires_speculative_profile": True,
            "min_posture": "heightened",
        },
    ),

    # 5) ESG / reputational – if there are actual ESG domain escalations
    ListingRequirementRule(
        id="esg_reputational_review",
        title="ESG and reputational review before/on listing",
        severity="Required",
        text=(
            "Undertake an ESG and reputational assessment (including political, "
            "governance and sanctions-adjacent issues) and ensure the outcome is "
            "explicitly considered by the appropriate internal committee when "
            "approving, maintaining or suspending listing for this asset."
        ),
        conditions={
            "min_esg_escalations": 1,
            "min_posture": "intermediate",
        },
    ),

    # 6) Many board-level triggers overall → committee visibility is non-optional
    ListingRequirementRule(
        id="committee_signoff_required",
        title="Formal committee sign-off",
        severity="Required",
        text=(
            "Ensure initial listing and any future suspension or delisting decisions "
            "for this asset are approved by an internal committee with full visibility "
            "of the DDQ assessment, board-level escalation points and incident history."
        ),
        conditions={
            "min_total_escalations": 4,
            "min_posture": "intermediate",
        },
    ),

    # 7) General ongoing monitoring for anything not clearly 'Very Low' / 'Low'
    ListingRequirementRule(
        id="scheduled_risk_reassessment",
        title="Scheduled risk reassessment",
        severity="Recommended",
        text=(
            "Schedule periodic reassessment of this asset’s risk profile, including "
            "review of DDQ responses, incidents, regulatory developments and key "
            "on-chain and market metrics, at least annually or after any major event."
        ),
        conditions={
            "min_overall_band": 3,  # Medium or above
        },
    ),
]


def build_listing_requirements(
    overall_band_numeric: int,
    board_escalations: List[Any],
    refined_risk_tags: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Turn tags + escalation picture into concrete listing requirements.

    This is deliberately *conservative* for relatively clean, established assets
    (e.g. AVAX), and more prescriptive for complex, controversy-heavy assets
    (e.g. WLFI).
    """
    ctx = _build_context(overall_band_numeric, board_escalations, refined_risk_tags)

    out: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    for rule in LISTING_REQUIREMENT_RULES:
        if not _rule_matches(rule, ctx):
            continue
        if rule.id in seen_ids:
            continue

        out.append(
            {
                "id": rule.id,
                "title": rule.title,
                "severity": rule.severity,
                "text": rule.text,
            }
        )
        seen_ids.add(rule.id)

    return out


def build_listing_context(
    overall_band_numeric: int,
    board_escalations: List[Any] | None,
    refined_risk_tags: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Public wrapper exposing the derived listing posture context.

    This is useful for other report sections (e.g. token fact sheets and
    executive summaries) so they can stay consistent with the requirement
    engine’s posture/speculative/hard-control logic.
    """
    return _build_context(overall_band_numeric, board_escalations, refined_risk_tags)
