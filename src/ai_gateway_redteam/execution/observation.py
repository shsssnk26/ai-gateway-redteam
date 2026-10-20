from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Observation:
    """What happened when one case ran. Graders decide PASS or FAIL from this alone."""

    case_id: str
    status: int | None = None
    body: str | None = None
    connection: Literal["refused", "timeout"] | None = None
    error: str | None = None
    elapsed_ms: float | None = None