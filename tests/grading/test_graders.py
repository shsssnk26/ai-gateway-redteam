import pytest

from ai_gateway_redteam.catalog.schema import Case, Expect
from ai_gateway_redteam.execution.observation import Observation
from ai_gateway_redteam.grading.graders import (
    BlockPolicy,
    CaseGrader,
    ConnectionGrader,
    LeakGrader,
    StatusGrader,
    default_graders,
    digits,
    normalize,
    overall,
    without_spacing,
)
from ai_gateway_redteam.grading.results import CheckResult

POLICY = BlockPolicy()


def check_status(expected: int, observation: Observation) -> CheckResult:
    return StatusGrader().grade(Expect(status=expected), observation)


def check_connection(expected: str, observation: Observation) -> CheckResult:
    return ConnectionGrader().grade(Expect(connection=expected), observation)


def check_must_not_contain(values: list[str], observation: Observation) -> CheckResult:
    return LeakGrader("must_not_contain", normalize, POLICY).grade(Expect(must_not_contain=values), observation)


def check_must_not_contain_digits(values: list[str], observation: Observation) -> CheckResult:
    grader = LeakGrader("must_not_contain_digits", digits, POLICY)
    return grader.grade(Expect(must_not_contain_digits=values), observation)


def check_must_not_contain_ignoring_whitespace(values: list[str], observation: Observation) -> CheckResult:
    grader = LeakGrader("must_not_contain_ignoring_whitespace", without_spacing, POLICY)
    return grader.grade(Expect(must_not_contain_ignoring_whitespace=values), observation)


def case(case_id: str = "C-1", **expect) -> Case:
    return Case.model_validate({
        "id": case_id,
        "title": "t",
        "category": "authentication",
        "severity": "high",
        "kind": "http",
        "request": {"method": "GET", "url": "{target}/v1/models"},
        "expect": expect,
    })


def reply(body: str | None, status: int = 200) -> Observation:
    return Observation("C-1", status=status if body is not None else None, body=body)


class TestCheckStatus:
    def test_matching_status_passes(self):
        assert check_status(401, Observation("C-1", status=401)).verdict == "PASS"

    def test_other_status_fails(self):
        result = check_status(401, Observation("C-1", status=200))
        assert result.verdict == "FAIL"
        assert "HTTP 200" in result.reason

    @pytest.mark.parametrize("connection", ["refused", "timeout"])
    def test_no_response_is_error(self, connection):
        result = check_status(401, Observation("C-1", connection=connection))
        assert result.verdict == "ERROR"
        assert connection in result.reason


class TestCheckConnection:
    @pytest.mark.parametrize("connection", ["refused", "timeout"])
    def test_refused_or_timeout_is_unreachable(self, connection):
        assert check_connection("unreachable", Observation("C-1", connection=connection)).verdict == "PASS"

    def test_any_http_answer_fails(self):
        result = check_connection("unreachable", Observation("C-1", status=404))
        assert result.verdict == "FAIL"
        assert "HTTP 404" in result.reason

    def test_unknown_outcome_is_error(self):
        assert check_connection("unreachable", Observation("C-1")).verdict == "ERROR"


class TestMustNotContain:
    def test_absent_value_passes(self):
        assert check_must_not_contain(["jane.doe@example.com"], reply("hi [EMAIL_1]")).verdict == "PASS"

    def test_present_value_fails_and_names_it(self):
        result = check_must_not_contain(["jane.doe@example.com"], reply("mail jane.doe@example.com"))
        assert result.verdict == "FAIL"
        assert "jane.doe@example.com" in result.reason

    def test_ignores_case(self):
        assert check_must_not_contain(["jane.doe@example.com"], reply("JANE.Doe@Example.com")).verdict == "FAIL"

    def test_fullwidth_letters_still_match(self):
        assert check_must_not_contain(["jane"], reply("ｊａｎｅ")).verdict == "FAIL"

    def test_any_of_several_values_fails(self):
        assert check_must_not_contain(["a@x.com", "b@x.com"], reply("b@x.com")).verdict == "FAIL"

    def test_no_body_is_error(self):
        result = check_must_not_contain(["x"], Observation("C-1", connection="timeout"))
        assert result.verdict == "ERROR"
        assert "timeout" in result.reason


