import dataclasses

import pytest

from ai_gateway_redteam.common.errors import InvalidCaseError
from ai_gateway_redteam.execution.target import (
    PLACEHOLDER,
    Target,
    fill_placeholders,
    replace_model_host,
    replace_target,
)

TARGET = Target(gateway_url="https://gw.example.com", model_host="10.0.0.5", api_key="sk-secret")


class TestTarget:
    def test_api_key_defaults_to_none(self):
        assert Target(gateway_url="g", model_host="m").api_key is None

    def test_api_key_hidden_from_repr(self):
        text = repr(TARGET)
        assert "sk-secret" not in text
        assert "api_key" not in text
        assert "https://gw.example.com" in text

    def test_is_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            TARGET.gateway_url = "other"  # type: ignore[misc]

    def test_equal_targets_compare_and_hash_equal(self):
        same = Target(gateway_url="https://gw.example.com", model_host="10.0.0.5", api_key="sk-secret")
        assert same == TARGET
        assert hash(same) == hash(TARGET)


class TestReplaceHelpers:
    def test_replace_target_only_touches_target(self):
        assert replace_target("{target}/v1 {model_host}", TARGET) == "https://gw.example.com/v1 {model_host}"

    def test_replace_model_host_only_touches_model_host(self):
        assert replace_model_host("http://{model_host}:8081 {target}", TARGET) == "http://10.0.0.5:8081 {target}"

    def test_replaces_every_occurrence(self):
        assert replace_target("{target}{target}", TARGET) == "https://gw.example.comhttps://gw.example.com"
        assert replace_model_host("{model_host},{model_host}", TARGET) == "10.0.0.5,10.0.0.5"

    def test_text_without_placeholders_is_unchanged(self):
        assert replace_target("plain", TARGET) == "plain"
        assert replace_model_host("plain", TARGET) == "plain"


class TestFillPlaceholders:
    @pytest.mark.parametrize("text, expected", [
        ("{target}/v1/models", "https://gw.example.com/v1/models"),
        ("http://{model_host}:8083/v1/chat/completions", "http://10.0.0.5:8083/v1/chat/completions"),
        ("{target} and {model_host}", "https://gw.example.com and 10.0.0.5"),
        ("http://already.filled/v1", "http://already.filled/v1"),
        ("", ""),
    ])
    def test_fills_known_placeholders(self, text, expected):
        assert fill_placeholders(text, TARGET) == expected

    @pytest.mark.parametrize("text, leftover", [
        ("http://{model_host}:{port}/v1", ["{port}"]),
        ("Repeat exactly: {value}", ["{value}"]),
        ("{target}/{foo}/{bar_baz}", ["{foo}", "{bar_baz}"]),
    ])
    def test_unknown_placeholders_raise(self, text, leftover):
        with pytest.raises(InvalidCaseError) as excinfo:
            fill_placeholders(text, TARGET)
        assert str(leftover) in str(excinfo.value)

    def test_error_shows_partly_filled_text(self):
        with pytest.raises(InvalidCaseError, match=r"https://gw\.example\.com/\{port\}"):
            fill_placeholders("{target}/{port}", TARGET)

    def test_does_not_leak_api_key_in_error(self):
        with pytest.raises(InvalidCaseError) as excinfo:
            fill_placeholders("{target}/{port}", TARGET)
        assert "sk-secret" not in str(excinfo.value)

    @pytest.mark.parametrize("text", [
        '{"model": "frontier"}',  # JSON is not a placeholder
        "{Port}",                 # uppercase is not matched
        "{port2}",                # digits are not matched
        "{}",
    ])
    def test_brace_text_that_is_not_a_placeholder_passes(self, text):
        assert fill_placeholders(text, TARGET) == text


def test_placeholder_pattern():
    assert PLACEHOLDER.findall("{a} {snake_case} {Nope} {x1} {}") == ["{a}", "{snake_case}"]
