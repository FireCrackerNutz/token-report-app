from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from urllib.parse import urlencode
from urllib.request import Request, urlopen


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
        for c in coins:
            nm = (c.get("name") or "").strip().lower()
            if name_l and nm == name_l:
                return c.get("id"), "exact name match (symbol mismatch)"
        return None, "no match in coins/list"

    if name_l:
        for c in candidates:
            nm = (c.get("name") or "").strip().lower()
            if nm == name_l:
                return c.get("id"), "exact name match among same-symbol candidates"
        for c in candidates:
            nm = (c.get("name") or "").strip().lower()
            if name_l in nm or nm in name_l:
                return c.get("id"), "fuzzy name match among same-symbol candidates"

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


def fetch_external_token_metadata(token_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort fetch of external token metadata.

    Controlled via env:
      - TOKEN_METADATA_PROVIDER: coingecko | off
    If not set, we use CoinGecko if a key is present.
    """
    provider = (os.getenv("TOKEN_METADATA_PROVIDER") or "").strip().lower()
    if provider in {"off", "none", "0", "false"}:
        return {"provider": provider or "off", "enabled": False}

    # Default/only provider in this repo build
    return _fetch_coingecko_metadata(token_meta)


_TAG_LABELS: Dict[str, str] = {
    "admin_key_centralisation_risk": "Admin keys / privileged access",
    "upgradeability_risk": "Upgradability / change control",
    "smart_contract_risk": "Smart contract dependency",
    "treasury_concentration_risk": "Treasury / reserve concentration",
    "infrastructure_centralisation_risk": "Infrastructure centralisation",
    "insider_unlocks_risk": "Insider unlocks / allocations",
    "poor_disclosure_quality_risk": "Disclosure quality concerns",
    "sanctions_exposure_risk": "Sanctions / high-risk geography exposure",
    "sanctions_designated_wallets_risk": "Designated wallets/entities exposure",
    "sanctions_screening_controls_risk": "Sanctions screening control gaps",
    "sanctions_enforcement_watch_risk": "Sanctions-related enforcement watch",
}


def _label_for_tag(tag_id: str) -> str:
    return _TAG_LABELS.get(tag_id, tag_id.replace("_", " ").strip())


def _clip(s: Optional[str], n: int = 600) -> Optional[str]:
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    return s if len(s) <= n else (s[: n - 3] + "...")


def _fallback_description_from_ddq(parsed_ddq: Dict[str, Any]) -> Optional[str]:
    """
    DDQ fallback order:
      1) A1.1 narrative (token_category.narrative)
      2) A1.1 raw
      3) parsed_ddq.project_description
    """
    tc = parsed_ddq.get("token_category") or {}
    desc = (tc.get("narrative") or "").strip()
    if desc:
        return _clip(desc)

    raw = (tc.get("raw") or "").strip()
    if raw:
        return _clip(raw)

    pd = (parsed_ddq.get("project_description") or "").strip()
    if pd:
        return _clip(pd)

    return None


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
    token_meta = token_meta or {}
    listing_ctx = listing_ctx or {}
    listing_requirements = listing_requirements or []

    name = (token_meta.get("name") or parsed_ddq.get("project_description") or "Unknown token").strip()
    ticker = (token_meta.get("ticker") or "").strip()
    token_type = (token_meta.get("token_type") or "other").strip()

    external = {}
    try:
        external = fetch_external_token_metadata({"name": name, "ticker": ticker, **token_meta})
    except Exception as e:
        external = {"provider": "auto", "enabled": True, "error": str(e)}

    overall_band = risk_dashboard.get("overall_band") or {"numeric": 0, "name": "Unknown"}
    total_real_escalations = len(board_escalation_cards or [])

    included_tags: List[Dict[str, Any]] = [t for t in (refined_risk_tags or []) if bool(t.get("include", True))]
    top_tags = included_tags[:6]
    top_tag_ids = [t.get("id") for t in top_tags if t.get("id")]

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

    disclosure_flag = "unknown"
    if any((t.get("id") == "poor_disclosure_quality_risk") for t in included_tags):
        disclosure_flag = "poor"

    control_signal_ids = [
        "admin_key_centralisation_risk",
        "upgradeability_risk",
        "smart_contract_risk",
        "gov_token_governance_concentration_risk",
    ]
    signals = []
    tag_set = set([t.get("id") for t in included_tags if t.get("id")])
    for tid in control_signal_ids:
        signals.append({"id": tid, "label": _label_for_tag(tid), "present": tid in tag_set})

    # Description: CoinGecko first, DDQ fallback second
    description_short = _clip(external.get("description_en")) or _clip(external.get("description")) or _fallback_description_from_ddq(parsed_ddq)

    chains = []
    if isinstance(external.get("platforms"), dict):
        chains = [k for k, v in external.get("platforms").items() if v]
    primary_chain = chains[0] if chains else None

    reqs_compact = [{"id": r.get("id"), "severity": r.get("severity"), "title": r.get("title")} for r in listing_requirements or []]

    urls = external.get("urls") or {}
    website = urls.get("homepage") or urls.get("website")
    whitepaper = urls.get("whitepaper")

    return {
        "asset": {
            "name": name,
            "ticker": ticker,
            "token_type": token_type,
            "description_short": description_short,
            "primary_chain": primary_chain,
            "chains": chains,
            "website": website,
            "whitepaper": whitepaper,
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
            {"id": "total_escalations", "label": "Listing committee escalation triggers", "value": total_real_escalations, "format": "number"},
            {"id": "top_risk_tags", "label": "Top risk drivers", "value": top_tag_ids, "format": "list"},
        ],
        "risk_highlights": {
            "top_risk_tags": [
                {"id": t.get("id"), "label": _label_for_tag(t.get("id") or ""), "reason": (t.get("reason") or "").strip() or None}
                for t in top_tags
                if t.get("id")
            ],
            "top_domains": [
                {"domain": d.get("name"), "band": {"numeric": d.get("band_numeric"), "name": d.get("band_name")}, "escalations": d.get("board_escalation_count")}
                for d in top_domains
            ],
        },
        "governance_and_controls": {"summary": None, "signals": signals},
        "listing_requirements_summary": reqs_compact,
        "data_quality": {"ddq_completeness_note": None, "disclosure_quality_flag": disclosure_flag, "known_gaps": []},
        "external_metadata": external,
        "sources": {
            "token_meta_provided": bool(token_meta),
            "derived_from": ["parsed_ddq", "risk_dashboard", "refined_risk_tags", "board_escalations", "listing_context"],
        },
    }
