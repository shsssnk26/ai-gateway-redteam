import httpx
from typing import Protocol

from ai_gateway_redteam.catalog.schema import Case
from ai_gateway_redteam.execution.executors import ChatExecutor, Executors, HttpExecutor, send
from ai_gateway_redteam.execution.observation import Observation
from ai_gateway_redteam.execution.target import Target

DEFAULT_TIMEOUT = 10.0
BYPASS_CATEGORY = "gateway-bypass"


class Precondition(Protocol):
    """Something that must hold before certain cases can prove anything."""

    def applies_to(self, case: Case) -> bool:
        """Return true if the case is meaningless unless this precondition holds"""
        ...

    def check(self, target: Target) -> str | None:
        """Return None if the precondition holds, otherwise the reason it does not"""
        ...


class GatewayUp:
    """Bypass cases pass when a model port is unreachable, which a powered-off host also gives.

    So they only count if the gateway on the same machine answers at all.
    """

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def applies_to(self, case: Case) -> bool:
        return case.category == BYPASS_CATEGORY

    def check(self, target: Target) -> str | None:
        observation = send(self._client, "host-check", "GET", target.gateway_url)
        if observation.status is not None:
            return None
        return (f"host check failed: gateway {target.gateway_url} is unreachable, "
                "so an unreachable model port proves nothing")


class Runner:
    """Runs each case with the first executor that applies, after its preconditions hold."""

    def __init__(self, executors: list[Executors], preconditions: list[Precondition] | None = None) -> None:
        self._executors = executors
        self._preconditions = preconditions or []

    def run(self, cases: list[Case], target: Target) -> list[Observation]:
        """Return one Observation per case, in order. Each precondition is checked at most once."""
        checked: dict[int, str | None] = {}
        observations: list[Observation] = []
        for case in cases:
            reason = self._unmet(case, target, checked)
            observations.append(Observation(case.id, error=reason) if reason else self._execute(case, target))
        return observations

    def _unmet(self, case: Case, target: Target, checked: dict[int, str | None]) -> str | None:
        """The reason the first failing precondition gives for this case, or None if all hold"""
        for index, precondition in enumerate(self._preconditions):
            if not precondition.applies_to(case):
                continue
            if index not in checked:
                checked[index] = precondition.check(target)
            if checked[index] is not None:
                return checked[index]
        return None

    def _execute(self, case: Case, target: Target) -> Observation:
        executor = next((e for e in self._executors if e.applies_to(case)), None)
        if executor is None:
            return Observation(case.id, error=f"no executor for kind '{case.kind}'")
        return executor.execute(case, target)


def default_executors(client: httpx.Client) -> list[Executors]:
    return [HttpExecutor(client), ChatExecutor(client)]


def default_preconditions(client: httpx.Client) -> list[Precondition]:
    return [GatewayUp(client)]


def run_all(
    cases: list[Case],
    target: Target,
    timeout: float = DEFAULT_TIMEOUT,
    transport: httpx.BaseTransport | None = None,
) -> list[Observation]:
    """Run every case over one shared client with the default executors and preconditions.

    transport replaces the network, so tests can pass an httpx.MockTransport.
    """
    with httpx.Client(timeout=timeout, follow_redirects=False, transport=transport) as client:
        runner = Runner(default_executors(client), default_preconditions(client))
        return runner.run(cases, target)
