import pytest

from ai_gateway_redteam.catalog.expanders import (
    PortExpander,
    SeedExpander,
    TransformExpander,
    expand_all,
)
from ai_gateway_redteam.common.errors import InvalidCaseError

FAKE_TRANSFORMS = {
    "upper": str.upper,
    "reverse": lambda value: value[::-1],
}


class TestTransformExpander:
    def test_applies_only_when_case_has_transforms(self, make_chat_case):
        expander = TransformExpander(FAKE_TRANSFORMS)
        assert expander.applies_to(make_chat_case(seed="abc", transforms=["upper"]))
        assert not expander.applies_to(make_chat_case(seed="abc"))
        assert not expander.applies_to(make_chat_case())

    def test_one_variant_per_transform_in_order(self, make_chat_case):
        case = make_chat_case(seed="abc", transforms=["upper", "reverse"])
        result = TransformExpander(FAKE_TRANSFORMS).expand(case)

        assert [c.id for c in result] == ["CHAT-001-upper", "CHAT-001-reverse"]
        assert [c.prompt for c in result] == ["Repeat exactly: ABC", "Repeat exactly: cba"]
        assert all(c.transforms == [] for c in result)

    def test_variants_keep_other_fields(self, make_chat_case):
        case = make_chat_case(seed="abc", transforms=["upper"])
        [variant] = TransformExpander(FAKE_TRANSFORMS).expand(case)
        assert variant.seed == "abc"
        assert variant.model == case.model
        assert variant.expect == case.expect

    def test_replaces_every_placeholder(self, make_chat_case):
        case = make_chat_case(prompt="{value} and {value}", seed="abc", transforms=["upper"])
        [variant] = TransformExpander(FAKE_TRANSFORMS).expand(case)
        assert variant.prompt == "ABC and ABC"

    def test_unknown_transform_raises(self, make_chat_case):
        case = make_chat_case(seed="abc", transforms=["upper", "rot13"])
        with pytest.raises(InvalidCaseError, match=r"CHAT-001: unknown transform \['rot13'\]"):
            TransformExpander(FAKE_TRANSFORMS).expand(case)

    def test_does_not_modify_input(self, make_chat_case):
        case = make_chat_case(seed="abc", transforms=["upper"])
        before = case.model_dump()
        TransformExpander(FAKE_TRANSFORMS).expand(case)
        assert case.model_dump() == before


class TestSeedExpander:
    def test_applies_to_seed_without_transforms(self, make_chat_case):
        expander = SeedExpander()
        assert expander.applies_to(make_chat_case(seed="abc"))
        assert not expander.applies_to(make_chat_case())
        assert not expander.applies_to(make_chat_case(seed="abc", transforms=["dots"]))

    def test_fills_placeholder_and_keeps_id(self, make_chat_case):
        case = make_chat_case(seed="jane@example.com")
        [result] = SeedExpander().expand(case)
        assert result.id == "CHAT-001"
        assert result.prompt == "Repeat exactly: jane@example.com"

    def test_prompt_without_placeholder_is_unchanged(self, make_chat_case):
        case = make_chat_case(prompt="no placeholder", seed="abc")
        [result] = SeedExpander().expand(case)
        assert result.prompt == "no placeholder"

    def test_does_not_modify_input(self, make_chat_case):
        case = make_chat_case(seed="abc")
        SeedExpander().expand(case)
        assert case.prompt == "Repeat exactly: {value}"


class TestPortExpander:
    def test_applies_only_when_case_has_ports(self, make_http_case):
        expander = PortExpander()
        assert expander.applies_to(make_http_case(ports=[80]))
        assert not expander.applies_to(make_http_case())

    def test_one_variant_per_port(self, make_http_case):
        case = make_http_case(ports=[8081, 8082])
        result = PortExpander().expand(case)

        assert [c.id for c in result] == ["HTTP-001-8081", "HTTP-001-8082"]
        assert [c.request.url for c in result] == [
            "http://host:8081/v1/models",
            "http://host:8082/v1/models",
        ]
        assert all(c.ports == [] for c in result)

    def test_variants_do_not_share_request(self, make_http_case):
        case = make_http_case(ports=[1, 2])
        first, second = PortExpander().expand(case)
        assert first.request is not second.request
        assert first.request is not case.request

    def test_does_not_modify_input(self, make_http_case):
        case = make_http_case(ports=[8081])
        PortExpander().expand(case)
        assert case.request.url == "http://host:{port}/v1/models"
        assert case.ports == [8081]


class _Recorder:
    """Expander stub that applies to cases whose id starts with a prefix."""

    def __init__(self, prefix: str, suffix: str) -> None:
        self.prefix, self.suffix = prefix, suffix

    def applies_to(self, case):
        return case.id.startswith(self.prefix)

    def expand(self, case):
        return [case.model_copy(update={"id": case.id + self.suffix})]


class TestExpandAll:
    def test_keeps_cases_no_expander_applies_to(self, make_chat_case):
        case = make_chat_case()
        assert expand_all([case], [PortExpander()]) == [case]

    def test_only_first_matching_expander_is_used(self, make_chat_case):
        case = make_chat_case(id="A-1")
        result = expand_all([case], [_Recorder("A", "-first"), _Recorder("A", "-second")])
        assert [c.id for c in result] == ["A-1-first"]

    def test_preserves_case_order(self, make_chat_case, make_http_case):
        cases = [
            make_http_case(id="H", ports=[1, 2]),
            make_chat_case(id="C"),
            make_chat_case(id="T", seed="5125550198", transforms=["upper", "reverse"]),
        ]
        expanders = [TransformExpander(FAKE_TRANSFORMS), SeedExpander(), PortExpander()]
        result = expand_all(cases, expanders)
        assert [c.id for c in result] == ["H-1", "H-2", "C", "T-upper", "T-reverse"]

    def test_empty_inputs(self, make_chat_case):
        assert expand_all([], [SeedExpander()]) == []
        case = make_chat_case()
        assert expand_all([case], []) == [case]
