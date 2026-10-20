import dataclasses

import pytest

from ai_gateway_redteam.execution.observation import Observation


def test_only_case_id_is_required():
    observation = Observation(case_id="AUTH-001")
    assert observation == Observation(
        case_id="AUTH-001",
        status=None,
        body=None,
        connection=None,
        error=None,
        elapsed_ms=None,
    )


def test_case_id_is_required():
    with pytest.raises(TypeError):
        Observation()  # type: ignore[call-arg]


def test_http_response_observation():
    observation = Observation(case_id="AUTH-001", status=401, body='{"error":"unauthorized"}', elapsed_ms=12.5)
    assert observation.status == 401
    assert observation.body == '{"error":"unauthorized"}'
    assert observation.connection is None
    assert observation.elapsed_ms == 12.5


@pytest.mark.parametrize("connection", ["refused", "timeout"])
def test_connection_failure_observation(connection):
    observation = Observation(case_id="BYPASS-001-8081", connection=connection, error="connect failed")
    assert observation.connection == connection
    assert observation.status is None


def test_is_frozen():
    observation = Observation(case_id="AUTH-001")
    with pytest.raises(dataclasses.FrozenInstanceError):
        observation.status = 200  # type: ignore[misc]


def test_replace_returns_new_observation():
    original = Observation(case_id="AUTH-001", status=401)
    changed = dataclasses.replace(original, status=200)
    assert changed.status == 200
    assert original.status == 401


def test_equal_observations_compare_and_hash_equal():
    a = Observation(case_id="X", status=200, body="ok")
    b = Observation(case_id="X", status=200, body="ok")
    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1
    assert a != Observation(case_id="X", status=500, body="ok")


def test_field_order_matches_positional_construction():
    observation = Observation("X", 200, "ok", None, None, 3.0)
    assert [f.name for f in dataclasses.fields(Observation)] == [
        "case_id", "status", "body", "connection", "error", "elapsed_ms",
    ]
    assert observation.elapsed_ms == 3.0
