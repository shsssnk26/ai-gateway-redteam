from pathlib import Path

import pytest

from ai_gateway_redteam.catalog.build import build_cases, check_unique_ids, default_expanders
from ai_gateway_redteam.catalog.expanders import PortExpander, SeedExpander, TransformExpander
from ai_gateway_redteam.catalog.transforms import NBSP, ZERO_WIDTH
from ai_gateway_redteam.common.errors import DuplicateCaseIdError

from .conftest import chat_case_data, http_case_data

REPO_CASES = Path(__file__).resolve().parents[2] / "cases"


def test_default_expanders_order():
    expanders = default_expanders()
    assert [type(e) for e in expanders] == [TransformExpander, SeedExpander, PortExpander]


class TestCheckUniqueIds:
    def test_unique_ids_pass(self, make_chat_case):
        check_unique_ids([make_chat_case(id="A"), make_chat_case(id="B")])

    def test_empty_list_passes(self):
        check_unique_ids([])

    def test_duplicates_are_reported_sorted_once(self, make_chat_case):
        cases = [make_chat_case(id=i) for i in ["B", "A", "B", "A", "B", "C"]]
        with pytest.raises(DuplicateCaseIdError, match=r"\['A', 'B'\]"):
            check_unique_ids(cases)


class TestBuildCases:
    def test_expands_with_default_expanders(self, write_yaml):
        path = write_yaml("cases.yaml", [
            http_case_data(id="H", ports=[8081, 8082]),
            chat_case_data(id="S", seed="jane@example.com"),
            chat_case_data(id="T", seed="5125550198", transforms=["dots", "no_separators"]),
            chat_case_data(id="P"),
        ])
        cases = build_cases(path)
        assert {c.id: c.prompt for c in cases if c.kind == "chat"} == {
            "S": "Repeat exactly: jane@example.com",
            "T-dots": "Repeat exactly: 512.555.0198",
            "T-no_separators": "Repeat exactly: 5125550198",
            "P": "Repeat exactly: {value}",
        }
        assert [c.request.url for c in cases if c.kind == "http"] == [
            "http://host:8081/v1/models",
            "http://host:8082/v1/models",
        ]

    def test_custom_expanders_replace_defaults(self, write_yaml):
        path = write_yaml("cases.yaml", [
            http_case_data(id="H", ports=[1, 2]),
            chat_case_data(id="S", seed="x"),
        ])
        cases = build_cases(path, expanders=[PortExpander()])
        assert [c.id for c in cases] == ["H-1", "H-2", "S"]
        assert cases[-1].prompt == "Repeat exactly: {value}"

    def test_empty_expander_list_means_no_expansion(self, write_yaml):
        path = write_yaml("cases.yaml", [
            http_case_data(id="H", ports=[1, 2]),
            chat_case_data(id="S", seed="x"),
        ])
        cases = build_cases(path, expanders=[])
        assert [c.id for c in cases] == ["H", "S"]
        assert cases[0].ports == [1, 2]
        assert cases[1].prompt == "Repeat exactly: {value}"

    def test_duplicate_ids_after_expansion_raise(self, write_yaml):
        path = write_yaml("cases.yaml", [
            http_case_data(id="H", ports=[1]),
            http_case_data(id="H-1"),
        ])
        with pytest.raises(DuplicateCaseIdError, match="H-1"):
            build_cases(path)

    def test_duplicate_ids_across_files_raise(self, tmp_path, write_yaml):
        write_yaml("a.yaml", [chat_case_data(id="X")])
        write_yaml("b.yaml", [chat_case_data(id="X")])
        with pytest.raises(DuplicateCaseIdError):
            build_cases(tmp_path)


def test_repository_case_catalog_builds():
    """The shipped cases/ directory must load, expand and have unique ids."""
    cases = {c.id: c for c in build_cases(REPO_CASES)}

    assert {"BYPASS-001-8081", "BYPASS-001-8082", "BYPASS-001-8083"} <= cases.keys()
    assert "BYPASS-001" not in cases
    assert cases["BYPASS-001-8083"].request.url == "http://{model_host}:8083/v1/models"

    pii2 = {k: v.prompt for k, v in cases.items() if k.startswith("PII-002-")}
    assert set(pii2) == {f"PII-002-{n}" for n in
                         ["dots", "no_separators", "nbsp", "zero_width", "fullwidth_characters"]}
    assert pii2["PII-002-dots"].endswith("512.555.0198")
    assert pii2["PII-002-nbsp"].endswith(f"512{NBSP}555{NBSP}0198")
    assert ZERO_WIDTH in pii2["PII-002-zero_width"]

    assert cases["PII-003"].prompt.endswith("jane.doe@example.com")
    assert all("{value}" not in (c.prompt or "") for c in cases.values())
    assert all("{port}" not in (c.request.url if c.request else "") for c in cases.values())
