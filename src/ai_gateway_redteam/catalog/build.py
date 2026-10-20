from pathlib import Path

from ai_gateway_redteam.catalog.expanders import (
    Expander,
    PortExpander,
    SeedExpander,
    TransformExpander,
    expand_all,
)
from ai_gateway_redteam.catalog.loader import load_cases
from ai_gateway_redteam.catalog.schema import Case
from ai_gateway_redteam.catalog.transforms import TRANSFORMS
from ai_gateway_redteam.common.errors import DuplicateCaseIdError

def default_expanders() -> list[Expander]:
    return [TransformExpander(TRANSFORMS), SeedExpander(), PortExpander()]

def check_unique_ids(cases: list[Case]) -> None:
    """Fail if two cases share the same id as that would lead to ambiguos cases"""
    ids = [case.id for case in cases]
    duplicates = sorted({id for id in ids if ids.count(id) > 1})
    if duplicates:
        raise DuplicateCaseIdError(f"Duplicate case ides detected : {duplicates}")

def build_cases(path: str|Path, expanders: list[Expander]|None=None) -> list[Case]:
    """Load cases, expand fields to add cases and return all cases after expansion"""
    cases = expand_all(load_cases(path), expanders or default_expanders())
    check_unique_ids(cases)
    return cases
     