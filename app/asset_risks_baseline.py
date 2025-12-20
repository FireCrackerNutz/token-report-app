# app/asset_risks_baseline.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

from .ddq_signals import get_signal_answer

RiskGroup = Literal[
    "baseline_crypto",
    "defi",
    "memecoin",
    "stablecoin",
    "wrapped",
    "security_token",
    "governance_utility",
    "native_network",
]

DisclosureSection = Literal[
    # Token-type / profile sections (only shown when applicable)
    "native_network",
    "governance_utility",
    "defi",
    "stablecoin",
    "wrapped",
    "security_token",
    "memecoin",
    # Cross-cutting buckets (shown for any token)
    "cross_cutting_governance",
    "cross_cutting_technical",
    "cross_cutting_tokenomics",
    "cross_cutting_market",
    "cross_cutting_disclosure",
    "cross_cutting_regulatory",
    "cross_cutting_fincrime",
    "cross_cutting_other",
]


@dataclass
class BaselineRiskBullet:
    id: str
    group: RiskGroup
    text: str
    tags: List[str]
    conditions: Dict[str, Any]


# ---------------------------------------------------------------------------
# Baseline headings and bullets
# ---------------------------------------------------------------------------

RISK_GROUP_HEADINGS: Dict[RiskGroup, str] = {
    "baseline_crypto": "Cryptoasset risks (baseline)",
    "defi": "DeFi risks",
    "memecoin": "Memecoin risks",
    "stablecoin": "Stablecoin risks",
    "wrapped": "Wrapped token risks",
    "security_token": "Security / tokenised asset risks",
    "governance_utility": "Governance & utility token risks",
    "native_network": "Network & infrastructure risks",
}

