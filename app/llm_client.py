import json
import os
from typing import Any, Dict, List

from openai import OpenAI

from .models import DomainStats, BoardEscalation

# Create a single shared client
client = OpenAI()

# Default model for domain findings, but override via env if you want
DEFAULT_DOMAIN_MODEL = os.getenv("OPENAI_DOMAIN_MODEL", "gpt-4.1-mini")


def _build_domain_prompt(domain: DomainStats, escalations: List[BoardEscalation]) -> str:
    """
    Build a compact JSON-ish context string for the model.
    """
    esc_payload = [
        {
            "question_id": e.question_id,
            "question_text": e.question_text,
            "flag": e.flag,
            "trigger_rule": e.trigger_rule,
            "staleness_class": e.staleness_class,
        }
        for e in escalations
    ]

    context = {
        "domain": {
            "code": domain.code,
            "name": domain.name,
            "band_name": domain.band_name,
            "band_numeric": domain.band_numeric,
            "avg_score": domain.avg_score,
            "has_board_escalation": domain.has_board_escalation,
            "board_escalation_count": domain.board_escalation_count,
        },
        "board_escalations": esc_payload,
    }

    return json.dumps(context, indent=2)


def generate_domain_findings_via_gpt(
    domain: DomainStats,
    escalations: List[BoardEscalation],
    model: str | None = None,
) -> Dict[str, Any]:
    """
    Call GPT to generate domain findings for a single domain.

    Returns a dict with:
      {
        "one_line": str,
        "strengths": [str, ...],
        "risks": [str, ...],
        "watchpoints": [str, ...]
      }
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set; cannot call GPT.")

    model_name = model or DEFAULT_DOMAIN_MODEL

    context_str = _build_domain_prompt(domain, escalations)

    system_msg = (
        "You are a senior cryptoasset risk analyst writing concise, "
        "board-facing findings for an institutional token listing report. "
        "You are given numeric risk information for one risk domain and any "
        "board escalation triggers. "
        "Write in clear, neutral UK English."
    )

    user_msg = (
        "Here is the domain context as JSON:\n\n"
        f"{context_str}\n\n"
        "Using this, produce a STRICT JSON object with the following shape:\n"
        "{\n"
        '  \"one_line\": \"<single sentence overview>\",\n'
        '  \"strengths\": [\"<bullet 1>\", \"<bullet 2>\", ...],\n'
        '  \"risks\": [\"<bullet 1>\", \"<bullet 2>\", ...],\n'
        '  \"watchpoints\": [\"<bullet 1>\", \"<bullet 2>\", ...]\n'
        "}\n\n"
        "Guidance:\n"
        "- Do NOT include any keys other than one_line, strengths, risks, watchpoints.\n"
        "- Each bullet should be at most 40 words.\n"
        "- Do not mention numeric scores or weights explicitly; describe them qualitatively.\n"
        "- If there are board escalations, clearly reflect them in the risks.\n"
        "- If there are none, say so briefly in strengths or risks.\n"
        "- Output ONLY the JSON, with no surrounding text."
    )

    resp = client.responses.create(
        model=model_name,
        input=[
            {
                "role": "system",
                "content": system_msg,
            },
            {
                "role": "user",
                "content": user_msg,
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    content = resp.output[0].content[0].text

    data = json.loads(content)

    # Basic sanity check
    for key in ("one_line", "strengths", "risks", "watchpoints"):
        if key not in data:
            raise RuntimeError(f"GPT JSON missing key '{key}' for domain {domain.name}")

    return data
