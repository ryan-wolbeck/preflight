"""
Suppression model and loader.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path

from preflight.model.finding import Finding


@dataclass(frozen=True)
class Suppression:
    check_id: str
    column: str | None = None
    expires: date | None = None
    reason: str = ""

    def matches(self, finding: Finding) -> bool:
        if finding.check_id != self.check_id:
            return False
        if self.column is None:
            return True
        return self.column in finding.affected_columns

    def is_expired(self, today: date | None = None) -> bool:
        if self.expires is None:
            return False
        current = today or date.today()
        return self.expires < current


def load_suppressions(path: str | None) -> list[Suppression]:
    if path is None:
        return []
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Suppressions file must be a JSON array.")
    out: list[Suppression] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        check_id = item.get("check_id")
        if not isinstance(check_id, str) or not check_id:
            continue
        col = item.get("column")
        if col is not None and not isinstance(col, str):
            col = None
        expires_raw = item.get("expires")
        expires_date: date | None = None
        if isinstance(expires_raw, str):
            expires_date = date.fromisoformat(expires_raw)
        reason = item.get("reason")
        if not isinstance(reason, str):
            reason = ""
        out.append(Suppression(check_id=check_id, column=col, expires=expires_date, reason=reason))
    return out