BASELINE_BULLETS: List[BaselineRiskBullet] = [
    # =========================
    # Cryptoasset risks (baseline)
    # =========================
    BaselineRiskBullet(
        id="baseline_investment_risk",
        group="baseline_crypto",
        text=(
            "Investment risk: Cryptoassets can be extremely volatile. Prices may fall as quickly "
            "as they rise and you should be prepared to lose all the money you invest."
        ),
        tags=["high_volatility_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="baseline_lack_of_protections",
        group="baseline_crypto",
        text=(
            "Lack of protections: Cryptoassets are typically not covered by the protections that "
            "apply to regulated investments. If something goes wrong, you may have limited recourse."
        ),
        tags=["poor_disclosure_quality_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="baseline_selling_your_investment",
        group="baseline_crypto",
        text=(
            "Selling your investment: You may not always be able to sell your cryptoassets when you want. "
            "Market conditions or operational issues can cause delays, meaning you might not be able to access "
            "your money at the time you need it."
        ),
        tags=["low_liquidity_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="baseline_complexity",
        group="baseline_crypto",
        text=(
            "Cryptoassets are complex: It may not always be clear how a cryptoasset works or what factors "
            "influence its value. Take time to understand what you are buying. If something sounds too good "
            "to be true, it probably is."
        ),
        tags=["complex_protocol_design_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="baseline_scams",
        group="baseline_crypto",
        text=(
            "Scams and cybercrime: Cryptoasset markets attract scammers and cybercriminals. If you fall victim "
            "to a scam or hack, you may be unable to recover your assets."
        ),
        tags=["scams_and_fraud_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="baseline_market_manipulation",
        group="baseline_crypto",
        text=(
            "Market manipulation: Cryptoasset markets can be susceptible to market abuse, including wash trading "
            "and price manipulation. This can affect pricing and your ability to transact at a fair market value."
        ),
        tags=["wash_trading_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="baseline_technology_risk",
        group="baseline_crypto",
        text=(
            "Technology risk: Cryptoassets rely on complex software and networks. Bugs, exploits, or failures in "
            "protocols, smart contracts, or related infrastructure can result in loss of funds or disruption of service."
        ),
        tags=["smart_contract_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="baseline_infrastructure_centralisation",
        group="baseline_crypto",
        text=(
            "Infrastructure centralisation: Some networks depend on a small number of validators, node operators, "
            "or infrastructure providers. Concentration of critical infrastructure can increase the risk of outages, "
            "censorship, or coordinated failures."
        ),
        tags=["infrastructure_centralisation_risk"],
        conditions={"always": True},
    ),
    # =========================
    # Governance & utility token risks
    # =========================
    BaselineRiskBullet(
        id="governance_admin_controls",
        group="governance_utility",
        text=(
            "Governance and privileged controls: If a small group can propose, vote on, or execute changes, the "
            "token’s rules can change in ways that disadvantage holders. Concentrated governance can also undermine "
            "claims of decentralisation."
        ),
        tags=["gov_token_governance_concentration_risk", "governance_concentration_risk"],
        conditions={"token_type": ["governance_utility", "governance", "utility"]},
    ),
    BaselineRiskBullet(
        id="governance_admin_keys",
        group="governance_utility",
        text=(
            "Admin keys and privileged functions: If admins can pause, blacklist, mint, upgrade, or otherwise control "
            "core protocol behaviour, holders face reliance on those controllers acting appropriately and securely."
        ),
        tags=["admin_key_centralisation_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="governance_upgradeability",
        group="governance_utility",
        text=(
            "Upgradeability risk: Upgradeable contracts can change behaviour post-listing. Without robust governance, "
            "timelocks and transparency, upgrades can increase the likelihood of unexpected changes or security incidents."
        ),
        tags=["upgradeability_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="governance_timelock_absence",
        group="governance_utility",
        text=(
            "Timelock absence: Where upgrades or privileged actions can be executed without a meaningful timelock, "
            "users and venues may have limited time to react to high-impact changes."
        ),
        tags=["timelock_absence_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="governance_docs_gaps",
        group="governance_utility",
        text=(
            "Governance documentation gaps: If governance processes, roles or controls are not clearly documented, "
            "it is harder to assess accountability, change-management risk and effective decentralisation."
        ),
        tags=["governance_documentation_gaps_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="governance_dispute_history",
        group="governance_utility",
        text=(
            "Governance dispute history: Prior disputes, contentious votes or emergency interventions can indicate "
            "elevated operational risk, including forks, abrupt changes in protocol parameters, or reputational impacts "
            "that affect market confidence."
        ),
        tags=["governance_dispute_history_risk"],
        conditions={"always": True},
    ),
    # =========================
    # DeFi risks
    # =========================
    BaselineRiskBullet(
        id="defi_smart_contract_risk",
        group="defi",
        text=(
            "Smart contract dependency: DeFi protocols rely on smart contracts that may contain bugs or vulnerabilities. "
            "Exploits can cause rapid losses and may be difficult to reverse."
        ),
        tags=["smart_contract_risk"],
        conditions={"token_type": ["defi"]},
    ),
    BaselineRiskBullet(
        id="defi_oracle_dependency",
        group="defi",
        text=(
            "Oracle dependency: If the protocol relies on price or data oracles, oracle failures or manipulation can "
            "trigger erroneous liquidations, mispricing, or protocol insolvency."
        ),
        tags=["oracle_dependency_risk"],
        conditions={"token_type": ["defi"]},
    ),
    BaselineRiskBullet(
        id="defi_liquidations",
        group="defi",
        text=(
            "Liquidation mechanics risk: Liquidation designs can amplify volatility, particularly during stressed markets. "
            "Poorly designed liquidations can create cascading losses for users."
        ),
        tags=["defi_liquidation_mechanism_risk"],
        conditions={"token_type": ["defi"]},
    ),
    # =========================
    # Stablecoin risks
    # =========================
    BaselineRiskBullet(
        id="stablecoin_reserve_transparency",
        group="stablecoin",
        text=(
            "Reserve transparency: Stable-value claims depend on the quality and transparency of reserves and liabilities. "
            "If reserves are opaque or poorly controlled, stability and redemption expectations may not hold."
        ),
        tags=["stablecoin_reserve_transparency_risk"],
        conditions={"token_type": ["stablecoin"]},
    ),
    # =========================
    # Memecoin risks
    # =========================
    BaselineRiskBullet(
        id="memecoin_no_utility",
        group="memecoin",
        text=(
            "Limited utility risk: Tokens that rely primarily on narrative, attention, or community momentum can face sharp "
            "drawdowns when sentiment changes."
        ),
        tags=["memecoin_no_utility_risk"],
        conditions={"token_type": ["memecoin"]},
    ),
    # =========================
    # Wrapped token risks
    # =========================
    BaselineRiskBullet(
        id="wrapped_custody_dependency",
        group="wrapped",
        text=(
            "Custody / bridge dependency: Wrapped tokens depend on a custodian, bridge, or mint/burn mechanism. Failures in "
            "custody, bridge security, or redemption processes can impair value and redeemability."
        ),
        tags=["bridge_dependency_risk"],
        conditions={"token_type": ["wrapped"]},
    ),
    # =========================
    # Security / tokenised asset risks
    # =========================
    BaselineRiskBullet(
        id="security_token_legal_uncertainty",
        group="security_token",
        text=(
            "Legal and enforceability risk: Tokenised assets can be subject to legal, regulatory, and enforceability risks. "
            "Holders may have limited or uncertain rights in underlying assets depending on structure and jurisdiction."
        ),
        tags=["security_token_legal_uncertainty_risk"],
        conditions={"token_type": ["security_token"]},
    ),
    # =========================
    # Network & infrastructure risks
    # =========================
    BaselineRiskBullet(
        id="network_consensus_risk",
        group="native_network",
        text=(
            "Network and consensus risk: Native networks may face consensus failures, chain reorganisations, validator "
            "concentration, or outages. These can disrupt trading, transfers and downstream protocol activity."
        ),
        tags=["infrastructure_centralisation_risk"],
        conditions={"token_type": ["native_network", "native_l1", "native_l2"]},
    ),
    # =========================
    # Cross-cutting: sanctions / financial crime (disclosed when tags included)
    # =========================
    BaselineRiskBullet(
        id="fincrime_sanctions_exposure",
        group="baseline_crypto",
        text=(
            "Sanctions and high-risk geography exposure: Where a token has meaningful exposure to high-risk jurisdictions "
            "or ecosystems, it may be more likely to attract illicit activity or become subject to enforcement action. "
            "This can create legal, operational and reputational risk for venues and clients."
        ),
        tags=["sanctions_exposure_risk", "high_risk_geography_exposure_risk"],
        conditions={"always": False},
    ),
    BaselineRiskBullet(
        id="fincrime_designated_wallets",
        group="baseline_crypto",
        text=(
            "Designated wallets and counterparties: If the token or associated protocol has interacted with designated "
            "wallets, entities or services, venues may face heightened sanctions compliance risk. Exposure can result in "
            "account restrictions, trading suspensions, or heightened monitoring obligations."
        ),
        tags=["sanctions_designated_wallets_risk"],
        conditions={"always": False},
    ),
    BaselineRiskBullet(
        id="fincrime_sanctions_controls",
        group="baseline_crypto",
        text=(
            "Sanctions controls and screening: Where sanctions screening controls are partial, unclear or absent, the risk "
            "of inadvertent dealings with sanctioned counterparties increases. Venues may need enhanced wallet screening, "
            "transaction monitoring and clear escalation playbooks."
        ),
        tags=["sanctions_screening_controls_risk"],
        conditions={"always": False},
    ),
    BaselineRiskBullet(
        id="fincrime_sanctions_enforcement_watch",
        group="baseline_crypto",
        text=(
            "Sanctions-related enforcement watch: Public allegations or enforcement actions relating to sanctions or "
            "financial crime exposure can materially impact a token’s tradability and the reputational profile of venues "
            "listing it."
        ),
        tags=["sanctions_enforcement_watch_risk"],
        conditions={"always": False},
    ),
]

# ---------------------------------------------------------------------------
# Baseline builder
# ---------------------------------------------------------------------------


def build_baseline_risk_sections(risk_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds the baseline risk disclosure blocks used for generic listing pages / info sheets.

    Always returns the baseline crypto block, plus optional token-type blocks when conditions match.
    """
    token_type = (risk_inputs or {}).get("token_type") or ""
    token_type = str(token_type).strip().lower()

    out: Dict[str, Any] = {"blocks": []}
    by_group: Dict[str, List[str]] = {}

    for b in BASELINE_BULLETS:
        if b.group not in by_group:
            by_group[b.group] = []

        cond = b.conditions or {}
        if cond.get("always"):
            by_group[b.group].append(b.text)
            continue

        allowed = cond.get("token_type") or []
        if allowed and token_type in {str(x).strip().lower() for x in allowed}:
            by_group[b.group].append(b.text)

    for g, items in by_group.items():
        if not items:
            continue
        out["blocks"].append({"group": g, "heading": RISK_GROUP_HEADINGS.get(g, g), "bullets": items})

    return out


# ---------------------------------------------------------------------------
# Asset-specific risks: tag → standard bullet glue + grouping for report
# ---------------------------------------------------------------------------

# Clean section titles (no "Cross-cutting risks — " prefix)
DISCLOSURE_SECTION_TITLES: Dict[str, str] = {
    # Type-specific sections
    "defi": "DeFi protocol risks",
    "memecoin": "Memecoin risks",
    "stablecoin": "Stablecoin risks",
    "wrapped": "Wrapped token risks",
    "security_token": "Security / tokenised asset risks",
    "governance_utility": "Governance & token design risks",
    "native_network": "Network & infrastructure risks",
    # Cross-cutting sections
    "cross_cutting_governance": "Governance & control risks",
    "cross_cutting_technical": "Technical & protocol risks",
    "cross_cutting_tokenomics": "Tokenomics & concentration risks",
    "cross_cutting_market": "Market integrity & liquidity risks",
    "cross_cutting_disclosure": "Disclosure & transparency risks",
    "cross_cutting_regulatory": "Regulatory & legal risks",
    "cross_cutting_fincrime": "Sanctions & financial crime risks",
    "cross_cutting_other": "Additional risks",
}

DISCLOSURE_SECTION_ORDER: List[str] = [
    "native_network",
    "governance_utility",
    "defi",
    "stablecoin",
    "wrapped",
    "security_token",
    "memecoin",
    "cross_cutting_governance",
    "cross_cutting_technical",
    "cross_cutting_tokenomics",
    "cross_cutting_market",
    "cross_cutting_disclosure",
    "cross_cutting_fincrime",
    "cross_cutting_regulatory",
    "cross_cutting_other",
]

# Map each tag to a disclosure section bucket.
TAG_SECTION_MAP: Dict[str, DisclosureSection] = {
    # Governance/control
    "admin_key_centralisation_risk": "cross_cutting_governance",
    "upgradeability_risk": "cross_cutting_governance",
    "timelock_absence_risk": "cross_cutting_governance",
    "gov_token_governance_concentration_risk": "cross_cutting_governance",
    "governance_documentation_gaps_risk": "cross_cutting_governance",
    "governance_dispute_history_risk": "cross_cutting_governance",
    # Technical/protocol
    "smart_contract_risk": "cross_cutting_technical",
    "complex_protocol_design_risk": "cross_cutting_technical",
    "oracle_dependency_risk": "cross_cutting_technical",
    "defi_liquidation_mechanism_risk": "defi",
    # Tokenomics/concentration
    "treasury_concentration_risk": "cross_cutting_tokenomics",
    "tokenomics_concentration_risk": "cross_cutting_tokenomics",
    "insider_unlocks_risk": "cross_cutting_tokenomics",
    "unlock_schedule_uncertainty_risk": "cross_cutting_tokenomics",
    # Market/liquidity
    "low_liquidity_risk": "cross_cutting_market",
    "liquidity_concentration_risk": "cross_cutting_market",
    "wash_trading_risk": "cross_cutting_market",
    # Disclosure
    "poor_disclosure_quality_risk": "cross_cutting_disclosure",
    # Sanctions / financial crime
    "sanctions_exposure_risk": "cross_cutting_fincrime",
    "sanctions_designated_wallets_risk": "cross_cutting_fincrime",
    "sanctions_screening_controls_risk": "cross_cutting_fincrime",
    "sanctions_enforcement_watch_risk": "cross_cutting_fincrime",
    "high_risk_geography_exposure_risk": "cross_cutting_fincrime",
}


def is_type_specific_section(section: str) -> bool:
    return section in {"native_network", "governance_utility", "defi", "stablecoin", "wrapped", "security_token", "memecoin"}


def _find_block_and_text_for_tag(tag_id: str) -> Optional[Dict[str, Any]]:
    """Find the first baseline bullet that supports this tag and return its group+text."""
    for b in BASELINE_BULLETS:
        if tag_id in (b.tags or []):
            return {
                "block_key": b.group,
                "block_heading": RISK_GROUP_HEADINGS.get(b.group, b.group),
                "tag_id": tag_id,
                "text": b.text,
            }
    return None


def build_asset_specific_risks(
    refined_tags: List[Dict[str, Any]],
    parsed_ddq: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Takes refined risk tags from GPT (include=True/False) and returns grouped bullet disclosures:

      [
        {"category": "Governance & control risks", "items": [{"tag_id","reason","text","evidence":[...]}]},
        ...
      ]
    """
    token_type = ""
    if parsed_ddq:
        tt_info = parsed_ddq.get("_token_type_inferred") or {}
        token_type = (tt_info.get("token_type") or "").strip().lower()

    # Evidence produced by deterministic inference (tag -> list of evidence dicts)
    tag_evidence_map: Dict[str, List[Dict[str, Any]]] = {}
    if parsed_ddq:
        tag_evidence_map = (parsed_ddq.get("_tag_evidence") or {})  # type: ignore[assignment]

    # Evidence backfill hints (signal names -> lookups in ddq_question_registry via ddq_signals)
    TAG_EVIDENCE_HINTS: Dict[str, List[str]] = {
        # Governance/control
        "admin_key_centralisation_risk": ["privileged_functions_scope", "privileged_roles_disclosure", "emergency_pause_controls"],
        "upgradeability_risk": ["upgradeability_profile", "timelock_present"],
        "timelock_absence_risk": ["timelock_present"],
        "gov_token_governance_concentration_risk": ["governance_described_in_whitepaper"],
        "governance_documentation_gaps_risk": ["governance_described_in_whitepaper"],
        "governance_dispute_history_risk": ["prior_governance_disputes"],
        # Technical
        "oracle_dependency_risk": ["oracle_reliability"],
        "defi_liquidation_mechanism_risk": ["oracle_reliability"],
        "smart_contract_risk": ["audit_coverage", "audit_recency"],
        "complex_protocol_design_risk": ["oracle_reliability", "privileged_functions_scope"],
        # Market/liquidity
        "low_liquidity_risk": ["exit_feasibility"],
        "liquidity_concentration_risk": ["liquidity_concentration"],
        "wash_trading_risk": ["wash_trading_flags"],
        # Tokenomics
        "treasury_concentration_risk": ["treasury_allocation_pct"],
        "tokenomics_concentration_risk": ["team_allocation_pct", "investor_allocation_pct", "treasury_allocation_pct"],
        "insider_unlocks_risk": ["unlocks_milestone_link", "unlock_next_6m_pct"],
        "unlock_schedule_uncertainty_risk": ["unlock_schedule_disclosed", "unlock_next_6m_pct"],
        # Disclosure
        "poor_disclosure_quality_risk": ["privileged_roles_disclosure", "oracle_reliability", "unlock_next_6m_pct"],
        # Sanctions / financial crime
        "sanctions_designated_wallets_risk": ["sanctions_designated_wallets"],
        "sanctions_enforcement_watch_risk": ["sanctions_enforcement_actions"],
        "sanctions_exposure_risk": ["sanctions_structural_exposure", "sanctions_high_risk_geo_volume"],
        "sanctions_screening_controls_risk": ["sanctions_screening_controls"],
        "high_risk_geography_exposure_risk": ["sanctions_high_risk_geo_volume"],
    }

    def _compact_evidence(tag: str, limit: int = 4) -> List[Dict[str, Any]]:
        raw = tag_evidence_map.get(tag) or []
        compact: List[Dict[str, Any]] = []
        seen: set[Tuple[str, str]] = set()
        for e in raw:
            sheet = (e.get("sheet") or e.get("sheet_name") or "").strip()
            qid = (e.get("question_id") or "").strip()
            key = (sheet, qid)
            if sheet and qid:
                if key in seen:
                    continue
                seen.add(key)
            compact.append(
                {
                    "sheet_name": sheet or None,
                    "question_id": qid or None,
                    "raw_response": e.get("raw_response") or None,
                    "confidence": e.get("confidence") or None,
                    "source_citations": e.get("citations") or e.get("source_citations") or [],
                    "note": e.get("note") or None,
                }
            )
            if len(compact) >= limit:
                break
        return compact

    def _backfill_evidence_for_tag(tag: str, limit: int = 4) -> List[Dict[str, Any]]:
        if not parsed_ddq:
            return []
        hints = TAG_EVIDENCE_HINTS.get(tag, [])
        out: List[Dict[str, Any]] = []
        seen: set[Tuple[str, str]] = set()
        for sig in hints:
            ans = get_signal_answer(parsed_ddq, sig)
            if not ans:
                continue
            sheet = (ans.sheet or "").strip()
            qid = (ans.question_id or "").strip()
            if sheet and qid:
                if (sheet, qid) in seen:
                    continue
                seen.add((sheet, qid))
            out.append(
                {
                    "sheet_name": sheet or None,
                    "question_id": qid or None,
                    "raw_response": ans.raw_response or None,
                    "confidence": ans.confidence or None,
                    "source_citations": ans.citations or [],
                    "note": f"evidence_hint:{sig}",
                }
            )
            if len(out) >= limit:
                break
        return out

    def type_sections_for_token(tt: str) -> set[str]:
        tt = (tt or "").strip().lower()
        if tt == "stablecoin":
            return {"stablecoin"}
        if tt == "defi":
            return {"defi"}
        if tt == "memecoin":
            return {"memecoin"}
        if tt == "wrapped":
            return {"wrapped"}
        if tt == "security_token":
            return {"security_token"}
        if tt in {"native_l1", "native_l2"}:
            return {"native_network"}
        if tt in {"governance", "utility", "governance_utility"}:
            return {"governance_utility"}
        return set()

    allowed_type_sections = type_sections_for_token(token_type)

    # Filter to included tags only
    active_tag_ids: List[str] = []
    reasons_by_tag: Dict[str, str] = {}
    for t in refined_tags or []:
        tag_id = (t.get("id") or "").strip()
        if not tag_id:
            continue
        if not bool(t.get("include", True)):
            continue
        active_tag_ids.append(tag_id)
        reasons_by_tag[tag_id] = (t.get("reason") or "").strip()

    if not active_tag_ids:
        return []

    # Group bullets by disclosure sections
    grouped: Dict[str, Dict[str, Any]] = {}

    for tag_id in active_tag_ids:
        entry = _find_block_and_text_for_tag(tag_id)
        if not entry:
            continue

        # Pick a section bucket (type-specific OR cross-cutting)
        preferred_section = TAG_SECTION_MAP.get(tag_id, "cross_cutting_other")
        section = preferred_section

        # Governance/utility tokens: prefer the dedicated "Governance & token design" section
        # rather than leaving governance/control items only in cross-cutting buckets.
        if token_type in {"governance", "utility", "governance_utility"} and section == "cross_cutting_governance":
            section = "governance_utility"

        # Enforce "only show type-specific headings that match this token".
        if is_type_specific_section(section) and section not in allowed_type_sections:
            # Route mismatched type-specific tags into cross-cutting buckets.
            if section in {"defi", "stablecoin", "wrapped", "security_token"}:
                section = "cross_cutting_technical"
            elif section == "memecoin":
                section = "cross_cutting_market"
            else:
                section = "cross_cutting_other"

        # Also allow governance_utility section only for governance/utility tokens.
        if section == "governance_utility" and section not in allowed_type_sections:
            section = "cross_cutting_governance"

        title = DISCLOSURE_SECTION_TITLES.get(section, section)
        block = grouped.setdefault(section, {"category": title, "items": []})
        block["items"].append(
            {
                "tag_id": tag_id,
                "reason": reasons_by_tag.get(tag_id, ""),
                "text": entry["text"],
                "evidence": (_compact_evidence(tag_id) or _backfill_evidence_for_tag(tag_id)),
            }
        )

    # Stable order: use DISCLOSURE_SECTION_ORDER
    ordered: List[Dict[str, Any]] = []
    for sec in DISCLOSURE_SECTION_ORDER:
        if sec in grouped and grouped[sec].get("items"):
            ordered.append(grouped[sec])

    # Append any unrecognised sections (should be rare)
    for sec, block in grouped.items():
        if sec not in DISCLOSURE_SECTION_ORDER and block.get("items"):
            ordered.append(block)

    return ordered
