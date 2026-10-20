from pathlib import Path

import pytest

from ai_gateway_redteam.catalog.build import build_cases
from ai_gateway_redteam.common.errors import (
    DuplicateCaseIdError,
    InvalidCaseError,
    NoCaseFilesError,
)

REPO_CASES = Path(__file__).resolve().parents[2] / "cases"

VALID_CASE = """
- id: AUTH-001
  title: t
  category: authentication
  severity: high
  kind: http
  request:
    method: GET
    url: "{target}/v1/models"
  expect:
    status: 401
"""


def test_real_case_files_load_and_expand():
    assert len(build_cases(REPO_CASES)) == 12


def test_empty_folder_is_an_error(tmp_path):
    with pytest.raises(NoCaseFilesError):
        build_cases(tmp_path)


def test_yml_files_in_subfolders_are_found(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "auth.yml").write_text(VALID_CASE)
    assert [c.id for c in build_cases(tmp_path)] == ["AUTH-001"]


def test_misspelled_field_is_rejected(tmp_path):
    (tmp_path / "bad.yaml").write_text(VALID_CASE.replace("method:", "methos:"))
    with pytest.raises(InvalidCaseError, match="AUTH-001"):
        build_cases(tmp_path)


def test_empty_expect_is_rejected(tmp_path):
    (tmp_path / "bad.yaml").write_text(VALID_CASE.replace("expect:\n    status: 401", "expect: {}"))
    with pytest.raises(InvalidCaseError):
        build_cases(tmp_path)


def test_duplicate_ids_are_rejected(tmp_path):
    (tmp_path / "a.yaml").write_text(VALID_CASE)
    (tmp_path / "b.yaml").write_text(VALID_CASE)
    with pytest.raises(DuplicateCaseIdError):
        build_cases(tmp_path)
