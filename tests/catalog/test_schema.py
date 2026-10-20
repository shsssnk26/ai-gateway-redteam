import pytest
from pydantic import ValidationError

from ai_gateway_redteam.catalog.schema import Case, Expect, Request

from .conftest import chat_case_data, http_case_data


class TestRequest:
    def test_defaults(self):
        request = Request(method="GET", url="http://x")
        assert request.headers == {}
        assert request.body is None

    def test_rejects_unknown_method(self):
        with pytest.raises(ValidationError):
            Request(method="DELETE", url="http://x")

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            Request(method="GET", url="http://x", timeout=5)


class TestExpect:
    @pytest.mark.parametrize("check", [
        {"status": 401},
        {"connection": "unreachable"},
        {"must_not_contain": ["a"]},
        {"must_not_contain_digits": ["123"]},
        {"must_not_contain_ignoring_whitespace": ["a b"]},
    ])
    def test_accepts_any_single_check(self, check):
        Expect(**check)

    def test_requires_at_least_one_check(self):
        with pytest.raises(ValidationError, match="at least one non-empty check"):
            Expect()

    @pytest.mark.parametrize("name", [
        "must_not_contain",
        "must_not_contain_digits",
        "must_not_contain_ignoring_whitespace",
    ])
    def test_rejects_empty_string_list_alongside_other_check(self, name):
        with pytest.raises(ValidationError, match=f"{name} is empty"):
            Expect(status=200, **{name: []})

    def test_rejects_unknown_connection_value(self):
        with pytest.raises(ValidationError):
            Expect(connection="reachable")

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            Expect(status=200, must_contain=["x"])


class TestCase:
    def test_valid_http_case(self):
        case = Case.model_validate(http_case_data(ports=[8081, 8082]))
        assert case.request.method == "GET"
        assert case.ports == [8081, 8082]
        assert case.transforms == []

    def test_valid_chat_case(self):
        case = Case.model_validate(chat_case_data(seed="x", transforms=["dots"]))
        assert case.model == "frontier"
        assert case.transforms == ["dots"]

    def test_http_case_requires_request(self):
        with pytest.raises(ValidationError, match="kind 'http' needs a request"):
            Case.model_validate(http_case_data(request=None))

    @pytest.mark.parametrize("missing", ["model", "prompt"])
    def test_chat_case_requires_model_and_prompt(self, missing):
        data = chat_case_data()
        del data[missing]
        with pytest.raises(ValidationError, match="kind 'chat' needs a model and a prompt"):
            Case.model_validate(data)

    def test_transforms_require_seed(self):
        with pytest.raises(ValidationError, match="transforms need a seed"):
            Case.model_validate(chat_case_data(transforms=["dots"]))

    @pytest.mark.parametrize("field, value", [
        ("category", "unknown"),
        ("severity", "urgent"),
        ("kind", "grpc"),
    ])
    def test_rejects_invalid_literals(self, field, value):
        with pytest.raises(ValidationError):
            Case.model_validate(chat_case_data(**{field: value}))

    @pytest.mark.parametrize("field", ["id", "title", "category", "severity", "kind", "expect"])
    def test_rejects_missing_required_field(self, field):
        data = chat_case_data()
        del data[field]
        with pytest.raises(ValidationError):
            Case.model_validate(data)

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            Case.model_validate(chat_case_data(owner="me"))

    def test_ports_rejected_on_chat_case(self):
        with pytest.raises(ValidationError, match="ports are only allowed for http cases"):
            Case.model_validate(chat_case_data(ports=[8081]))

    @pytest.mark.parametrize("extra", [
        {"seed": "5125550198"},
        {"seed": ""},  # an empty seed still makes SeedExpander apply
        {"seed": "5125550198", "transforms": ["dots"]},
    ])
    def test_seed_and_transforms_rejected_on_http_case(self, extra):
        with pytest.raises(ValidationError, match="only valid for chat cases"):
            Case.model_validate(http_case_data(**extra))

    def test_transforms_without_seed_on_http_case_still_rejected(self):
        with pytest.raises(ValidationError, match="transforms need a seed"):
            Case.model_validate(http_case_data(transforms=["dots"]))

    def test_ports_and_transforms_cannot_be_combined(self):
        with pytest.raises(ValidationError):
            Case.model_validate(chat_case_data(seed="x", transforms=["dots"], ports=[8081]))
        with pytest.raises(ValidationError):
            Case.model_validate(http_case_data(seed="x", transforms=["dots"], ports=[8081]))

    def test_invalid_nested_expect_fails_case(self):
        with pytest.raises(ValidationError):
            Case.model_validate(chat_case_data(expect={}))
