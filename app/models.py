from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class DomainStats:
    """
    Domain-level risk stats pulled from the Master_Summary sheet.
    """
    code: str
    name: str
    weight: float
    avg_score: float
    band_name: str
    band_numeric: int
    has_board_escalation: bool
    board_escalation_count: int


@dataclass
class BoardEscalation:
    """
    A single row from a domain sheet where Board_Escalation_Flag is set
    (including 'No Review' informational narratives).
    """
    id: str
    domain_code: str
    domain_name: str
    question_id: str
    question_text: str
    flag: str
    trigger_rule: Optional[str]
    raw_narrative: Optional[str]
    most_recent_source_date: Optional[str]
    staleness_class: Optional[str]
    citations: List[Dict[str, str]]
