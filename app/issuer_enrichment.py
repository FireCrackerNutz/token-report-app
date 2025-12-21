from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


_CACHE_DIR = Path(os.getenv("ENRICHMENT_CACHE_DIR", ".cache/enrichment"))


def _utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _safe_slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = "".join(ch if ch.isalnum() else "-" for ch in s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "unknown"


def _ensure_client() -> "OpenAI":
    if OpenAI is None:
        raise RuntimeError("openai package not available")
    return OpenAI()


def _load_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    try:
        p = _CACHE_DIR / f"{cache_key}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _save_cache(cache_key: str, payload: Dict[str, Any]) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p = _CACHE_DIR / f"{cache_key}.json"
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # Cache failures must never fail report generation
        return


def _asset_seed(asset: Dict[str, Any]) -> Dict[str, Any]:
    """Return a small, stable seed for enrichment prompts."""
    return {
        "coingecko_id": asset.get("coingecko_id") or asset.get("id"),
        "name": asset.get("name"),
        "symbol": asset.get("symbol"),
        "token_type": asset.get("token_type"),
        "website": asset.get("website"),
        "whitepaper": asset.get("whitepaper"),
        "website_host": asset.get("website_host"),
        "whitepaper_host": asset.get("whitepaper_host"),
    }


def enrich_issuer_and_key_people(
    *,
    asset: Dict[str, Any],
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Enrich issuer + key people via OpenAI web_search.

    Design goals:
      - Repeatable: deterministic input seed + cached results
      - Defensible: strict 'Unknown' for fields without evidence
      - Minimal coupling: returns a single JSON object safe to add to snapshot

    Env toggles:
      - ENABLE_ISSUER_ENRICHMENT=0 to skip
      - OPENAI_ISSUER_ENRICHMENT_MODEL to override model
      - ISSUER_ENRICHMENT_REFRESH=1 to bypass cache
    """
    enabled = os.getenv("ENABLE_ISSUER_ENRICHMENT", "1").strip() != "0"
    if not enabled:
        return {"status": "skipped", "reason": "ENABLE_ISSUER_ENRICHMENT=0"}

    if not os.getenv("OPENAI_API_KEY"):
        return {"status": "skipped", "reason": "OPENAI_API_KEY not set"}

    seed = _asset_seed(asset)
    cache_key = (
        seed.get("coingecko_id")
        or seed.get("website_host")
        or seed.get("name")
        or "issuer_enrichment"
    )
    cache_key = f"issuer_people__{_safe_slug(str(cache_key))}"

    refresh = os.getenv("ISSUER_ENRICHMENT_REFRESH", "0") == "1"
    if not refresh:
        cached = _load_cache(cache_key)
        if cached:
            return cached

    model_name = (
        model
        or os.getenv("OPENAI_ISSUER_ENRICHMENT_MODEL")
        or os.getenv("OPENAI_EXEC_SUMMARY_MODEL")
        or os.getenv("OPENAI_DOMAIN_MODEL")
        or os.getenv("OPENAI_RESPONSES_MODEL")
        or "gpt-5-mini"
    )

    system_text = (
        "You are a due diligence analyst. Your job is to identify the legal issuer / controlling entity "
        "behind a crypto token/project, and the key people involved, using web search.\n\n"
        "Rules:\n"
        "- Be conservative: if you cannot substantiate a field with a credible public source, output 'Unknown' for that field.\n"
        "- Prefer primary/official sources: official project website legal pages (imprint/terms), regulator filings, company registries.\n"
        "- Do not guess or infer legal entities from token names.\n"
        "- Key people must come from official sources or high-quality profiles (e.g., official team page, verified registry officers). "
        "Do not use random blog posts.\n"
        "- Every non-Unknown field must include at least one evidence link.\n"
        "- Keep text concise and compliance-friendly.\n"
        "- Output must be STRICT JSON and must match the schema implied by the example.\n"
    )

    user_text = (
        "Find the token issuer (legal entity) and key people for the project described below.\n\n"
        "PROJECT SEED (JSON):\n"
        f"{json.dumps(seed, ensure_ascii=False)}\n\n"
        "Return STRICT JSON with this shape:\n"
        "{\n"
        '  "status": "ok|partial|unknown",\n'
        '  "retrieved_at_utc": "YYYY-MM-DD HH:MM UTC",\n'
        '  "issuer": {\n'
        '    "legal_name": "string|Unknown",\n'
        '    "entity_type": "string|Unknown",\n'
        '    "jurisdiction": "string|Unknown",\n'
        '    "registration_number": "string|Unknown",\n'
        '    "lei": "string|Unknown",\n'
        '    "registered_address": "string|Unknown",\n'
        '    "status": "Active|Dissolved|Unknown",\n'
        '    "website": "string|Unknown",\n'
        '    "confidence": "high|medium|low|unknown",\n'
        '    "evidence": [{"label": "string", "url": "string"}]\n'
        "  },\n"
        '  "key_people": [\n'
        "    {\n"
        '      "name": "string",\n'
        '      "role": "string|Unknown",\n'
        '      "affiliation": "string|Unknown",\n'
        '      "confidence": "high|medium|low|unknown",\n'
        '      "evidence": [{"label": "string", "url": "string"}]\n'
        "    }\n"
        "  ],\n"
        '  "notes": "string"\n'
        "}\n\n"
        "Guidance:\n"
        "- If you find a registry listing (e.g., Companies House / OpenCorporates), include it as evidence.\n"
        "- If issuer cannot be identified reliably, set issuer fields to 'Unknown' and status='unknown'.\n"
        "- Key people list: up to 8 entries, prioritise founders/execs/governance leads.\n"
    )

    # Call OpenAI with hosted web search tool enabled (agentic).
    client = _ensure_client()
    try:
        resp = client.responses.create(
            model=model_name,
            tools=[{"type": "web_search"}],
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system_text}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
            ],
        )
    except Exception as e:
        # Some models may not support web_search; fallback to gpt-5.
        try:
            resp = client.responses.create(
                model="gpt-5",
                tools=[{"type": "web_search"}],
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": system_text}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
                ],
            )
        except Exception:
            return {"status": "error", "reason": f"OpenAI web_search call failed: {e!s}"}

    raw_text = getattr(resp, "output_text", None)
    if raw_text is None:
        try:
            raw_text = resp.output[0].content[0].text
        except Exception:
            raw_text = str(resp)
    raw_text = (raw_text or "").strip()

    # Parse JSON robustly (strip leading commentary if any).
    data: Dict[str, Any]
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start >= 0 and end >= 0 and end > start:
            data = json.loads(raw_text[start : end + 1])
        else:
            return {"status": "error", "reason": "Could not parse issuer enrichment JSON", "raw_preview": raw_text[:400]}

    # Normalize and add timestamps
    data.setdefault("retrieved_at_utc", _utc_now_str())

    # Cache and return
    _save_cache(cache_key, data)
    return data
