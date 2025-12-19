from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple


def canonical_token_type_from_ddq(token_category: Optional[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """Map DDQ A1.1 (primary/secondary) into an internal canonical token_type.

    Returns: (token_type, meta)
      - token_type: stable string used by the rest of the app
      - meta: includes primary/secondary, confidence, and a short rationale
    """
    if not token_category:
        return "other", {
            "primary": None,
            "secondary": None,
            "confidence": None,
            "rationale": "No A1.1 token category found in DDQ; defaulted to 'other'.",
        }

    primary = (token_category.get("primary") or "").strip()
    secondary = (token_category.get("secondary") or "").strip()

    p = primary.lower()
    s = secondary.lower()

    def has(txt: str, *needles: str) -> bool:
        return any(n in txt for n in needles)

    # Stablecoins
    if has(p, "stablecoin") or has(s, "stablecoin"):
        if has(p, "algorithm", "algo") or has(s, "algorithm", "algo"):
            return "stablecoin_algorithmic", {
                "primary": primary,
                "secondary": secondary,
                "confidence": token_category.get("confidence"),
                "rationale": "DDQ category indicates a stablecoin with algorithmic characteristics.",
            }
        return "stablecoin_fiat", {
            "primary": primary,
            "secondary": secondary,
            "confidence": token_category.get("confidence"),
            "rationale": "DDQ category indicates a reserve/fiat-backed stablecoin (default stablecoin mapping).",
        }

    # Wrapped tokens
    if has(p, "wrapped") or has(s, "wrapped"):
        return "wrapped", {
            "primary": primary,
            "secondary": secondary,
            "confidence": token_category.get("confidence"),
            "rationale": "DDQ category indicates a wrapped token.",
        }

    # Security / tokenised securities
    if has(p, "security") or has(p, "tokenised") or has(s, "security") or has(s, "tokenised"):
        return "security_token", {
            "primary": primary,
            "secondary": secondary,
            "confidence": token_category.get("confidence"),
            "rationale": "DDQ category indicates a security/tokenised asset.",
        }

    # Memecoins
    if has(p, "meme") or has(s, "meme"):
        return "memecoin", {
            "primary": primary,
            "secondary": secondary,
            "confidence": token_category.get("confidence"),
            "rationale": "DDQ category indicates a memecoin.",
        }

    # DeFi
    if has(p, "defi") or has(s, "defi"):
        return "defi", {
            "primary": primary,
            "secondary": secondary,
            "confidence": token_category.get("confidence"),
            "rationale": "DDQ category indicates a DeFi protocol token.",
        }

    # Native network tokens
    if has(p, "native") and has(p, "l1", "layer 1", "layer-1"):
        return "native_l1", {
            "primary": primary,
            "secondary": secondary,
            "confidence": token_category.get("confidence"),
            "rationale": "DDQ category indicates a native Layer-1 network token.",
        }
    if has(p, "native") and has(p, "l2", "layer 2", "layer-2"):
        return "native_l2", {
            "primary": primary,
            "secondary": secondary,
            "confidence": token_category.get("confidence"),
            "rationale": "DDQ category indicates a native Layer-2 network token.",
        }

    # Governance / utility
    if has(p, "govern") and has(s, "utility") or (has(p, "govern") and has(p, "utility")):
        return "governance_utility", {
            "primary": primary,
            "secondary": secondary,
            "confidence": token_category.get("confidence"),
            "rationale": "DDQ category indicates combined governance + utility role.",
        }
    if has(p, "govern"):
        return "governance", {
            "primary": primary,
            "secondary": secondary,
            "confidence": token_category.get("confidence"),
            "rationale": "DDQ category indicates a governance token role.",
        }
    if has(p, "utility"):
        return "utility", {
            "primary": primary,
            "secondary": secondary,
            "confidence": token_category.get("confidence"),
            "rationale": "DDQ category indicates a utility token role.",
        }

    # Fallback
    cleaned_primary = re.sub(r"\s+", " ", primary).strip() or None
    cleaned_secondary = re.sub(r"\s+", " ", secondary).strip() or None
    return "other", {
        "primary": cleaned_primary,
        "secondary": cleaned_secondary,
        "confidence": token_category.get("confidence"),
        "rationale": "DDQ category did not match known mappings; defaulted to 'other'.",
    }


def human_token_type_label(token_type: str) -> str:
    """Human label for report output."""
    mapping = {
        "native_l1": "Native Layer-1 network token",
        "native_l2": "Native Layer-2 network token",
        "defi": "DeFi protocol token",
        "memecoin": "Memecoin",
        "stablecoin_fiat": "Stablecoin (reserve/fiat-backed)",
        "stablecoin_algorithmic": "Stablecoin (algorithmic)",
        "wrapped": "Wrapped token",
        "security_token": "Security / tokenised asset",
        "governance": "Governance token",
        "utility": "Utility token",
        "governance_utility": "Governance & utility token",
        "other": "Other / unclassified",
    }
    return mapping.get(token_type, token_type)
