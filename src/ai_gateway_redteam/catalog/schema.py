from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, model_validator

class Request(BaseModel):
    """The raw HTTP request for kind: http cases."""

    model_config = ConfigDict(extra="forbid")

    method: Literal["GET", "POST"]
    url: str
    headers: dict[str, str] = {}
    body: dict[str, Any] | None = None

class Expect(BaseModel):
    """What must be true for the case to pass."""

    model_config = ConfigDict(extra="forbid")

    status: int | None = None
    connection: Literal["unreachable"] | None = None
    must_not_contain: list[str] | None = None
    must_not_contain_digits: list[str] | None = None
    must_not_contain_ignoring_whitespace: list[str] | None = None

    @model_validator(mode="after")
    def check_expect_has_check(self) -> "Expect":
        checks = [
            self.status,
            self.connection,
            self.must_not_contain,
            self.must_not_contain_digits,
            self.must_not_contain_ignoring_whitespace
        ]
        if not any(checks):
            raise ValueError("Expect needs at least one non-empty check")

        string_lists = {
            "must_not_contain": self.must_not_contain,
            "must_not_contain_digits": self.must_not_contain_digits,
            "must_not_contain_ignoring_whitespace": self.must_not_contain_ignoring_whitespace,
        }

        for name, values in string_lists.items():
            if values is not None and len(values) == 0:
                raise ValueError(f"{name} is empty. It checks nothing")
        return self


class Case(BaseModel):
    "One attack case exactly written in the YAML file"

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    category: Literal["authentication", "gateway-bypass", "pii-leak"]
    severity: Literal["low", "medium", "high", "critical"]
    kind: Literal["http", "chat"]

    # kind: http
    request: Request | None = None
    ports: list[int] = []

    # kind: chat
    model: str | None = None
    prompt: str | None = None
    seed: str | None = None
    transforms: list[str] = []

    expect: Expect

    @model_validator(mode="after")
    def check_fields_match_kind(self) -> "Case":
        if self.kind == "http" and self.request is None:
            raise ValueError(f"{self.id}: kind 'http' needs a request")
        if self.kind == "chat" and (self.model is None or self.prompt is None):
            raise ValueError(f"{self.id}: kind 'chat' needs a model and a prompt")
        if self.transforms and self.seed is None:
            raise ValueError(f"{self.id}: transforms need a seed")
        return self

    


    