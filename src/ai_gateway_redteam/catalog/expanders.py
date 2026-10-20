from collections.abc import Callable, Mapping
from typing import Protocol

from ai_gateway_redteam.catalog.schema import Case
from ai_gateway_redteam.common.errors import InvalidCaseError

class Expander(Protocol):
    """Turns onne case into the concrete casses it describes. Must never modify its input"""

    def applies_to(self, case: Case) -> bool:
        """Return true if this expander should handle the case"""

    def expand(self, case: Case) -> list[Case]:
        """Return the expanded case this case describes"""

class TransformExpander:
    """One variant per named transform, each filling {value} with a disguised seed."""
    def __init__(self, transforms: Mapping[str, Callable[[str], str]]) -> None:
        self._transforms = transforms

    def applies_to(self, case: Case) -> bool:
        return bool(case.transforms)

    def expand(self, case: Case) -> list[Case]:
        unknown = [name for name in case.transforms if name not in self._transforms]
        if unknown:
            raise InvalidCaseError(f"{case.id}: unknown transform {unknown}")
        return [
            case.model_copy(update={
                "id": f"{case.id}-{name}",
                "prompt": case.prompt.replace("{value}", self._transforms[name](case.seed)),
                "transforms": [],
            })
            for name in case.transforms
        ]

class SeedExpander:
    def applies_to(self, case: Case) -> bool:
        return case.seed is not None and not case.transforms

    def expand(self, case: Case) -> list[Case]:
        return [case.model_copy(update={
            "prompt": case.prompt.replace("{value}", case.seed),
        })]

class PortExpander:
    """One variant per port, each with {port} in the request URL replaced."""
    def applies_to(self, case: Case) -> bool:
        return bool(case.ports)

    def expand(self, case: Case) -> list[Case]:
        cases = []
        for port in case.ports:
            new_request = case.request.model_copy(update={
                "url": case.request.url.replace("{port}", f"{port}")
            })
            cases.append(case.model_copy(update={
                "id": f"{case.id}-{port}",
                "request": new_request,
                "ports": [],
            }))
        return cases


def expand_all(cases: list[Case], expanders: list[Expander]) -> list[Case]:
    """Give each case to the first expander that applies; keep it unchanged if none does."""
    expanded: list[Case] = []
    for case in cases:
        expander = next((e for e in expanders if e.applies_to(case)), None)
        expanded.extend(expander.expand(case) if expander else [case])
    return expanded 