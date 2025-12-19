from __future__ import annotations

import json
import os
from typing import Any, Dict, List

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

from .models import DomainStats, BoardEscalation

# Lazily-created shared client
_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if OpenAI is None:
            raise RuntimeError(
                "openai package is not installed. Install 'openai' to enable GPT features."
            )
        _client = OpenAI()  # uses OPENAI_API_KEY from env
    return _client


# Default model for domain findings (override via env if you want)
# e.g. OPENAI_DOMAIN_MODEL=gpt-5.2 for max quality, or leave as gpt-5-mini
DEFAULT_DOMAIN_MODEL = os.getenv("OPENAI_DOMAIN_MODEL", "gpt-5-mini")

# Safety limits so we don't over-stuff the prompt
MAX_CONTEXT_ITEMS_PER_DOMAIN = 14
MAX_NARRATIVE_CHARS = 700


def _build_domain_context(
    domain: DomainStats,
    escalations: List[BoardEscalation],
) -> Dict[str, Any]:
    """
    Build a compact JSON payload for one domain, using ALL narrative rows
    for that domain as context (not just Review Required ones).
    """
    items: List[Dict[str, Any]] = []

    for e in escalations:
        if not e.raw_narrative:
            continue

        items.append(
            {
                "question_id": e.question_id,
                "question_text": e.question_text,
                "flag": e.flag,  # "Review Required" / "No Review"
                "trigger_rule": e.trigger_rule,
                "staleness_class": e.staleness_class,
                # Trim each narrative so a few long answers don't blow up context
                "narrative": (e.raw_narrative or "")[:MAX_NARRATIVE_CHARS],
                "has_citations": bool(e.citations),
            }
        )

        if len(items) >= MAX_CONTEXT_ITEMS_PER_DOMAIN:
            break

    return {
        "domain": {
            "code": domain.code,
            "name": domain.name,
            "band_name": domain.band_name,        # Very Low / Low / Medium / Medium-High / High
            "band_numeric": domain.band_numeric,  # numeric band index
            "avg_score": domain.avg_score,
            "has_board_escalation": domain.has_board_escalation,
            "board_escalation_count": domain.board_escalation_count,
        },
        "items": items,
    }


