from pathlib import Path

import yaml
from pydantic import ValidationError

from ai_gateway_redteam.catalog.schema import Case
from ai_gateway_redteam.common.errors import CaseFileError, InvalidCaseError

def find_yaml_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files = sorted(p for p in path.rglob("*") if p.suffix in {".yaml", ".yml"})
    if not files:
        raise CaseFileError(f"no .yaml or .yml files found in {path}")
    return files

def parse_case_files(path: Path) -> list[Case]:
    """Read yaml file and validate it against the schema"""
    raw = yaml.safe_load(path.read_text()) or []
    if not isinstance(raw, list):
        raise InvalidCaseError(f"{path} does not contain a list of cases")

    cases: list[Case] = []
    for item in raw:
        try:
            cases.append(Case.model_validate(item))
        except ValidationError as error:
            case_id = item.get("id", "<no id>") if isinstance(item, dict) else "<not a mapping>"
            raise InvalidCaseError(f"{path}: case {case_id} is invalid:\n{error}") from error
    return cases

def load_cases(path: str | Path) -> list[Case]:
    """Every case from the case files, validated but not yet expanded"""
    files = find_yaml_files(Path(path))
    return [case for file in files for case in parse_case_files(file)]



        
