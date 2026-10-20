import pytest

from ai_gateway_redteam.catalog import transforms
from ai_gateway_redteam.catalog.transforms import (
    NBSP,
    TRANSFORMS,
    ZERO_WIDTH,
    dots,
    fullwidth_characters,
    nbsp,
    no_separators,
    zero_width,
)

PHONE = "5125550198"


@pytest.mark.parametrize("value", [PHONE, "512-555-0198", "(512) 555 0198", "512.555.0198"])
def test_dots_groups_digits_regardless_of_input_format(value):
    assert dots(value) == "512.555.0198"


@pytest.mark.parametrize("value", [PHONE, "512-555-0198", "(512) 555-0198"])
def test_no_separators_keeps_only_digits(value):
    assert no_separators(value) == PHONE


def test_no_separators_on_value_without_digits():
    assert no_separators("abc") == ""


def test_nbsp_groups_with_non_breaking_space():
    result = nbsp(PHONE)
    assert result == f"512{NBSP}555{NBSP}0198"
    assert " " not in result


def test_phone_grouping_keeps_all_trailing_digits():
    assert dots("15125550198") == "151.255.50198"


def test_zero_width_interleaves_every_character():
    result = zero_width("abc")
    assert result == f"a{ZERO_WIDTH}b{ZERO_WIDTH}c"
    assert result.replace(ZERO_WIDTH, "") == "abc"


def test_zero_width_on_single_character_and_empty():
    assert zero_width("a") == "a"
    assert zero_width("") == ""


def test_fullwidth_converts_printable_ascii():
    assert fullwidth_characters("A1@~!") == "Ａ１＠～！"


def test_fullwidth_leaves_space_and_non_ascii_untouched():
    assert fullwidth_characters("a bé") == "ａ ｂé"


def test_fullwidth_output_differs_from_input_but_normalizes_back():
    import unicodedata

    result = fullwidth_characters("jane.doe@example.com")
    assert result != "jane.doe@example.com"
    assert unicodedata.normalize("NFKC", result) == "jane.doe@example.com"


def test_registry_names_map_to_module_functions():
    assert set(TRANSFORMS) == {"dots", "no_separators", "nbsp", "zero_width", "fullwidth_characters"}
    for name, func in TRANSFORMS.items():
        assert func is getattr(transforms, name)


@pytest.mark.parametrize("name", list(TRANSFORMS))
def test_every_transform_disguises_the_phone_seed(name):
    result = TRANSFORMS[name](PHONE)
    assert isinstance(result, str)
    if name != "no_separators":  # the seed already has no separators
        assert result != PHONE