def generate_domain_findings_via_gpt(
    domain: DomainStats,
    escalations: List[BoardEscalation],
    model: str | None = None,
) -> Dict[str, Any]:
    """
    Call GPT to generate domain findings for a single domain.

    Input:
      - domain: DomainStats
      - escalations: ALL question-level “escalation rows” for that domain
                     (including ones with flag == "No Review")

    Returns a dict with:
      {
        "one_line": str,
        "strengths": [str, ...],
        "risks": [str, ...],
        "watchpoints": [str, ...]
      }
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set; cannot call OpenAI API.")

    client = get_client()
    model_name = model or DEFAULT_DOMAIN_MODEL

    payload = _build_domain_context(domain, escalations)
    payload_json = json.dumps(payload, ensure_ascii=False)

    prompt = (
        "You are a senior cryptoasset risk analyst preparing domain-level findings "
        "for clients who operate in regulated environments (e.g. exchanges, brokers, custodians, "
        "compliance advisers).\n\n"
        "You are given JSON describing one risk domain and several question-level narratives.\n"
        "Use ALL narratives as context, but treat questions flagged 'Review Required' as higher-salience.\n\n"
        "JSON INPUT:\n"
        f"{payload_json}\n\n"
        "Your job is to help the CLIENT FIRM make realistic listing, onboarding and monitoring decisions. "
        "You must ONLY recommend actions that the CLIENT FIRM itself can take unilaterally "
        "(e.g. disclosures, internal controls, limits, monitoring, governance, suitability/appropriateness), "
        "NOT actions that require the issuer/protocol/foundation to change behaviour, marketing, tokenomics "
        "or documentation.\n\n"
        "Produce STRICT JSON with this shape:\n"
        "{\n"
        '  \"one_line\": \"<<= 35 words>\",\n'
        '  \"strengths\": [\"...\"],\n'
        '  \"risks\": [\"...\"],\n'
        '  \"watchpoints\": [\"...\"]\n'
        "}\n\n"
        "Field semantics:\n"
        "- one_line: Board-level summary of this domain for this token, neutral UK-style English, <= 35 words.\n"
        "- strengths: Structural positives or mitigants relevant to a CLIENT FIRM's decision "
        "(e.g. decentralisation, depth/liquidity, clear documentation, reputable audits). "
        "If none are clear, use an empty list.\n"
        "- risks: Key domain risks that a listing/onboarding committee should consider when deciding WHETHER and HOW "
        "to offer the asset (e.g. need for higher risk classification, tighter limits, enhanced checks, stronger "
        "disclosures). Describe the risk, not a remediation plan for the issuer.\n"
        "- watchpoints: Forward-looking monitoring items and internal ‘re-review triggers’ ONLY for the CLIENT FIRM. "
        "These might be metrics (TVL, volumes, governance events, incidents) or qualitative developments. "
        "Do NOT tell the issuer/protocol to do anything; phrase watchpoints as what the CLIENT FIRM should "
        "monitor, revisit or escalate.\n\n"
        "Hard constraints:\n"
        "- Do NOT instruct or suggest that the protocol/issuer/foundation must change its website, marketing, "
        "documentation, tokenomics or governance. If improvements would be desirable, frame them as how the "
        "CLIENT FIRM should treat or describe the asset (e.g. disclosures, limits, risk tiering).\n"
        "- Do NOT phrase bullets as direct instructions to the protocol team. Only describe actions, controls or "
        "monitoring that sit within the CLIENT FIRM’s own remit.\n"
        "- Do not invent facts that contradict or materially go beyond the narratives.\n"
        "- Each bullet must be <= 40 words.\n"
        "- Output JSON only, no extra commentary."
    )


    # NOTE: no temperature, no response_format – your model rejects those.
    resp = client.responses.create(
        model=model_name,
        input=prompt,
    )

    # Prefer the SDK helper if available
    raw_text = getattr(resp, "output_text", None)

    if raw_text is None:
        # Fallback to first output chunk
        try:
            first_output = resp.output[0]
            if hasattr(first_output, "content") and first_output.content:
                part = first_output.content[0]
                raw_text = getattr(part, "text", str(part))
            else:
                raw_text = str(first_output)
        except Exception:
            # Last-ditch: serialize the whole response
            raw_text = str(resp)

    # Parse JSON; if the model wrapped it, strip around outer braces
    raw_text = raw_text.strip()
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(raw_text[start : end + 1])
        else:
            raise RuntimeError(
                f"Failed to parse GPT JSON for domain {domain.name}: {raw_text!r}"
            )

    # Basic sanity check
    for key in ("one_line", "strengths", "risks", "watchpoints"):
        if key not in data:
            raise RuntimeError(f"Missing key '{key}' in GPT output for domain {domain.name}")

    return data



# ---------------------------------------------------------------------------
# Risk tag refiner (DDQ → base tags → GPT-refined tags)
# ---------------------------------------------------------------------------

import json
import os
from typing import Any, Dict, List


def refine_risk_tags_via_gpt(
    parsed_ddq: Dict[str, Any],
    base_tags: List[str],
    model: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Take:
      - parsed_ddq: full parse_ddq() output
      - base_tags: deterministic tags from infer_risk_tags_from_ddq()

    Return:
      - a list of objects:
        [
          {"id": "high_volatility_risk", "include": True, "reason": "..."},
          ...
        ]

    The model is allowed to:
      - KEEP most base tags
      - DROP a tag if DDQ evidence clearly *doesn't* support it
      - ADD a *small* number of extra tags if there's strong support

    It is *not* allowed to:
      - Go wild and add every possible tag
      - Suggest mitigations that require the issuer/protocol to change behaviour
    """

    if not base_tags:
        return []

    # Choose model: risk-specific override, then domain model, then default.
    model = (
        model
        or os.getenv("OPENAI_RISK_MODEL")
        or os.getenv("OPENAI_DOMAIN_MODEL")
        or "gpt-5.2"
    )

    domain_stats = parsed_ddq.get("domain_stats", [])
    board_escalations = parsed_ddq.get("board_escalations", [])

    # --- Build a compact context snapshot --------------------------------
    ctx_lines: List[str] = []

    ctx_lines.append("Domain summary:")
    for d in domain_stats:
        try:
            avg = float(d.avg_score)
        except Exception:
            avg = 0.0
        ctx_lines.append(
            f"- {d.name}: band={d.band_name}, avg_score={avg:.2f}, "
            f"board_escalations={d.board_escalation_count}"
        )

    if board_escalations:
        ctx_lines.append("\nKey escalation narratives (truncated):")
        # Keep it short-ish to stay token-efficient
        for esc in board_escalations[:30]:
            flag = (esc.flag or "").strip()
            snippet = (esc.raw_narrative or "").replace("\n", " ")
            if len(snippet) > 280:
                snippet = snippet[:277] + "..."
            ctx_lines.append(
                f"[{esc.domain_name}] {esc.question_id} ({flag}): {snippet}"
            )

    context_text = "\n".join(ctx_lines)

    # --- Prompt -----------------------------------------------------------
    system_text = (
        "You are helping a cryptoasset listing committee produce concise, "
        "regulator-style asset-specific risk disclosures.\n"
        "- Your job is ONLY to decide which internal risk tags apply to the token.\n"
        "- Risk tags are labels like 'bridge_dependency_risk' or 'stablecoin_peg_break_risk'.\n"
        "- You do NOT write user-facing wording or mitigations.\n"
        "- Be conservative and materiality-focused: only keep tags that reflect "
        "clear, decision-relevant risks supported by the evidence.\n"
        "- Do NOT propose mitigations that require the issuer or protocol to change "
        "their behaviour, website, whitepapers, or product. Assume the exchange "
        "cannot change the project itself."
    )

    user_text = f"""
    We are assessing a crypto token using a due diligence questionnaire (DDQ).
    Here is a compact snapshot of the results:

    {context_text}

    The deterministic rules have already assigned these base risk tags:

    {base_tags}

    Your tasks:

    1. Start from the base_tags above.
    2. Optionally ADD a small number of extra tags if the DDQ evidence clearly and strongly
    supports an additional, *material* risk that would matter for listing decisions.
    3. Optionally DROP a base tag if the DDQ evidence clearly does NOT support it.
    4. Keep the final number of tags small and focused (ideally 3–10 tags total).
    Do NOT include generic 'all crypto' risks; only include token/project-specific
    risk patterns that are outsized vs a typical large-cap asset.

    Available tag IDs include (examples, not exhaustive):
    - smart_contract_risk
    - oracle_dependency_risk
    - bridge_dependency_risk
    - admin_key_centralisation_risk
    - unaudited_code_risk
    - upgradeability_risk
    - complex_protocol_design_risk
    - high_volatility_risk
    - low_liquidity_risk
    - whale_concentration_risk
    - high_emissions_inflation_risk
    - insider_unlocks_risk
    - thin_market_venue_risk
    - defi_rug_pull_exit_risk
    - defi_liquidation_mechanism_risk
    - stablecoin_peg_break_risk
    - stablecoin_collateral_opacity_risk
    - stablecoin_counterparty_risk
    - stablecoin_redemption_risk
    - stablecoin_fx_risk
    - stablecoin_algorithmic_risk
    - wrapped_collateral_risk
    - wrapped_custody_risk
    - wrapped_price_divergence_risk
    - memecoin_hype_dependency_risk
    - memecoin_no_utility_risk
    - gov_token_governance_concentration_risk
    - security_token_issuer_default_risk
    - single_protocol_dependency_risk
    - infrastructure_centralisation_risk
    - unsustainable_yield_risk
    - treasury_concentration_risk
    - mev_and_sandwich_risk
    - rehypothecation_risk
    - claims_hierarchy_uncertainty_risk
    - poor_disclosure_quality_risk

    Respond ONLY with strict JSON in this form:

    {{
    "tags": [
        {{
        "id": "high_volatility_risk",
        "include": true,
        "reason": "Short explanation grounded in the DDQ evidence."
        }}
    ]
    }}
    """

    # NOTE: we reuse the same `client` object defined earlier in this module.
    client = get_client()
    
    resp = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_text}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_text}],
            },
        ],
    )

    try:
        raw_text = resp.output[0].content[0].text
    except Exception:
        raw_text = str(resp)

    # --- Parse JSON safely ------------------------------------------------
    try:
        data = json.loads(raw_text)
        parsed_tags = data.get("tags", [])
    except Exception:
        # Fallback: keep base_tags only if JSON parsing fails
        parsed_tags = [
            {
                "id": t,
                "include": True,
                "reason": "Included by deterministic DDQ rule (GPT JSON parse failure).",
            }
            for t in base_tags
        ]

    # Normalise and filter
    seen = set()
    out: List[Dict[str, Any]] = []
    for item in parsed_tags:
        tid = (item.get("id") or "").strip()
        if not tid or tid in seen:
            continue
        include = bool(item.get("include", True))
        reason = (item.get("reason") or "").strip()

        if include:
            out.append(
                {
                    "id": tid,
                    "include": True,
                    "reason": reason or "Included by GPT risk tag refiner.",
                }
            )
            seen.add(tid)

    # If GPT dropped everything, default back to base_tags
    if not out:
        out = [
            {
                "id": t,
                "include": True,
                "reason": "Included by deterministic DDQ rule (fallback – empty GPT result).",
            }
            for t in base_tags
        ]

    return out