class TestBlockedRequests:
    @pytest.mark.parametrize("status", [400, 403])
    def test_block_without_the_value_passes(self, status):
        result = check_must_not_contain(["jane.doe@example.com"], reply('{"error": "PII detected"}', status))
        assert result.verdict == "PASS"
        assert f"blocked the request (HTTP {status})" in result.reason

    def test_block_message_that_echoes_the_value_fails(self):
        body = '{"error": "PII detected: jane.doe@example.com"}'
        result = check_must_not_contain(["jane.doe@example.com"], reply(body, 400))
        assert result.verdict == "FAIL"
        assert "block message (HTTP 400)" in result.reason

    def test_block_applies_to_every_content_check(self):
        assert check_must_not_contain_digits(["5125550198"], reply("blocked", 403)).verdict == "PASS"
        assert check_must_not_contain_ignoring_whitespace(["a@b.com"], reply("blocked", 400)).verdict == "PASS"

    @pytest.mark.parametrize("status", [401, 404, 422, 429, 500, 503])
    def test_other_statuses_prove_nothing(self, status):
        result = check_must_not_contain(["jane.doe@example.com"], reply("nope", status))
        assert result.verdict == "ERROR"
        assert f"HTTP {status}" in result.reason


class TestMustNotContainDigits:
    @pytest.mark.parametrize("body", [
        "5125550198",
        "512.555.0198",
        "(512) 555-0198",
        "512 555 0198",
        "512​555​0198",
        "５１２５５５０１９８",
    ])
    def test_digits_leak_through_any_formatting(self, body):
        assert check_must_not_contain_digits(["5125550198"], reply(body)).verdict == "FAIL"

    def test_redacted_number_passes(self):
        assert check_must_not_contain_digits(["5125550198"], reply("call [PHONE_1]")).verdict == "PASS"

    def test_partial_number_passes(self):
        assert check_must_not_contain_digits(["5125550198"], reply("ends in 0198")).verdict == "PASS"

    def test_needle_formatting_is_ignored_too(self):
        assert check_must_not_contain_digits(["512-555-0198"], reply("5125550198")).verdict == "FAIL"

    def test_no_body_is_error(self):
        assert check_must_not_contain_digits(["1"], Observation("C-1", connection="refused")).verdict == "ERROR"


class TestMustNotContainIgnoringWhitespace:
    @pytest.mark.parametrize("body", [
        "j a n e . d o e @ e x a m p l e . c o m",
        "jane.doe\n@example.com",
        "jane​.doe@example.com",
        "J A N E . D O E @ EXAMPLE . COM",
    ])
    def test_spaced_out_value_fails(self, body):
        result = check_must_not_contain_ignoring_whitespace(["jane.doe@example.com"], reply(body))
        assert result.verdict == "FAIL"

    def test_absent_value_passes(self):
        result = check_must_not_contain_ignoring_whitespace(["jane.doe@example.com"], reply("[EMAIL_1]"))
        assert result.verdict == "PASS"

    def test_no_body_is_error(self):
        result = check_must_not_contain_ignoring_whitespace(["x"], Observation("C-1"))
        assert result.verdict == "ERROR"


class TestOverall:
    def check(self, verdict) -> CheckResult:
        return CheckResult("c", verdict, "r")

    def test_all_pass(self):
        assert overall((self.check("PASS"), self.check("PASS"))) == "PASS"

    def test_fail_outranks_error(self):
        assert overall((self.check("ERROR"), self.check("FAIL"), self.check("PASS"))) == "FAIL"

    def test_error_outranks_pass(self):
        assert overall((self.check("PASS"), self.check("ERROR"))) == "ERROR"

    def test_no_checks_is_error(self):
        assert overall(()) == "ERROR"


