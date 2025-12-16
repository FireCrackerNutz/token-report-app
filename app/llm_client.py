from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from openai import OpenAI

from .models import DomainStats, BoardEscalation

# Lazily-created shared client
_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
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
