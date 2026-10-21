import httpx
import json
import time
from typing import Protocol

from ai_gateway_redteam.catalog.schema import Case
from ai_gateway_redteam.execution.target import Target, fill_placeholders
from ai_gateway_redteam.execution.observation import Observation

from dataclasses import replace


class Executors(Protocol):
    """Execute the actions defined in cases"""

    def applies_to(self, case : Case) -> bool:
        """Checks if the executor applies to the kind of case provided"""

    def execute(self, case: Case, target: Target) -> List[str]:
        """Sends the case to the target anf returns what was observed """


def _was_refused(error: BaseException) -> bool:
    """True only if the operating system actively refused the connection"""
    current: BaseException | None = error
    while current is not None:
        if isinstance(current, ConnectionRefusedError):
            return True
        current = current.__cause__ or current.__context__
    return False

def send(client: httpx.Client, case_id: str, method: str, url: str, **kwargs) -> Observation:
    """Make rquest to the url and store every possible outcome in Observation"""
    start = time.perf_counter()

    def elapsed() -> float:
        return round((time.perf_counter() - start) * 1000, 1)

    try:
        response = client.request(method, url, **kwargs)
    except httpx.TimeoutException:
        return Observation(case_id, connection = "timeout", elapsed_ms = elapsed())
    except httpx.ConnectError as error:
        if _was_refused(error):
            return Observation(case_id, connection = "refused", elapsed_ms = elapsed())
        return Observation(case_id, error = f"Could not connect: {error}", elapsed_ms = elapsed())
    except httpx.HTTPError as error:
        return Observation(case_id, error=f"{type(error).__name__}: {error}", elapsed_ms = elapsed())
    return Observation(case_id, status = response.status_code, body = response.text, elapsed_ms = elapsed())

class HttpExecutor:
    """Sends the case's raw request exactly as written. Adds no gateway key."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def applies_to(self, case: Case) -> bool:
        return case.kind == "http"

    def execute(self, case: Case, target: Target) -> Observation:
        request = case.request
        return send(self._client,
                    case.id,
                    request.method,
                    fill_placeholders(request.url, target),
                    headers = request.headers,
                    json = request.body,
                    )


class ChatExecutor:
    """Send a chat case through the gateway with a key the sameway an agent would"""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def applies_to(self, case: Case) -> bool:
        return case.kind == "chat"

    def execute(self, case: Case, target: Target) -> Observation:
        if target.api_key is None:
            return Observation(case.id, error = "no API key found: set AIGW_REDTEAM_API_KEY")
        url = target.gateway_url + "/v1/chat/completions"
        headers = {
            "Authorization" : f"Bearer {target.api_key}",
            "Content-Type" : "application/json",
        }
        body = {
            "model" : case.model,
            "messages": [{
                "role" : "user",
                "content" : case.prompt,
        }]
        }
        
        observation = send(self._client,
                        case.id,
                        method = "POST",
                        url = url,
                        headers = headers,
                        json = body,
                        )

        return self._with_reply(observation)

    def _with_reply(self, observation : Observation) -> Observation:
        if observation.body is None:
            return observation
        try: 
            body_json = json.loads(observation.body)
            new_observation = replace(observation, body = body_json["choices"][0]["message"]["content"])
            return new_observation
        except (json.JSONDecodeError, KeyError, IndexError, TypeError )as error:
            return replace(observation, error=f"gateway reply was not a chat completion: {error} " +
                            f" of type {type(error).__name__}")
