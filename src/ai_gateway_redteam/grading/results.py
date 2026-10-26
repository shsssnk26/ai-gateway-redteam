from dataclasses import dataclass
from typing import Literal

Verdict = Literal["PASS", "FAIL", "ERROR"]


@dataclass(frozen=True)
class CheckResult:
    """The verdict of one check in a case's expect block."""

    check: str
    verdict: Verdict
    reason: str


@dataclass(frozen=True)
class CaseResult:
    """The overall verdict for one case, with the result of each check behind it."""

    case_id: str
    verdict: Verdict
    checks: tuple[CheckResult, ...]