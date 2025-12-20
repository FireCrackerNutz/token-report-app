from __future__ import annotations

"""Signal extraction and response normalisation helpers.

This module turns raw DDQ rows into normalised, queryable "signals" that the
deterministic inference layer can reason about.

Key idea:
  - Detect objective *features* and *control quality* indicators.
  - Avoid naive "keyword -> risk" tagging.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .ddq_question_registry import SignalSource, get_sources


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


def _norm(x: Any) -> str:
    return str(x or "").strip()


def _norm_low(x: Any) -> str:
    return _norm(x).lower()


def normalise_raw_response(raw: Any) -> str:
    """Normalise semi-consistent DDQ responses into a small set of buckets.

    Buckets:
      - yes / no
      - partial (mixed/limited/partially/etc.)
      - unknown (unknown/unclear/not disclosed/etc.)
      - na
      - other (free text, numbers, narratives)
    """
    s = _norm_low(raw)
    if not s:
        return "unknown"

    # N/A
    if s in {"n/a", "na", "not applicable", "not-applicable"}:
        return "na"

    # Common unknowns
    if any(k in s for k in ["unknown", "unclear", "not disclosed", "not provided", "tbc", "to be confirmed"]):
        return "unknown"

    # Explicit yes/no
    if s in {"yes", "y", "true"}:
        return "yes"
    if s.startswith("yes"):
        return "yes"
    if s in {"no", "n", "false"}:
        return "no"
    if s.startswith("no"):
        return "no"
    
    # Common "none" phrasing that should behave like "no"
    if s in {"none disclosed", "none identified", "none reported", "none known"}:
        return "no"
    if s.startswith("none disclosed") or s.startswith("none identified"):
        return "no"

    # Partial / mixed
    if any(k in s for k in ["partial", "partially", "mixed", "limited", "some", "in part", "incomplete"]):
        return "partial"

    return "other"


def confidence_rank(conf: Any) -> int:
    c = _norm_low(conf)
    if c.startswith("high"):
        return 3
    if c.startswith("medium"):
        return 2
    if c.startswith("low"):
        return 1
    if c in {"unknown", ""}:
        return 0
    return 0


def parse_float_from_text(x: Any) -> Optional[float]:
    """Extract a numeric value from inputs like '41.7', '41.7%', '≥4', '<12 months'."""
    s = _norm_low(x)
    if not s:
        return None

    # Common symbolic buckets
    if s.startswith("≥") or s.startswith(">="):
        m = re.findall(r"\d+(?:\.\d+)?", s)
        return float(m[0]) if m else None
    if s.startswith("<"):
        m = re.findall(r"\d+(?:\.\d+)?", s)
        return float(m[0]) if m else None

    m = re.findall(r"\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m[0])
    except Exception:
        return None


def has_negative_cues(text: str) -> bool:
    t = (text or "").lower()
    return any(
        k in t
        for k in [
            "unclear",
            "unknown",
            "not disclosed",
            "not provided",
            "cannot confirm",
            "no evidence",
            "insufficient",
            "incomplete",
            "fallback error",
        ]
    )


# ---------------------------------------------------------------------------
# Answer selection
# ---------------------------------------------------------------------------


def _answers_by_key(parsed_ddq: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    return (parsed_ddq.get("answers_by_key") or {})  # keyed by "<sheet>::<QID>"


def _key(sheet: str, qid: str) -> str:
    return f"{sheet}::{(qid or '').strip().upper()}"


def best_answer_for_question(
    parsed_ddq: Dict[str, Any],
    sheet: str,
    question_ids: Sequence[str],
) -> Optional[Dict[str, Any]]:
    """Pick the best answer row across one or more candidate QIDs in a sheet."""
    by_key = _answers_by_key(parsed_ddq)
    candidates: List[Dict[str, Any]] = []
    for qid in question_ids:
        rows = by_key.get(_key(sheet, qid), [])
        candidates.extend(rows)
    if not candidates:
        return None

    def score(a: Dict[str, Any]) -> Tuple[int, int, int]:
        conf = confidence_rank(a.get("confidence"))
        has_cit = 1 if (a.get("source_citations") or []) else 0
        has_narr = 1 if _norm(a.get("narrative_justification")) else 0
        return (conf, has_cit, has_narr)

    return sorted(candidates, key=score, reverse=True)[0]


@dataclass
class SignalAnswer:
    signal: str
    sheet: str
    question_id: str
    raw_response: str
    response_norm: str
    confidence: str
    narrative: str
    citations: List[str]
    numeric: Optional[float]


def get_signal_answer(parsed_ddq: Dict[str, Any], signal_name: str) -> Optional[SignalAnswer]:
    """Resolve a signal to the best matching DDQ answer, using the registry."""
    sources: List[SignalSource] = get_sources(signal_name)
    for src in sources:
        ans = best_answer_for_question(parsed_ddq, src.sheet, src.question_ids)
        if not ans:
            continue
        raw = _norm(ans.get("raw_response"))
        return SignalAnswer(
            signal=signal_name,
            sheet=src.sheet,
            question_id=_norm(ans.get("question_id")),
            raw_response=raw,
            response_norm=normalise_raw_response(raw),
            confidence=_norm(ans.get("confidence")),
            narrative=_norm(ans.get("narrative_justification")),
            citations=[_norm(c) for c in (ans.get("source_citations") or []) if _norm(c)],
            numeric=parse_float_from_text(raw),
        )
    return None


def signal_missing(parsed_ddq: Dict[str, Any], signal_name: str) -> bool:
    return get_signal_answer(parsed_ddq, signal_name) is None
