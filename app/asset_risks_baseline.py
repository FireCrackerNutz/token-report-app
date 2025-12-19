# app/asset_risks_baseline.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Literal, Optional 

RiskGroup = Literal[
    "baseline_crypto",
    "defi",
    "memecoin",
    "stablecoin",
    "wrapped",
    "security_token",
    "governance_utility",
]


@dataclass
class BaselineRiskBullet:
    id: str                   # e.g. "baseline_investment_risk"
    text: str                 # final wording for the bullet (static)
    tags: List[str]           # e.g. ["high_volatility_risk"]
    group: RiskGroup          # which heading it lives under
    conditions: Dict[str, Any]  # simple rule for when this bullet applies


RISK_GROUP_HEADINGS: Dict[RiskGroup, str] = {
    "baseline_crypto": "Cryptoasset risks (baseline)",
    "defi": "DeFi risks",
    "memecoin": "Memecoin risks",
    "stablecoin": "Stablecoin risks",
    "wrapped": "Wrapped token risks",
    "security_token": "Security token risks",
    "governance_utility": "Governance & utility token risks",
}


BASELINE_BULLETS: List[BaselineRiskBullet] = [
    # =========================
    # Cryptoasset Risks (Baseline)
    # =========================
    BaselineRiskBullet(
        id="baseline_investment_risk",
        group="baseline_crypto",
        text=(
            "Investment risk: The value of cryptoassets can be extremely volatile. "
            "Prices may fall just as quickly as they rise, and you should be prepared "
            "to lose all the money you invest."
        ),
        tags=["high_volatility_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="baseline_lack_of_protections",
        group="baseline_crypto",
        text=(
            "Lack of protections: Cryptoassets are largely unregulated. This means you "
            "will not be protected by the Financial Services Compensation Scheme (FSCS) "
            "or the Financial Ombudsman Service (FOS) if something goes wrong with "
            "your investment."
        ),
        tags=["poor_disclosure_quality_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="baseline_selling_your_investment",
        group="baseline_crypto",
        text=(
            "Selling your investment: You may not always be able to sell your "
            "cryptoassets when you want. Market conditions or operational issues "
            "(like outages or cyber-attacks) can cause delays, meaning you might "
            "not be able to access your money at the time you need it."
        ),
        tags=["low_liquidity_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="baseline_complexity",
        group="baseline_crypto",
        text=(
            "Cryptoassets are complex: It may not always be clear how a cryptoasset "
            "works or what factors influence its value. Take time to research and "
            "understand what you’re investing in. If something sounds too good to be "
            "true, it probably is."
        ),
        tags=["complex_protocol_design_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
        id="baseline_concentration",
        group="baseline_crypto",
        text=(
            "Don't put all your eggs in one basket: Putting all your money in a single "
            "type of investment is risky. It is good practise not to invest more than "
            "10% of all your money in high risk investments such as crypto assets."
        ),
        tags=["concentration_risk"],
        conditions={"always": True},
    ),
    BaselineRiskBullet(
    id="baseline_infrastructure_centralisation",
    group="baseline_crypto",
    text=(
        "Infrastructure and outage risk: Many crypto networks rely on a small number "
        "of core developers, clients or infrastructure providers. Incidents, bugs or "
        "co-ordinated upgrades affecting these parties can disrupt trading or transfers."
    ),
    tags=["infrastructure_centralisation_risk"],
    conditions={"always": True},
    ),


    # =========================
    # DeFi Risks
    # =========================
    BaselineRiskBullet(
        id="defi_smart_contract_risk",
        group="defi",
        text=(
            "Smart contract risk: DeFi relies on smart contracts. Even small coding "
            "errors or bugs can lead to exploits, potentially resulting in significant "
            "financial loss."
        ),
        tags=["smart_contract_risk", "defi_rug_pull_exit_risk"],
        conditions={"token_type": ["defi"]},
    ),
    BaselineRiskBullet(
        id="defi_regulatory_risk",
        group="defi",
        text=(
            "Regulatory risk: DeFi protocols often operate without intermediaries or "
            "standard compliance controls. Future regulation could affect the "
            "legality, availability, or value of DeFi tokens."
        ),
        tags=["regulatory_risk"],
        conditions={"token_type": ["defi"]},
    ),
    BaselineRiskBullet(
        id="defi_rug_pull_risk",
        group="defi",
        text=(
            "Rug pulls and exit scams: Some DeFi projects are launched by anonymous "
            "teams. This increases the risk of developers abandoning the project and "
            "removing liquidity, leaving investors with worthless tokens."
        ),
        tags=["defi_rug_pull_exit_risk"],
        conditions={"token_type": ["defi"]},
    ),
    BaselineRiskBullet(
        id="defi_oracle_risk",
        group="defi",
        text=(
            "Data/oracle risk: DeFi platforms depend on external data sources "
            "(oracles) for pricing and execution. If these are manipulated or "
            "inaccurate, it can lead to losses."
        ),
        tags=["oracle_dependency_risk"],
        conditions={"token_type": ["defi"]},
    ),
    BaselineRiskBullet(
        id="defi_protocol_complexity",
        group="defi",
        text=(
            "Protocol complexity: Many DeFi systems are difficult to understand, even "
            "for experienced investors. You should not invest unless you fully "
            "understand how the protocol works and the risks involved."
        ),
        tags=["complex_protocol_design_risk"],
        conditions={"token_type": ["defi"]},
    ),

    # =========================
    # Memecoin Risks
    # =========================
    BaselineRiskBullet(
        id="memecoin_volatility",
        group="memecoin",
        text=(
            "Volatility risk: Memecoins often experience extreme and unpredictable "
            "price swings, heavily influenced by social media trends, celebrity "
            "endorsements, and market hype. You should be prepared to lose all the "
            "money you invest."
        ),
        tags=["high_volatility_risk", "memecoin_hype_dependency_risk"],
        conditions={"token_type": ["memecoin"]},
    ),
    BaselineRiskBullet(
        id="memecoin_lack_of_utility",
        group="memecoin",
        text=(
            "Lack of utility: Meme coins often lack intrinsic value and utility, "
            "relying on community interest and online trends."
        ),
        tags=["memecoin_no_utility_risk"],
        conditions={"token_type": ["memecoin"]},
    ),
    BaselineRiskBullet(
        id="memecoin_market_manipulation",
        group="memecoin",
        text=(
            "Market manipulation: Meme coins are susceptible to market manipulation, "
            "including \"pump-and-dump\" schemes. It is important to be aware of "
            "concentrated ownership, low liquidity, and lack of oversight."
        ),
        tags=["whale_concentration_risk", "thin_market_venue_risk"],
        conditions={"token_type": ["memecoin"]},
    ),
    BaselineRiskBullet(
        id="memecoin_community_risks",
        group="memecoin",
        text=(
            "Community-driven risks: These tokens typically rely on community "
            "participation without formal governance structures. If interest fades or "
            "a few holders dominate the conversation, the token’s value may drop sharply."
        ),
        tags=["governance_concentration_risk", "memecoin_hype_dependency_risk"],
        conditions={"token_type": ["memecoin"]},
    ),
    BaselineRiskBullet(
        id="memecoin_emotional_investing",
        group="memecoin",
        text=(
            "Emotional investing: Memecoins attract strong emotional responses and "
            "viral excitement, which can lead to impulsive or irrational investment "
            "decisions and increased risk of loss."
        ),
        tags=["behavioural_risk"],
        conditions={"token_type": ["memecoin"]},
    ),
    BaselineRiskBullet(
        id="memecoin_lack_of_transparency",
        group="memecoin",
        text=(
            "Lack of transparency: Many memecoins are launched with minimal project "
            "documentation or unknown teams, making it difficult to assess "
            "credibility or future plans."
        ),
        tags=["poor_disclosure_quality_risk"],
        conditions={"token_type": ["memecoin"]},
    ),
    BaselineRiskBullet(
        id="memecoin_governance_risks",
        group="memecoin",
        text=(
            "Governance risks: If token holders are given voting power, decisions may "
            "be influenced by users with short-term interests or low experience, "
            "increasing risk to the protocol and token value."
        ),
        tags=["gov_token_governance_concentration_risk"],
        conditions={"token_type": ["memecoin"]},
    ),

    # =========================
    # Stablecoin Risks
    # =========================
    BaselineRiskBullet(
        id="stablecoin_counterparty_risk",
        group="stablecoin",
        text=(
            "Counterparty risk: If the stablecoin is backed by reserves, a third party "
            "is typically responsible for holding and managing those assets. If that "
            "party fails, becomes insolvent, or does not maintain the reserves properly, "
            "the stablecoin’s value could be affected."
        ),
        tags=["stablecoin_counterparty_risk"],
        conditions={"token_type": ["stablecoin_fiat", "stablecoin_algorithmic"]},
    ),
    BaselineRiskBullet(
        id="stablecoin_redemption_risk",
        group="stablecoin",
        text=(
            "Redemption risk: The ability to redeem an asset for its underlying "
            "collateral may not function as expected, especially during market "
            "volatility or network issues."
        ),
        tags=["stablecoin_redemption_risk"],
        conditions={"token_type": ["stablecoin_fiat", "stablecoin_algorithmic"]},
    ),
    BaselineRiskBullet(
        id="stablecoin_collateral_risk",
        group="stablecoin",
        text=(
            "Collateral risk: Some stablecoins are backed by other cryptoassets. If "
            "the value of the collateral falls significantly, this can destabilise the "
            "token and put holders at risk of loss."
        ),
        tags=["stablecoin_collateral_opacity_risk"],
        conditions={"token_type": ["stablecoin_fiat", "stablecoin_algorithmic"]},
    ),
    BaselineRiskBullet(
        id="stablecoin_fx_risk",
        group="stablecoin",
        text=(
            "Foreign exchange (FX) risk: Many stablecoins are pegged to fiat currencies "
            "(e.g., US Dollars), exposing you to movements in fiat exchange rates."
        ),
        tags=["stablecoin_fx_risk"],
        conditions={"token_type": ["stablecoin_fiat", "stablecoin_algorithmic"]},
    ),
    BaselineRiskBullet(
        id="stablecoin_algorithmic_risk",
        group="stablecoin",
        text=(
            "Algorithmic risk: Stablecoins that rely on algorithms or smart contracts "
            "to maintain their peg can fail due to flawed design, poor execution, or "
            "external market shocks. This may lead to a loss of value or stability."
        ),
        tags=["stablecoin_algorithmic_risk"],
        conditions={"token_type": ["stablecoin_algorithmic"]},
    ),

    # =========================
    # Wrapped Token Risks
    # =========================
    BaselineRiskBullet(
        id="wrapped_smart_contract_risk",
        group="wrapped",
        text=(
            "Smart contract risk: Wrapped tokens depend on smart contracts to maintain "
            "their link to the underlying asset. If the contract contains bugs or is "
            "exploited, the wrapped token may lose its intended value or function."
        ),
        tags=["smart_contract_risk", "wrapped_collateral_risk"],
        conditions={"token_type": ["wrapped"]},
    ),
    BaselineRiskBullet(
        id="wrapped_collateral_risk",
        group="wrapped",
        text=(
            "Collateral risk: The value of a wrapped token is typically backed by an "
            "equivalent amount of the underlying asset. If the mechanisms ensuring this "
            "collateralization fail, the wrapped token's value might not be preserved."
        ),
        tags=["wrapped_collateral_risk"],
        conditions={"token_type": ["wrapped"]},
    ),
    BaselineRiskBullet(
        id="wrapped_custodial_risk",
        group="wrapped",
        text=(
            "Custodial risk: Many wrapped tokens rely on a third-party custodian to hold "
            "the original asset. If this custodian is hacked, becomes insolvent, or "
            "loses access to the funds, the wrapped token may no longer be redeemable."
        ),
        tags=["wrapped_custody_risk"],
        conditions={"token_type": ["wrapped"]},
    ),
    BaselineRiskBullet(
        id="wrapped_bridging_risk",
        group="wrapped",
        text=(
            "Bridging risk: Wrapped tokens are often created through cross-chain bridges. "
            "These bridges can be vulnerable to technical failures or attacks, which could "
            "delay or prevent transfers and compromise token usability."
        ),
        tags=["bridge_dependency_risk"],
        conditions={"token_type": ["wrapped"]},
    ),
    BaselineRiskBullet(
        id="wrapped_price_divergence_risk",
        group="wrapped",
        text=(
            "Price divergence risk: Although designed to mirror the value of the original "
            "asset, the wrapped token may trade at a premium or discount due to market "
            "imbalances, liquidity issues, or trust in the wrapping process."
        ),
        tags=["wrapped_price_divergence_risk"],
        conditions={"token_type": ["wrapped"]},
    ),

    # =========================
    # Security Token Risks
    # =========================
    BaselineRiskBullet(
        id="security_token_regulatory_risk",
        group="security_token",
        text=(
            "Regulatory risk: Security tokens may fall under financial regulations. "
            "Offering, holding, or trading them without proper authorisation or in "
            "non-compliant environments may be unlawful, and could lead to loss of "
            "access or legal consequences."
        ),
        tags=["regulatory_risk"],
        conditions={"token_type": ["security_token"]},
    ),
    BaselineRiskBullet(
        id="security_token_issuer_risk",
        group="security_token",
        text=(
            "Issuer risk: The value of a security token is typically tied to a specific "
            "company, project, or asset. If the issuer underperforms, becomes insolvent, "
            "or fails to meet its obligations, the token’s value may drop significantly "
            "or become worthless."
        ),
        tags=["security_token_issuer_default_risk"],
        conditions={"token_type": ["security_token"]},
    ),
    BaselineRiskBullet(
        id="security_token_liquidity_risk",
        group="security_token",
        text=(
            "Liquidity risk: Security tokens often trade on a limited number of platforms. "
            "This can make it difficult to sell your tokens or access fair pricing, "
            "especially during periods of market stress."
        ),
        tags=["low_liquidity_risk"],
        conditions={"token_type": ["security_token"]},
    ),
    BaselineRiskBullet(
        id="security_token_legal_complexity",
        group="security_token",
        text=(
            "Legal complexity: Rights attached to security tokens (such as voting or "
            "dividend entitlements) may be hard to enforce, particularly if the issuer "
            "operates in a different legal jurisdiction."
        ),
        tags=["claims_hierarchy_uncertainty_risk"],
        conditions={"token_type": ["security_token"]},
    ),
    BaselineRiskBullet(
        id="security_token_custody_transfer",
        group="security_token",
        text=(
            "Custody and transferability risk: Security tokens may require specific "
            "custody solutions and may not be supported across all wallets or exchanges. "
            "Transfers may also be subject to regulatory restrictions, limiting how or "
            "where you can trade them."
        ),
        tags=["custody_risk"],
        conditions={"token_type": ["security_token"]},
    ),

    # =========================
    # Governance & Utility Token Risks
    # =========================
    BaselineRiskBullet(
        id="gov_utility_project_dependency",
        group="governance_utility",
        text=(
            "Project dependency: These tokens are closely tied to the ongoing development "
            "and success of a specific platform or protocol. If the project is abandoned "
            "or fails to attract users, the token may lose all value."
        ),
        tags=["project_dependency_risk"],
        conditions={"token_type": ["governance_utility", "governance", "utility", "native_l1", "native_l2"]},
    ),
    BaselineRiskBullet(
        id="gov_utility_governance_concentration",
        group="governance_utility",
        text=(
            "Governance concentration: While governance tokens aim to support "
            "decentralised decision-making, voting rights may be concentrated in the "
            "hands of a few large holders or insiders, undermining community control."
        ),
        tags=["gov_token_governance_concentration_risk"],
        conditions={"token_type": ["governance_utility", "governance", "utility", "native_l1", "native_l2"]},
    ),
    BaselineRiskBullet(
        id="gov_utility_volatility_risk",
        group="governance_utility",
        text=(
            "Volatility risk: Even if designed for use within a platform, governance and "
            "utility tokens can still be highly volatile, with prices driven by "
            "speculation rather than usage or fundamentals."
        ),
        tags=["high_volatility_risk"],
        conditions={"token_type": ["governance_utility", "governance", "utility", "native_l1", "native_l2"]},
    ),
    BaselineRiskBullet(
        id="gov_utility_functionality_risk",
        group="governance_utility",
        text=(
            "Functionality risk: Some utility tokens may have limited or no actual use "
            "beyond speculation. Promised features or applications may never be "
            "delivered or may be discontinued."
        ),
        tags=["memecoin_no_utility_risk"],
        conditions={"token_type": ["governance_utility", "governance", "utility", "native_l1", "native_l2"]},
    ),
    BaselineRiskBullet(
        id="gov_utility_regulatory_uncertainty",
        group="governance_utility",
        text=(
            "Regulatory uncertainty: Some tokens marketed as “utility” may later be "
            "reclassified as securities depending on how they function and are used. "
            "This could impact how they are offered, traded, or regulated in the future."
        ),
        tags=["regulatory_risk"],
        conditions={"token_type": ["governance_utility", "governance", "utility", "native_l1", "native_l2"]},
    ),
    BaselineRiskBullet(
    id="governance_treasury_concentration",
    group="governance_utility",
    text=(
        "Treasury concentration risk: Control over large pools of tokens or reserves "
        "may sit with a small group (such as a foundation or core team). Decisions "
        "about how these funds are used can materially affect the token’s price, "
        "liquidity and perceived fairness."
    ),
    tags=["treasury_concentration_risk"],
    conditions={"always": True},
    ),
]


def _conditions_match(bullet: BaselineRiskBullet, risk_inputs: Dict[str, Any]) -> bool:
    cond = bullet.conditions or {}
    if cond.get("always"):
        return True

    token_type = risk_inputs.get("token_type")
    if "token_type" in cond:
        allowed = cond["token_type"]
        if token_type not in allowed:
            return False

    required_tags = cond.get("requires_tag") or []
    have_tags = set(risk_inputs.get("inferred_tags") or [])
    if required_tags and not have_tags.issuperset(required_tags):
        return False

    return True


def build_baseline_risk_sections(risk_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    risk_inputs:
      - token_type: str  (e.g. 'stablecoin_fiat', 'defi', 'wrapped', 'memecoin', 'governance_utility', 'security_token')
      - inferred_tags: List[str] (optional, from DDQ tag engine later)

    Returns:
      {
        "baseline_crypto_risks": { "heading": ..., "bullets": [...] },
        "category_risks": [ { "group": ..., "heading": ..., "bullets": [...] }, ... ]
      }
    """
    grouped: Dict[RiskGroup, List[BaselineRiskBullet]] = {
        "baseline_crypto": [],
        "defi": [],
        "memecoin": [],
        "stablecoin": [],
        "wrapped": [],
        "security_token": [],
        "governance_utility": [],
    }

    for bullet in BASELINE_BULLETS:
        if _conditions_match(bullet, risk_inputs):
            grouped[bullet.group].append(bullet)

    baseline_section = {
        "heading": RISK_GROUP_HEADINGS["baseline_crypto"],
        "bullets": [
            {"id": b.id, "text": b.text, "tags": b.tags}
            for b in grouped["baseline_crypto"]
        ],
    }

    category_sections = []
    for group, bullets in grouped.items():
        if group == "baseline_crypto":
            continue
        if not bullets:
            continue
        category_sections.append({
            "group": group,
            "heading": RISK_GROUP_HEADINGS[group],
            "bullets": [
                {"id": b.id, "text": b.text, "tags": b.tags}
                for b in bullets
            ],
        })

    return {
        "baseline_crypto_risks": baseline_section,
        "category_risks": category_sections,
    }


# ---------------------------------------------------------------------------
# Tag → wording glue + snapshot helper
# ---------------------------------------------------------------------------

from typing import Any, Dict, List, Optional


def _find_block_and_text_for_tag(tag_id: str) -> Optional[Dict[str, Any]]:
    """
    Look through BASELINE_BULLETS and find the first bullet whose tags include this tag_id.

    Returns:
      {
        "block_key": <group key>,
        "block_heading": <human heading>,
        "tag_id": <the tag we matched>,
        "text": <FCA-style bullet text from the template>
      }
    or None if not found.
    """
    for bullet in BASELINE_BULLETS:
        if tag_id in (bullet.tags or []):
            block_key = bullet.group
            block_heading = RISK_GROUP_HEADINGS.get(bullet.group, bullet.group)

            return {
                "block_key": block_key,
                "block_heading": block_heading,
                "tag_id": tag_id,
                "text": bullet.text,
            }

    return None


def build_asset_specific_risks(
    refined_tags: List[Dict[str, Any]],
    parsed_ddq: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """
    Turn refined risk tags into structured asset-specific risks for the snapshot.

    Input:
      - refined_tags: list of {"id": tag_id, "include": bool, "reason": "..."}
      - parsed_ddq: currently unused, but we keep the parameter so we can
        later add light GPT tailoring if we want (e.g. tweak wording slightly).

    Output (example):
      [
        {
          "category": "Governance & control risks",
          "items": [
            {
              "tag_id": "admin_key_centralisation_risk",
              "reason": "short internal explanation from refiner",
              "text": "FCA-style bullet from the template..."
            },
            ...
          ],
        },
        ...
      ]
    """
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

    # Group bullets by block
    grouped: Dict[str, Dict[str, Any]] = {}

    for tag_id in active_tag_ids:
        entry = _find_block_and_text_for_tag(tag_id)
        if not entry:
            # No baseline wording for this tag → silently skip for now
            continue

        block_key = entry["block_key"]
        block_heading = entry["block_heading"]
        text = entry["text"]

        block = grouped.setdefault(
            block_key,
            {
                "category": block_heading,
                "items": [],
            },
        )

        block["items"].append(
            {
                "tag_id": tag_id,
                "reason": reasons_by_tag.get(tag_id, ""),
                "text": text,
            }
        )

    # Return as a list in a stable order
    return list(grouped.values())
