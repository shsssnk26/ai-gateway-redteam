import json
from pathlib import Path
from typing import Any, Protocol, TextIO

from ai_gateway_redteam.reporting.report import Entry, Report


class Reporter(Protocol):
    """Writes a finished report somewhere. Never modifies the report."""

    def write(self, report: Report) -> None:
        """Write the report to this reporter's destination"""
        ...


class TextReporter:
    """One line per case, the reason behind every check that did not pass, then a summary."""

    def __init__(self, stream: TextIO, verbose: bool = False) -> None:
        self._stream = stream
        self._verbose = verbose

    def write(self, report: Report) -> None:
        id_width = max((len(entry.case.id) for entry in report.entries), default=0) + 2
        for entry in report.entries:
            self._write_entry(entry, id_width)
        counts = report.counts()
        self._stream.write(
            f"\n{len(report.entries)} case(s) against {report.gateway_url}: "
            f"{counts['PASS']} passed, {counts['FAIL']} failed, {counts['ERROR']} error(s)\n"
        )

    def _write_entry(self, entry: Entry, id_width: int) -> None:
        case, result = entry.case, entry.result
        self._stream.write(f"{result.verdict:<6}{case.id:<{id_width}}{case.severity:<10}{case.title}\n")
        for check in result.checks:
            if self._verbose or check.verdict != "PASS":
                self._stream.write(f"{'':6}{check.verdict:<6}{check.check}: {check.reason}\n")


class JsonReporter:
    """The whole report as JSON at a path, for CI and later comparison."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, report: Report) -> None:
        self._path.write_text(json.dumps(self.to_dict(report), indent=2) + "\n")

    @staticmethod
    def to_dict(report: Report) -> dict[str, Any]:
        return {
            "gateway_url": report.gateway_url,
            "verdict": report.verdict(),
            "summary": report.counts(),
            "results": [
                {
                    "id": entry.case.id,
                    "title": entry.case.title,
                    "category": entry.case.category,
                    "severity": entry.case.severity,
                    "verdict": entry.result.verdict,
                    "checks": [
                        {"check": check.check, "verdict": check.verdict, "reason": check.reason}
                        for check in entry.result.checks
                    ],
                }
                for entry in report.entries
            ],
        }
