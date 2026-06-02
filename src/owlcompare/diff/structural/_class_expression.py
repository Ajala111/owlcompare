"""Readable summary fragments for decoded restrictions (Component 08).

Turns a :class:`DecodedRestriction` into the short human phrases that the
restriction diff stitches into ``Change.summary`` strings — e.g. ``"max 1
era:hasMaxSpeed"`` or ``"era:hasGauge some era:Gauge"``. Keeping this logic in
one place lets ``restrictions.py`` stay focused on the diff algorithm. See
``specs/08-structural-restrictions.md`` § Subject and summary.
"""

from __future__ import annotations

from collections.abc import Callable

from ._restriction_index import DecodedRestriction

# Cardinality kinds render with a leading keyword; value kinds put the keyword
# between the property and the filler.
_CARDINALITY_WORD: dict[str, str] = {
    "min_cardinality": "min",
    "max_cardinality": "max",
    "exact_cardinality": "exactly",
    "min_qualified_cardinality": "min",
    "max_qualified_cardinality": "max",
    "exact_qualified_cardinality": "exactly",
}
_VALUE_WORD: dict[str, str] = {
    "some_values_from": "some",
    "all_values_from": "all",
    "has_value": "value",
}

# A shortener maps a full IRI to its prefixed display form (or itself).
Shorten = Callable[[str], str]


def is_cardinality(kind: str) -> bool:
    """Whether ``kind`` is one of the (qualified or plain) cardinality shapes."""
    return kind in _CARDINALITY_WORD


def fragment(restriction: DecodedRestriction, short: Shorten) -> str:
    """Kind-specific phrase *without* the property name.

    Cardinality → ``"max 1"`` (qualified adds the filler: ``"min 1 era:Gauge"``);
    value restrictions → ``"some era:Gauge"`` / ``"all era:Gauge"`` /
    ``"value era:Individual"``; anything else → ``"complex expression"``.
    """
    kind = restriction.kind
    if kind in _CARDINALITY_WORD:
        phrase = f"{_CARDINALITY_WORD[kind]} {restriction.cardinality}"
        if restriction.filler is not None:
            phrase += f" {short(restriction.filler)}"
        return phrase
    if kind in _VALUE_WORD and restriction.filler is not None:
        return f"{_VALUE_WORD[kind]} {short(restriction.filler)}"
    return "complex expression"


def describe(restriction: DecodedRestriction, short: Shorten) -> str:
    """Full phrase *including* the property, for added/removed summaries.

    Cardinality reads keyword-first (``"max 1 era:hasMaxSpeed"``); value
    restrictions read property-first (``"era:hasGauge some era:Gauge"``).
    """
    prop = short(restriction.on_property) if restriction.on_property else "?"
    frag = fragment(restriction, short)
    if is_cardinality(restriction.kind):
        return f"{frag} {prop}"
    return f"{prop} {frag}"


def describe_change(before: DecodedRestriction, after: DecodedRestriction, short: Shorten) -> str:
    """Arrow phrase for a changed restriction: ``"era:hasMaxSpeed max 1 → max 2"``.

    The property is named once up front; the before/after fragments follow,
    so a kind change reads ``"era:hasGauge some era:Gauge → all era:Gauge"``.
    """
    prop = short(before.on_property or after.on_property or "?")
    return f"{prop} {fragment(before, short)} → {fragment(after, short)}"
