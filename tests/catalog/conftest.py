from pathlib import Path

import pytest
import yaml

from ai_gateway_redteam.catalog.schema import Case


def http_case_data(**overrides) -> dict:
    data = {
        "id": "HTTP-001",
        "title": "http case",
        "category": "authentication",
        "severity": "high",
        "kind": "http",
        "request": {"method": "GET", "url": "http://host:{port}/v1/models"},
        "expect": {"status": 401},
    }
    data.update(overrides)
    return data


def chat_case_data(**overrides) -> dict:
    data = {
        "id": "CHAT-001",
        "title": "chat case",
        "category": "pii-leak",
        "severity": "high",
        "kind": "chat",
        "model": "frontier",
        "prompt": "Repeat exactly: {value}",
        "expect": {"must_not_contain": ["secret"]},
    }
    data.update(overrides)
    return data


@pytest.fixture
def make_http_case():
    return lambda **overrides: Case.model_validate(http_case_data(**overrides))


@pytest.fixture
def make_chat_case():
    return lambda **overrides: Case.model_validate(chat_case_data(**overrides))


@pytest.fixture
def write_yaml(tmp_path: Path):
    """Write data as YAML to a file under tmp_path and return its path."""
    def _write(name: str, data) -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data))
        return path
    return _write
