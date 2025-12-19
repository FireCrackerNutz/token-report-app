from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from urllib.parse import urlencode
from urllib.request import Request, urlopen


# ---------------------------------------------------------------------------
# External metadata enrichment (optional)
#
# We keep this small and dependency-free (stdlib urllib only).
# Providers supported:
#   - CoinGecko (recommended default)
#   - CoinMarketCap (requires Pro key)
#
# Notes:
# - CoinGecko Demo/Pro keys are supplied via headers; see docs.
# - CoinMarketCap keys use X-CMC_PRO_API_KEY header; /cryptocurrency/info
#   returns logo + URLs.
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 20) -> Any:
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _coingecko_auth() -> Tuple[Optional[str], Dict[str, str]]:
    """Return (base_url, headers). If no key is available, base_url is None."""
    pro_key = os.getenv("COINGECKO_PRO_API_KEY")
    demo_key = os.getenv("COINGECKO_DEMO_API_KEY")

    if pro_key:
        return "https://pro-api.coingecko.com/api/v3", {"x-cg-pro-api-key": pro_key}
    if demo_key:
        return "https://api.coingecko.com/api/v3", {"x-cg-demo-api-key": demo_key}

    # CoinGecko now generally expects an API key even on the Demo/Public API.
    return None, {}


def _coingecko_cache_paths() -> Tuple[str, str]:
    cache_dir = os.getenv("TOKEN_METADATA_CACHE_DIR", ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    return (
        os.path.join(cache_dir, "coingecko_coins_list.json"),
        os.path.join(cache_dir, "coingecko_coins_list.meta.json"),
    )


def _load_coingecko_coins_list(
    base_url: str, headers: Dict[str, str], max_age_seconds: int = 7 * 24 * 3600
) -> List[Dict[str, Any]]:
    path, meta_path = _coingecko_cache_paths()
    now = time.time()

    try:
        if os.path.exists(path) and os.path.exists(meta_path):
            meta = json.loads(open(meta_path, "r", encoding="utf-8").read())
            fetched_at = float(meta.get("fetched_at", 0))
            if fetched_at and (now - fetched_at) <= max_age_seconds:
                return json.loads(open(path, "r", encoding="utf-8").read())
    except Exception:
        # Cache is best-effort. Ignore and refetch.
        pass

    url = f"{base_url}/coins/list?{urlencode({'include_platform': 'true'})}"
    data = _http_get_json(url, headers=headers)

    try:
        open(path, "w", encoding="utf-8").write(json.dumps(data))
        open(meta_path, "w", encoding="utf-8").write(
            json.dumps({"fetched_at": now, "fetched_at_utc": _utc_now_iso()})
        )
    except Exception:
        pass

    return data


def _resolve_coingecko_id(
    *,
    base_url: str,
    headers: Dict[str, str],
    name: str,
    ticker: str,
    explicit_id: Optional[str] = None,
) -> Tuple[Optional[str], str]:
    """Return (coingecko_id, match_note)."""
    if explicit_id:
        return explicit_id, "explicit coingecko_id provided"

    ticker_l = (ticker or "").strip().lower()
    name_l = (name or "").strip().lower()

    if not ticker_l and not name_l:
        return None, "no name/ticker to resolve"

    coins = _load_coingecko_coins_list(base_url, headers)

    candidates = []
    for c in coins:
        sym = (c.get("symbol") or "").strip().lower()
        nm = (c.get("name") or "").strip().lower()
        if ticker_l and sym != ticker_l:
            continue
        if name_l and nm == name_l:
            return c.get("id"), "exact name+symbol match"
        candidates.append(c)

    if not candidates:
        # fallback: try name-only exact match
        for c in coins:
            nm = (c.get("name") or "").strip().lower()
            if name_l and nm == name_l:
                return c.get("id"), "exact name match (symbol mismatch)"
        return None, "no match in coins/list"

    # Prefer name-substring match if we have a name
    if name_l:
        for c in candidates:
            nm = (c.get("name") or "").strip().lower()
            if nm == name_l:
                return c.get("id"), "exact name match among same-symbol candidates"
        for c in candidates:
            nm = (c.get("name") or "").strip().lower()
            if name_l in nm or nm in name_l:
                return c.get("id"), "fuzzy name match among same-symbol candidates"

    # Otherwise pick the first candidate for that ticker.
    return candidates[0].get("id"), "symbol-only match (ambiguous)"


def _fetch_coingecko_metadata(token_meta: Dict[str, Any]) -> Dict[str, Any]:
    base_url, headers = _coingecko_auth()
    if not base_url:
        return {
            "provider": "coingecko",
            "enabled": False,
            "error": "COINGECKO_DEMO_API_KEY or COINGECKO_PRO_API_KEY not set",
        }

    name = (token_meta.get("name") or "").strip()
    ticker = (token_meta.get("ticker") or "").strip()
    explicit_id = (token_meta.get("coingecko_id") or "").strip() or None

    coin_id, note = _resolve_coingecko_id(
        base_url=base_url,
        headers=headers,
        name=name,
        ticker=ticker,
        explicit_id=explicit_id,
    )

    if not coin_id:
        return {
            "provider": "coingecko",
            "enabled": True,
            "resolved": {"coin_id": None, "note": note},
            "error": "Could not resolve CoinGecko coin ID",
        }

    url = f"{base_url}/coins/{coin_id}"
    data = _http_get_json(url, headers=headers)

    # Extract a compact, renderer-friendly subset
    links = data.get("links") or {}
    image = data.get("image") or {}
    desc = (data.get("description") or {}).get("en") or ""
    desc = desc.strip()
    if len(desc) > 600:
        desc = desc[:597] + "..."

    market_data = data.get("market_data") or {}

    return {
        "provider": "coingecko",
        "enabled": True,
        "resolved": {"coin_id": coin_id, "note": note},
        "fetched_at_utc": _utc_now_iso(),
        "name": data.get("name"),
        "symbol": data.get("symbol"),
        "categories": data.get("categories") or [],
        "description_en": desc or None,
        "logo_url": image.get("large") or image.get("small") or image.get("thumb"),
        "urls": {
            "homepage": (links.get("homepage") or [None])[0],
            "whitepaper": links.get("whitepaper"),
            "blockchain_site": (links.get("blockchain_site") or []),
            "repos": links.get("repos_url") or {},
        },
        "platforms": data.get("platforms") or {},
        "market": {
            "market_cap_rank": data.get("market_cap_rank"),
            "market_cap_usd": (market_data.get("market_cap") or {}).get("usd"),
            "volume_24h_usd": (market_data.get("total_volume") or {}).get("usd"),
            "circulating_supply": market_data.get("circulating_supply"),
            "total_supply": market_data.get("total_supply"),
            "max_supply": market_data.get("max_supply"),
            "last_updated": market_data.get("last_updated"),
        },
    }


def _fetch_coinmarketcap_metadata(token_meta: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.getenv("CMC_PRO_API_KEY") or os.getenv("COINMARKETCAP_API_KEY")
    if not api_key:
        return {
            "provider": "coinmarketcap",
            "enabled": False,
            "error": "CMC_PRO_API_KEY (or COINMARKETCAP_API_KEY) not set",
        }

    # Prefer explicit IDs/slugs if provided; otherwise use symbol.
    params: Dict[str, str] = {}
    if token_meta.get("cmc_id"):
        params["id"] = str(token_meta["cmc_id"])  # type: ignore[index]
    elif token_meta.get("cmc_slug"):
        params["slug"] = str(token_meta["cmc_slug"])  # type: ignore[index]
    else:
        sym = (token_meta.get("ticker") or "").strip()
        if sym:
            params["symbol"] = sym

    if not params:
        return {
            "provider": "coinmarketcap",
            "enabled": True,
            "error": "No cmc_id/cmc_slug/ticker available to query /cryptocurrency/info",
        }

    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/info?" + urlencode(params)
    headers = {"X-CMC_PRO_API_KEY": api_key, "Accept": "application/json"}
    data = _http_get_json(url, headers=headers)

    # Response shape is {"data": {"<id>": {...}}} for id/symbol/slug
    payload = data.get("data") or {}
    item = None
    if isinstance(payload, dict) and payload:
        item = next(iter(payload.values()))

    if not item:
        return {
            "provider": "coinmarketcap",
            "enabled": True,
            "fetched_at_utc": _utc_now_iso(),
            "error": "No data returned from /cryptocurrency/info",
        }

    urls = item.get("urls") or {}
    return {
        "provider": "coinmarketcap",
        "enabled": True,
        "fetched_at_utc": _utc_now_iso(),
        "id": item.get("id"),
        "name": item.get("name"),
        "symbol": item.get("symbol"),
        "slug": item.get("slug"),
        "description": (item.get("description") or "")[:600] or None,
        "logo_url": item.get("logo"),
        "urls": {
            "website": (urls.get("website") or [None])[0],
            "whitepaper": (urls.get("technical_doc") or [None])[0],
            "explorers": urls.get("explorer") or [],
            "source_code": urls.get("source_code") or [],
        },
        "tags": item.get("tags") or [],
        "platform": item.get("platform"),
    }


def fetch_external_token_metadata(token_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort fetch of external token metadata.

    Controlled via env:
      - TOKEN_METADATA_PROVIDER: coingecko | coinmarketcap | off
    If not set, we prefer CoinGecko if a key is present, else fall back to CMC.
    """

    provider = (os.getenv("TOKEN_METADATA_PROVIDER") or "").strip().lower()
    if provider in {"off", "none", "0", "false"}:
        return {"provider": provider or "off", "enabled": False}

    if provider == "coinmarketcap":
        return _fetch_coinmarketcap_metadata(token_meta)
    if provider == "coingecko":
        return _fetch_coingecko_metadata(token_meta)

    # Auto mode
    if os.getenv("COINGECKO_PRO_API_KEY") or os.getenv("COINGECKO_DEMO_API_KEY"):
        return _fetch_coingecko_metadata(token_meta)
    if os.getenv("CMC_PRO_API_KEY") or os.getenv("COINMARKETCAP_API_KEY"):
        return _fetch_coinmarketcap_metadata(token_meta)

    return {
        "provider": "auto",
        "enabled": False,
        "error": "No external metadata API keys found in env",
    }


# ---------------------------------------------------------------------------
# Token fact sheet builder
# ---------------------------------------------------------------------------


_TAG_LABELS: Dict[str, str] = {
    "admin_key_centralisation_risk": "Admin keys / privileged access",
    "upgradeability_risk": "Upgradability / change control",
    "smart_contract_risk": "Smart contract dependency",
    "treasury_concentration_risk": "Treasury / reserve concentration",
    "infrastructure_centralisation_risk": "Infrastructure centralisation",
    "insider_unlocks_risk": "Insider unlocks / allocations",
    "poor_disclosure_quality_risk": "Disclosure quality concerns",
}


def _label_for_tag(tag_id: str) -> str:
    return _TAG_LABELS.get(tag_id, tag_id.replace("_", " ").strip())


def build_token_fact_sheet(
    *,
    parsed_ddq: Dict[str, Any],
    token_meta: Dict[str, Any],
    risk_dashboard: Dict[str, Any],
    refined_risk_tags: List[Dict[str, Any]],
    board_escalation_cards: List[Dict[str, Any]],
    listing_ctx: Optional[Dict[str, Any]] = None,
    listing_requirements: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build a structured, render-friendly token fact sheet.

    This object is designed for a PDF/HTML 'Key facts' section.
    External metadata enrichment is best-effort and optional.
    """

    token_meta = token_meta or {}
    listing_ctx = listing_ctx or {}
    listing_requirements = listing_requirements or []

    name = (token_meta.get("name") or parsed_ddq.get("project_description") or "Unknown token").strip()
    ticker = (token_meta.get("ticker") or "").strip()
    token_type = (token_meta.get("token_type") or "governance_utility").strip()

    # External enrichment (websites, logo, short description, market facts)
    external = {}
    try:
        external = fetch_external_token_metadata({"name": name, "ticker": ticker, **token_meta})
    except Exception as e:
        external = {"provider": "auto", "enabled": True, "error": str(e)}

    overall_band = risk_dashboard.get("overall_band") or {"numeric": 0, "name": "Unknown"}

    # Basic counts
    total_real_escalations = len(board_escalation_cards or [])

    # Tags: keep only included ones, preserve input order
    included_tags: List[Dict[str, Any]] = [
        t for t in (refined_risk_tags or []) if bool(t.get("include", True))
    ]

    top_tags = included_tags[:6]
    top_tag_ids = [t.get("id") for t in top_tags if t.get("id")]

    # Domains: show the highest-risk domains
    domains = (risk_dashboard.get("domains") or [])
    top_domains = sorted(
        domains,
        key=lambda d: (
            int(d.get("band_numeric") or 0),
            int(d.get("board_escalation_count") or 0),
            float(d.get("weight") or 0.0),
        ),
        reverse=True,
    )[:3]

    # Data quality heuristic
    disclosure_flag = "unknown"
    if any((t.get("id") == "poor_disclosure_quality_risk") for t in included_tags):
        disclosure_flag = "poor"

    # Governance/control signals (based on tag presence)
    control_signal_ids = [
        "admin_key_centralisation_risk",
        "upgradeability_risk",
        "smart_contract_risk",
        "gov_token_governance_concentration_risk",
    ]

    signals = []
    tag_set = set([t.get("id") for t in included_tags if t.get("id")])
    for tid in control_signal_ids:
        signals.append(
            {
                "id": tid,
                "label": _label_for_tag(tid),
                "present": tid in tag_set,
            }
        )

    # Prefer enriched description if available
    description_short = (
        external.get("description_en")
        or external.get("description")
        or None
    )

    # Prefer enriched chain/platform hints
    chains = []
    if isinstance(external.get("platforms"), dict):
        chains = [k for k, v in external.get("platforms").items() if v]  # type: ignore[union-attr]
    primary_chain = None
    if chains:
        primary_chain = chains[0]

    # Listing requirement summary (compact)
    reqs_compact = [
        {"id": r.get("id"), "severity": r.get("severity"), "title": r.get("title")}
        for r in (listing_requirements or [])
    ]

    return {
        "asset": {
            "name": name,
            "ticker": ticker,
            "token_type": token_type,
            "description_short": description_short,
            "primary_chain": primary_chain,
            "chains": chains,
            "website": (external.get("urls") or {}).get("homepage")
            or (external.get("urls") or {}).get("website"),
            "whitepaper": (external.get("urls") or {}).get("whitepaper"),
            "logo_url": external.get("logo_url"),
            "logo_source": external.get("provider") if external.get("logo_url") else None,
        },
        "classification": {
            "report_scope": "Listing risk snapshot",
            "overall_band": overall_band,
            "posture": listing_ctx.get("posture"),
            "is_speculative_profile": bool(listing_ctx.get("has_speculative_profile")),
            "has_hard_control_risks": bool(listing_ctx.get("has_hard_control")),
            "board_escalations_count": total_real_escalations,
        },
        "key_indicators": [
            {
                "id": "total_escalations",
                "label": "Board-level escalation triggers",
                "value": total_real_escalations,
                "format": "number",
            },
            {
                "id": "top_risk_tags",
                "label": "Top risk drivers",
                "value": top_tag_ids,
                "format": "list",
            },
        ],
        "risk_highlights": {
            "top_risk_tags": [
                {
                    "id": t.get("id"),
                    "label": _label_for_tag(t.get("id") or ""),
                    "reason": (t.get("reason") or "").strip() or None,
                }
                for t in top_tags
                if t.get("id")
            ],
            "top_domains": [
                {
                    "domain": d.get("name"),
                    "band": {"numeric": d.get("band_numeric"), "name": d.get("band_name")},
                    "escalations": d.get("board_escalation_count"),
                }
                for d in top_domains
            ],
        },
        "governance_and_controls": {
            "summary": None,
            "signals": signals,
        },
        "listing_requirements_summary": reqs_compact,
        "data_quality": {
            "ddq_completeness_note": None,
            "disclosure_quality_flag": disclosure_flag,
            "known_gaps": [],
        },
        "external_metadata": external,
        "sources": {
            "token_meta_provided": bool(token_meta),
            "derived_from": [
                "parsed_ddq",
                "risk_dashboard",
                "refined_risk_tags",
                "board_escalations",
                "listing_context",
            ],
        },
    }