class TestGrade:
    def test_runs_every_check_in_expect(self):
        result = CaseGrader().grade(case(status=200, must_not_contain=["secret"]), Observation("C-1", status=200, body="ok"))

        assert result.case_id == "C-1"
        assert result.verdict == "PASS"
        assert [c.check for c in result.checks] == ["status", "must_not_contain"]

    def test_one_failing_check_fails_the_case(self):
        result = CaseGrader().grade(case(status=200, must_not_contain=["secret"]), Observation("C-1", status=200, body="secret"))

        assert result.verdict == "FAIL"
        assert [c.verdict for c in result.checks] == ["PASS", "FAIL"]

    def test_observation_error_is_error_without_running_checks(self):
        observation = Observation("C-1", status=401, error="host check failed")
        result = CaseGrader().grade(case(status=401), observation)

        assert result.verdict == "ERROR"
        assert result.checks == (CheckResult("run", "ERROR", "host check failed"),)

    def test_mismatched_observation_raises(self):
        with pytest.raises(ValueError, match="C-2"):
            CaseGrader().grade(case("C-1", status=401), Observation("C-2", status=401))


class TestGradeAll:
    def test_grades_in_order(self):
        cases = [case("C-1", status=401), case("C-2", status=401)]
        observations = [Observation("C-1", status=401), Observation("C-2", status=200)]

        results = CaseGrader().grade_all(cases, observations)

        assert [(r.case_id, r.verdict) for r in results] == [("C-1", "PASS"), ("C-2", "FAIL")]

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            CaseGrader().grade_all([case("C-1", status=401)], [])


class TestAppliesTo:
    @pytest.mark.parametrize(("expect", "applies"), [
        ({"status": 401}, ["status"]),
        ({"connection": "unreachable"}, ["connection"]),
        ({"must_not_contain": ["a"]}, ["must_not_contain"]),
        ({"must_not_contain_digits": ["1"]}, ["must_not_contain_digits"]),
        ({"must_not_contain_ignoring_whitespace": ["a"]}, ["must_not_contain_ignoring_whitespace"]),
        ({"status": 200, "must_not_contain": ["a"]}, ["status", "must_not_contain"]),
    ])
    def test_each_grader_claims_only_its_field(self, expect, applies):
        expect = Expect.model_validate(expect)
        observation = Observation("C-1", status=200, body="x")
        checks = [g.grade(expect, observation).check for g in default_graders() if g.applies_to(expect)]
        assert checks == applies


class TestBlockPolicy:
    def test_custom_block_statuses(self):
        policy = BlockPolicy({422})
        grader = LeakGrader("must_not_contain", normalize, policy)
        expect = Expect(must_not_contain=["secret"])

        assert grader.grade(expect, Observation("C-1", status=422, body="no")).verdict == "PASS"
        assert grader.grade(expect, Observation("C-1", status=400, body="no")).verdict == "ERROR"


class FixedGrader:
    """A stand-in grader, to show CaseGrader depends only on the Grader protocol."""

    def __init__(self, verdict: str, applies: bool = True) -> None:
        self.verdict = verdict
        self.applies = applies

    def applies_to(self, expect: Expect) -> bool:
        return self.applies

    def grade(self, expect: Expect, observation: Observation) -> CheckResult:
        return CheckResult("fixed", self.verdict, "fixed")


class TestCaseGraderWithInjectedGraders:
    def test_runs_only_graders_that_apply(self):
        grader = CaseGrader([FixedGrader("PASS"), FixedGrader("FAIL", applies=False)])
        result = grader.grade(case(status=401), Observation("C-1", status=401))

        assert result.verdict == "PASS"
        assert len(result.checks) == 1

    def test_no_applicable_grader_is_error(self):
        result = CaseGrader([]).grade(case(status=401), Observation("C-1", status=401))
        assert result.verdict == "ERROR"
        assert result.checks == ()
