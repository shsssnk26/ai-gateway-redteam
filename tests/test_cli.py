import json
from pathlib import Path

import httpx
import pytest

from ai_gateway_redteam.cli import API_KEY_ENV, main

CASES = Path(__file__).parent.parent / "cases" / "gateway.yaml"
GATEWAY = "http://gw.test:4000"


def refused() -> httpx.ConnectError:
    error = httpx.ConnectError("refused")
    error.__cause__ = ConnectionRefusedError()
    return error


def network(chat_reply: str = "[EMAIL_1]", calls: list | None = None) -> httpx.MockTransport:
    """A locked-down gateway on port 4000: 401 without a key, redacted chat replies, every other port refused."""
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        if request.url.host != "gw.test" or request.url.port != 4000:
            raise refused()
        if request.url.path == "/v1/chat/completions" and request.headers.get("Authorization") == "Bearer sk-test":
            return httpx.Response(200, json={"choices": [{"message": {"content": chat_reply}}]})
        return httpx.Response(401, text="unauthorized")
    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "sk-test")


class TestMain:
    def test_secure_gateway_passes_every_shipped_case(self, capsys):
        assert main([str(CASES), "--target", GATEWAY], network()) == 0
        out = capsys.readouterr().out
        assert "0 failed, 0 error(s)" in out
        assert "FAIL" not in out

    def test_leak_exits_1_and_names_the_case(self, capsys):
        assert main([str(CASES), "--target", GATEWAY], network("sure: jane.doe@example.com")) == 1
        assert "FAIL  PII-001" in capsys.readouterr().out

    def test_missing_api_key_exits_2(self, monkeypatch, capsys):
        monkeypatch.delenv(API_KEY_ENV)
        assert main([str(CASES), "--target", GATEWAY], network()) == 2
        assert API_KEY_ENV in capsys.readouterr().out

    def test_model_host_defaults_to_gateway_host(self):
        calls: list[httpx.Request] = []
        main([str(CASES), "--target", GATEWAY + "/"], network(calls=calls))
        assert "gw.test" in {request.url.host for request in calls if request.url.port == 8081}

    def test_model_host_flag_is_used(self):
        calls: list[httpx.Request] = []
        main([str(CASES), "--target", GATEWAY, "--model-host", "10.0.0.5"], network(calls=calls))
        assert "10.0.0.5" in {request.url.host for request in calls}

    def test_json_report_never_contains_the_key(self, tmp_path):
        path = tmp_path / "report.json"
        main([str(CASES), "--target", GATEWAY, "--json", str(path)], network())
        text = path.read_text()
        assert json.loads(text)["verdict"] == "PASS"
        assert "sk-test" not in text

    def test_bad_case_path_exits_2(self, tmp_path, capsys):
        assert main([str(tmp_path), "--target", GATEWAY], network()) == 2
        assert "aigw-redteam:" in capsys.readouterr().err

    def test_target_without_host_exits_2(self, capsys):
        assert main([str(CASES), "--target", "gw.test"], network()) == 2
        assert "not a URL with a host" in capsys.readouterr().err

    def test_unwritable_json_path_exits_2(self, tmp_path, capsys):
        path = tmp_path / "missing" / "report.json"
        assert main([str(CASES), "--target", GATEWAY, "--json", str(path)], network()) == 2
        assert "could not write report" in capsys.readouterr().err

    def test_target_is_required(self):
        with pytest.raises(SystemExit) as exit_info:
            main([str(CASES)])
        assert exit_info.value.code == 2
