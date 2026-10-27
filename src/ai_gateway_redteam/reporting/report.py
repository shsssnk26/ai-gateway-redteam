from collections import Counter
from dataclasses import dataclass

from ai_gateway_redteam.catalog.schema import Case
from ai_gateway_redteam.grading.results import CaseResult, Verdict

VERDICTS: tuple[Verdict, ...] = ("PASS", "FAIL", "ERROR")


@dataclass(frozen=True)
class Entry:
    """One case next to the result it got."""

    case: Case
    result: CaseResult


@dataclass(frozen=True)
class Report:
    """Everything a reporter needs about one run. Never holds the API key."""

    gateway_url: str
    entries: tuple[Entry, ...]

    @classmethod
    def from_results(cls, gateway_url: str, cases: list[Case], results: list[CaseResult]) -> "Report":
        """Pair cases with results; both lists come from the grader in the same order"""
        entries = []
        for case, result in zip(cases, results, strict=True):
            if case.id != result.case_id:
                raise ValueError(f"result {result.case_id} does not belong to case {case.id}")
            entries.append(Entry(case, result))
        return cls(gateway_url, tuple(entries))

    def counts(self) -> dict[Verdict, int]:
        """How many cases got each verdict, with every verdict present"""
        counted = Counter(entry.result.verdict for entry in self.entries)
        return {verdict: counted[verdict] for verdict in VERDICTS}

    def verdict(self) -> Verdict:
        """FAIL if anything leaked, ERROR if anything proved nothing, otherwise PASS"""
        counts = self.counts()
        if counts["FAIL"]:
            return "FAIL"
        if counts["ERROR"] or not self.entries:
            return "ERROR"
        return "PASS"
