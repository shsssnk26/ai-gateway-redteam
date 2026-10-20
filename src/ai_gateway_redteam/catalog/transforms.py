"""Disguises applied to a case's seed, to test whether the redactor still recognizes it.

Each transform takes one string and returns the disguised string. Add a new one by
writing the function and registering it in TRANSFORMS; nothing else needs to change.
"""

from collections.abc import Callable

NBSP = "\u00a0"         # non-breaking space: looks like a space, isn't one
ZERO_WIDTH = "\u200b"   # zero-width space: invisible, but still a character
FULLWIDTH_OFFSET = 0xFEE0  # distance from ASCII '!'..'~' to their fullwidth forms


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _phone_groups(value: str, separator: str) -> str:
    """Group a phone number 3-3-rest, e.g. 5125550198 -> 512<sep>555<sep>0198."""
    digits = _digits(value)
    return separator.join([digits[:3], digits[3:6], digits[6:]])


def dots(value: str) -> str:
    return _phone_groups(value, ".")


def no_separators(value: str) -> str:
    return _digits(value)


def nbsp(value: str) -> str:
    return _phone_groups(value, NBSP)


def zero_width(value: str) -> str:
    return ZERO_WIDTH.join(value)


def fullwidth_characters(value: str) -> str:
    return "".join(
        chr(ord(ch) + FULLWIDTH_OFFSET) if "!" <= ch <= "~" else ch
        for ch in value
    )


TRANSFORMS: dict[str, Callable[[str], str]] = {
    "dots": dots,
    "no_separators": no_separators,
    "nbsp": nbsp,
    "zero_width": zero_width,
    "fullwidth_characters": fullwidth_characters,
}