"""Quarter bucketing rules for roadmap feature requests."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

STATE_ORDER = {
    "OPEN": 0, "TRIAGED": 1, "BRANCHED": 2, "IN_PROGRESS": 3,
    "CHANGES_REQUESTED": 3, "FUNCTIONAL_QA": 4, "ARCHITECTURE_REVIEW": 5,
    "REVIEW_REQUESTED": 6, "AUTO_REVIEWED": 7, "TYLER_APPROVED": 8,
    "BRANCH_CHECKED_OUT": 8, "SOAKING": 9, "MERGED": 9,
}
RISK_WEIGHT = {"low": 0, "medium": 1, "high": 2}


def current_quarter(today: date | None = None) -> str:
    today = today or date.today()
    return f"{today.year}-Q{(today.month - 1) // 3 + 1}"


def add_quarters(quarter_str: str, n: int) -> str:
    year_str, q_str = quarter_str.split("-Q")
    total = int(year_str) * 4 + int(q_str) - 1 + n
    year, quarter = divmod(total, 4)
    return f"{year}-Q{quarter + 1}"


def _age_days(opened_at: str | None, today: date) -> int:
    if not opened_at:
        return 0
    try:
        opened = datetime.strptime(opened_at[:10], "%Y-%m-%d").date()
    except ValueError:
        return 0
    return max(0, (today - opened).days)


def assign_quarter(fr: dict[str, Any], today: date | None = None) -> str:
    """Assign a target quarter using override and lifecycle heuristics."""
    override = fr.get("target_quarter")
    if override:
        return override
    today = today or date.today()
    bucket = 1
    bucket += RISK_WEIGHT.get((fr.get("risk") or "medium").lower(), 1) - 1
    state_order = STATE_ORDER.get((fr.get("state") or "OPEN").upper(), 0)
    if state_order >= 4:
        bucket -= 1
    elif state_order <= 1:
        bucket += 1
    age = _age_days(fr.get("opened_at"), today)
    if age >= 60:
        bucket -= 1
    elif age < 14:
        bucket += 1
    return add_quarters(current_quarter(today), max(0, min(3, bucket)))