# ---------------------------------------------------------------------------
# Executive summary generator
# ---------------------------------------------------------------------------


def generate_executive_summary_via_gpt(
    payload: Dict[str, Any],
    model: str | None = None,
) -> Dict[str, Any]:
    """Generate a structured executive summary JSON.

    The input `payload` is expected to be a curated snapshot (not the raw DDQ).
    """

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set; cannot call OpenAI API.")

    model_name = (
        model
        or os.getenv("OPENAI_EXEC_SUMMARY_MODEL")
        or os.getenv("OPENAI_DOMAIN_MODEL")
        or "gpt-5-mini"
    )

    client = get_client()

    payload_json = json.dumps(payload, ensure_ascii=False)

    system_text = (
        "You are a senior cryptoasset listing and risk analyst writing for a listing committee.\n"
        "Write in neutral, regulator-aware UK-style English.\n"
        "Do not invent facts beyond the provided JSON.\n"
        "Do not recommend actions that require the issuer/protocol/foundation to change behaviour; "
        "only actions the CLIENT FIRM can take (controls, monitoring, disclosures, limits, governance).\n"
        "Be concise, non-marketing, and consistent across runs."
    )

    user_text = (
        "You are given JSON describing a token risk snapshot.\n\n"
        "JSON INPUT:\n"
        f"{payload_json}\n\n"
        "Return STRICT JSON with this shape:\n"
        "{\n"
        '  "headline_decision_view": "...",\n'
        '  "overall_posture": "benign|intermediate|heightened|unknown",\n'
        '  "one_paragraph_narrative": "<= 120 words",\n'
        '  "key_positives": ["<= 5 bullets"],\n'
        '  "key_risks_and_mitigations": [\n'
        '    {"risk": "<= 30 words", "mitigation": "<= 30 words"}\n'
        '  ],\n'
        '  "board_escalations_summary": {"count": 0, "notable": [{"domain": "...", "issue": "<= 20 words"}]},\n'
        '  "recommended_listing_requirements": [{"id": "...", "severity": "...", "title": "..."}],\n'
        '  "open_questions_for_committee": ["<= 4 bullets"],\n'
        '  "generation": {"method": "gpt", "model": "..."}\n'
        "}\n\n"
        "Rules:\n"
        "- Keep bullet counts tight (3-5 items where possible).\n"
        "- If evidence is thin or ambiguous, say so briefly rather than guessing.\n"
        "- Use mitigations that map to CLIENT FIRM actions (monitoring, disclosures, limits).\n"
        "- Output JSON only, no extra commentary."
    )

    resp = client.responses.create(
        model=model_name,
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_text}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_text}],
            },
        ],
    )

    raw_text = getattr(resp, "output_text", None)
    if raw_text is None:
        try:
            raw_text = resp.output[0].content[0].text
        except Exception:
            raw_text = str(resp)

    raw_text = (raw_text or "").strip()
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(raw_text[start : end + 1])
        else:
            raise RuntimeError(f"Failed to parse GPT executive summary JSON: {raw_text!r}")

    # Minimal schema check
    for k in (
        "headline_decision_view",
        "overall_posture",
        "one_paragraph_narrative",
        "key_positives",
        "key_risks_and_mitigations",
        "open_questions_for_committee",
    ):
        if k not in data:
            raise RuntimeError(f"Missing key '{k}' in GPT executive summary output")

    return data
