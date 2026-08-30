"""English pluralization helpers for generating grammatically correct user-facing messages."""

import re
from typing import Sized


def pluralize(single_thing: str, items: int | Sized) -> str:
    """If items or len(items) is 1, return the provided noun. Otherwise, return
    its plural form.

    Examples:
        >>> pluralize("cat", 1)
        "cat"
        >>> pluralize("cat", 2)
        "cats"

    Args:
        single_thing: A singular noun.
        items: An integer or a Sized (countable) object.

    Returns:
        The singular or plural form of the given noun.
    """

    count = items if isinstance(items, int) else len(items)
    if count == 1:
        thing = single_thing
    elif single_thing.endswith("y"):
        thing = f"{single_thing[:-1]}ies"
    else:
        thing = f"{single_thing}s"

    return thing


def plural(items: int | Sized, single_thing: str) -> str:
    """Given a count or Sized object and a singular noun, return a count with
    the correct grammatical number.

    Examples:
        >>> plural(1, "cat")
        "1 cat"
        >>> plural(2, "cat")
        "2 cats"

    Args:
        items: An integer or a Sized (countable) object.
        single_thing: A singular noun.

    Returns:
        A string of the form N noun(s).
    """

    count = items if isinstance(items, int) else len(items)
    return f"{count} {pluralize(single_thing, items)}"


def is_plural(items: int | Sized, single_thing: str) -> str:
    """Given a count or Sized object and a singular noun, return a phrase
    of the form "is 1 apple" with the correct grammatical number.

    Examples:
        >>> is_plural(1, "cat")
        "is 1 cat"
        >>> is_plural(2, "cat")
        "are 2 cats"

    Args:
        items: An integer or a Sized (countable) object.
        single_thing: A singular noun.

    Returns:
        A phrase with "is" or "are" and the count.
    """
    count = items if isinstance(items, int) else len(items)
    verb = "is" if count == 1 else "are"
    return f"{verb} {count} {pluralize(single_thing, items)}"


def a_plural(items: int | Sized, single_thing: str) -> str:
    """Given a count or Sized object and a singular noun, return either the
    plural form of the noun, or the singular form prefixed with a/an.

    Examples:
        >>> a_plural(1, "cat")
        "a cat"
        >>> a_plural(2, "cat")
        "cats"

    Args:
        items: An integer or a Sized (countable) object.
        single_thing: A singular noun.

    Returns:
        Either the plural form of the noun or the noun prefixed with a/an.
    """
    count = items if isinstance(items, int) else len(items)
    if count != 1:
        article = ""
    else:
        # cSpell: disable-next-line
        article = "an " if re.match("[aeiou]", single_thing) else "a "
    return f"{article}{pluralize(single_thing, items)}"
