import pytest

from ai_gateway_redteam.catalog.loader import find_yaml_files, load_cases, parse_case_files
from ai_gateway_redteam.common.errors import InvalidCaseError, NoCaseFilesError

from .conftest import chat_case_data, http_case_data


class TestFindYamlFiles:
    def test_returns_single_file_as_is(self, write_yaml):
        path = write_yaml("cases.txt", [])  # any file is accepted when passed directly
        assert find_yaml_files(path) == [path]

    def test_finds_yaml_and_yml_recursively_sorted(self, tmp_path, write_yaml):
        b = write_yaml("b.yml", [])
        a = write_yaml("a.yaml", [])
        nested = write_yaml("sub/c.yaml", [])
        (tmp_path / "notes.txt").write_text("ignore me")

        assert find_yaml_files(tmp_path) == sorted([a, b, nested])

    def test_empty_directory_raises(self, tmp_path):
        with pytest.raises(NoCaseFilesError, match="no .yaml or .yml files"):
            find_yaml_files(tmp_path)

    def test_missing_path_raises(self, tmp_path):
        with pytest.raises(NoCaseFilesError):
            find_yaml_files(tmp_path / "does-not-exist")


class TestParseCaseFiles:
    def test_parses_valid_cases(self, write_yaml):
        path = write_yaml("cases.yaml", [http_case_data(), chat_case_data()])
        cases = parse_case_files(path)
        assert [c.id for c in cases] == ["HTTP-001", "CHAT-001"]

    def test_empty_file_gives_no_cases(self, tmp_path):
        path = tmp_path / "empty.yaml"
        path.write_text("")
        assert parse_case_files(path) == []

    def test_non_list_top_level_raises(self, write_yaml):
        path = write_yaml("cases.yaml", {"id": "X"})
        with pytest.raises(InvalidCaseError, match="does not contain a list of cases"):
            parse_case_files(path)

    def test_invalid_case_reports_file_and_id(self, write_yaml):
        path = write_yaml("cases.yaml", [chat_case_data(id="BAD-1", severity="urgent")])
        with pytest.raises(InvalidCaseError, match=r"case BAD-1 is invalid") as excinfo:
            parse_case_files(path)
        assert str(path) in str(excinfo.value)

    def test_invalid_case_without_id(self, write_yaml):
        data = chat_case_data()
        del data["id"]
        path = write_yaml("cases.yaml", [data])
        with pytest.raises(InvalidCaseError, match="<no id>"):
            parse_case_files(path)

    def test_non_mapping_item(self, write_yaml):
        path = write_yaml("cases.yaml", ["just a string"])
        with pytest.raises(InvalidCaseError, match="<not a mapping>"):
            parse_case_files(path)

    def test_malformed_yaml_propagates_yaml_error(self, tmp_path):
        import yaml

        path = tmp_path / "broken.yaml"
        path.write_text("- id: [unclosed\n")
        with pytest.raises(yaml.YAMLError):
            parse_case_files(path)


class TestLoadCases:
    def test_accepts_str_and_path(self, write_yaml):
        path = write_yaml("cases.yaml", [chat_case_data()])
        assert load_cases(str(path)) == load_cases(path)

    def test_combines_files_in_sorted_order(self, tmp_path, write_yaml):
        write_yaml("b.yaml", [chat_case_data(id="B")])
        write_yaml("a.yaml", [chat_case_data(id="A1"), chat_case_data(id="A2")])
        assert [c.id for c in load_cases(tmp_path)] == ["A1", "A2", "B"]

    def test_does_not_expand(self, write_yaml):
        path = write_yaml("cases.yaml", [http_case_data(ports=[1, 2])])
        [case] = load_cases(path)
        assert case.ports == [1, 2]
        assert case.request is not None
        assert "{port}" in case.request.url
