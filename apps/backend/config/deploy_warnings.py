"""
Deployment-check warning classifier — SBGC-43.

Classifies Django check --deploy output lines against an accepted
warning-ID allowlist.  Used by scripts/backend-deploy-check.sh and
testable independently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Match warning IDs like "security.W005" or "caches.W001".
_WARNING_ID_RE = re.compile(r"\(([a-zA-Z][a-zA-Z0-9]*\.W\d+)\)")


@dataclass
class ClassifiedWarning:
    """One classified warning line."""

    warning_id: str
    line: str
    accepted: bool


@dataclass
class CheckResult:
    """Result of classifying check --deploy output."""

    accepted: list[ClassifiedWarning] = field(default_factory=list)
    unexpected: list[ClassifiedWarning] = field(default_factory=list)
    other_lines: list[str] = field(default_factory=list)

    @property
    def has_unexpected(self) -> bool:
        return len(self.unexpected) > 0


def classify_warnings(output: str, accepted_ids: set[str]) -> CheckResult:
    """
    Classify each warning line in *output* against *accepted_ids*.

    Args:
        output: Raw stdout/stderr from ``manage.py check --deploy``.
        accepted_ids: Set of warning IDs (e.g. ``{"security.W005"}``)
            that are permitted.

    Returns:
        A ``CheckResult`` with classified warnings.
    """
    result = CheckResult()
    for line in output.splitlines():
        m = _WARNING_ID_RE.search(line)
        if m:
            wid = m.group(1)
            cw = ClassifiedWarning(
                warning_id=wid, line=line, accepted=wid in accepted_ids
            )
            if cw.accepted:
                result.accepted.append(cw)
            else:
                result.unexpected.append(cw)
        else:
            result.other_lines.append(line)
    return result
