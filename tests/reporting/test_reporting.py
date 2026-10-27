import io
import json

import pytest

from ai_gateway_redteam.catalog.schema import Case
from ai_gateway_redteam.grading.results import CaseResult, CheckResult
from ai_gateway_redteam.reporting.report import Report
from ai_gateway_redteam.reporting.reporters import JsonReporter, TextReporter

GATEWAY = "http://gw.test:4000"


def case(case_id: str, title: str = "t") -> Case:
    return Case.model_validate({
        "id": case_id,
        "title": title,
        "category": "authentication",
        "severity": "high",
        "kind": "http",
        "request": {"method": "GET", "url": "{target}/v1/models"},
        "expect": {"status": 401},
    })


def result(case_id: str, verdict: str, reason: str = "r") -> CaseResult:
    return CaseResult(case_id, verdict, (CheckResult("status", verdict, reason),))


def report(*verdicts: str) -> Report:
    ids = [f"C-{i}" for i in range(len(verdicts))]
    return Report.from_results(GATEWAY, [case(i) for i in ids], [result(i, v) for i, v in zip(ids, verdicts)])


class TestReport:
    def test_counts_every_verdict(self):
        assert report("PASS", "FAIL", "PASS").counts() == {"PASS": 2, "FAIL": 1, "ERROR": 0}

    @pytest.mark.parametrize("verdicts, expected", [
        (("PASS", "PASS"), "PASS"),
        (("PASS", "ERROR"), "ERROR"),
        (("ERROR", "FAIL"), "FAIL"),
        ((), "ERROR"),
    ])
    def test_verdict(self, verdicts, expected):
        assert report(*verdicts).verdict() == expected

    def test_mismatched_result_raises(self):
        with pytest.raises(ValueError, match="does not belong"):
            Report.from_results(GATEWAY, [case("A")], [result("B", "PASS")])

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            Report.from_results(GATEWAY, [case("A"), case("B")], [result("A", "PASS")])


class TestTextReporter:
    def write(self, report: Report, verbose: bool = False) -> str:
        stream = io.StringIO()
        TextReporter(stream, verbose).write(report)
        return stream.getvalue()

    def test_one_line_per_case_and_summary(self):
        out = self.write(report("PASS", "FAIL"))
        assert "PASS  C-0" in out
        assert "FAIL  C-1" in out
        assert f"2 case(s) against {GATEWAY}: 1 passed, 1 failed, 0 error(s)" in out

    def test_reason_shown_only_for_checks_that_did_not_pass(self):
        r = Report.from_results(
            GATEWAY, [case("A"), case("B")], [result("A", "PASS", "fine"), result("B", "FAIL", "leaked x")]
        )
        out = self.write(r)
        assert "status: leaked x" in out
        assert "fine" not in out

    def test_long_ids_keep_columns_apart(self):
        long_id = "PII-002-fullwidth_characters"
        r = Report.from_results(GATEWAY, [case(long_id)], [result(long_id, "PASS")])
        assert f"{long_id}  high" in self.write(r)

    def test_verbose_shows_passing_reasons(self):
        assert "status: r" in self.write(report("PASS"), verbose=True)


class TestJsonReporter:
    def test_writes_summary_and_every_check(self, tmp_path):
        path = tmp_path / "report.json"
        JsonReporter(path).write(report("PASS", "ERROR"))
        data = json.loads(path.read_text())
        assert data["gateway_url"] == GATEWAY
        assert data["verdict"] == "ERROR"
        assert data["summary"] == {"PASS": 1, "FAIL": 0, "ERROR": 1}
        assert [r["id"] for r in data["results"]] == ["C-0", "C-1"]
        assert data["results"][1]["checks"] == [{"check": "status", "verdict": "ERROR", "reason": "r"}]
