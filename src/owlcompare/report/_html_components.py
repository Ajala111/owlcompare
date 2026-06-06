"""Per-kind summary renderers and HTML building blocks for the report (Component 17).

The functions here turn one ``Change`` into the inner markup of a card: a human
*title* (the kind noun), a *subject* IRI chip, and a *summary* line that mirrors
Component 15's Markdown templates but with richer HTML (``<code>`` IRI chips,
``<del>``/``<ins>`` arrow changes, ``<code class="restriction">`` expressions).
Every value that originates in a ``DiffResult`` passes through
:func:`escape_html`. Unknown kinds fall back to the producer's plain ``summary``
so a future ``kind`` never breaks the v1 renderer. See ``specs/17-html-report.md``
and ``docs/design/UI_PRIMITIVES.md``.
"""

from __future__ import annotations

from collections.abc import Callable

from owlcompare.diff._common import Change, shorten_synthetic_iri
from owlcompare.model import shorten_iri

# A per-kind summary renderer: takes the change and the merged prefix map, returns
# the inner HTML of the card's summary line.
SummaryRenderer = Callable[[Change, dict[str, str]], str]

# Human-facing noun per entity kind (mirrors Component 15's table and the
# producer-side nouns in the diff slices).
_KIND_NOUN: dict[str, str] = {
    "class": "Class",
    "object_property": "Object property",
    "data_property": "Data property",
    "annotation_property": "Annotation property",
    "individual": "Individual",
    "datatype": "Datatype",
}

# Component 12.5 union kinds → the card title. The verb follows the same
# expanded / narrowed / changed logic the producer uses in its summaries.
_UNION_NOUN: dict[str, str] = {
    "domain": "Domain",
    "range": "Range",
    "subclass": "Subclass",
    "equivalent_class": "Equivalent class",
}
_UNION_VERB: dict[str, str] = {"added": "expanded", "removed": "narrowed", "changed": "changed"}

# Titles for kinds that don't follow the entity-add/remove or union pattern.
_TITLES: dict[str, str] = {
    "class_parent_added": "Class parent added",
    "class_parent_removed": "Class parent removed",
    "class_reparented": "Class reparented",
    "property_parent_added": "Property parent added",
    "property_parent_removed": "Property parent removed",
    "property_reparented": "Property reparented",
    "class_hierarchy_cycle_introduced": "Hierarchy cycle introduced",
    "restriction_added": "Restriction added",
    "restriction_removed": "Restriction removed",
    "restriction_changed": "Restriction changed",
    "domain_added": "Domain added",
    "domain_removed": "Domain removed",
    "domain_changed": "Domain changed",
    "range_added": "Range added",
    "range_removed": "Range removed",
    "range_changed": "Range changed",
    "equivalent_class_added": "Equivalent class added",
    "equivalent_class_removed": "Equivalent class removed",
    "disjoint_added": "Disjoint added",
    "disjoint_removed": "Disjoint removed",
    "complement_set": "Complement set",
    "complement_unset": "Complement unset",
    "complex_class_expression_changed": "Complex class expression changed",
    "entity_deprecated": "Deprecated",
    "entity_undeprecated": "Undeprecated",
    "ontology_metadata_changed": "Ontology metadata changed",
    "datatype_facet_added": "Range facet added",
    "datatype_facet_removed": "Range facet removed",
    "datatype_facet_changed": "Range facet changed",
    "datatype_base_changed": "Range base changed",
    "replaced_by_set": "Replaced by",
    "replaced_by_unset": "Replaced-by removed",
}

# Detail keys that are Tier 3 bookkeeping — anchors and roll-up ids, never shown
# in the details list (docs/design/CONTENT_INVENTORY.md).
_HIDDEN_DETAIL_KEYS = frozenset({"subsumes", "cascade_subsumes"})

_ARROW = '<span class="arrow" aria-hidden="true">&rarr;</span>'


def escape_html(text: str) -> str:
    """Escape the five HTML-significant characters in ``text``.

    The single source of truth for escaping user-supplied strings (labels, IRIs,
    comments, evidence, source paths). Order matters: ``&`` is replaced first so
    the entities introduced for the others are not double-escaped.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


# --------------------------------------------------------------------------- #
# IRI / value primitives
# --------------------------------------------------------------------------- #


def _short(iri: str, prefixes: dict[str, str]) -> str:
    """Prefixed display form of ``iri``, collapsing synthetic restriction/list URNs."""
    return shorten_synthetic_iri(shorten_iri(iri, prefixes))


def iri_chip(iri: str, prefixes: dict[str, str]) -> str:
    """An ``IRIChip``: ``<code class="iri" title="full">short</code>`` (UI_PRIMITIVES.md)."""
    short = _short(iri, prefixes)
    return f'<code class="iri" title="{escape_html(iri)}">{escape_html(short)}</code>'


def _arrow_change(before: str, after: str) -> str:
    """A ``<del>before</del> &rarr; <ins>after</ins>`` arrow change (already-escaped HTML)."""
    return f"<del>{before}</del> {_ARROW} <ins>{after}</ins>"


def _str(value: object) -> str:
    """Coerce an optional ``details`` value to a string (``<unknown>`` for ``None``)."""
    return str(value) if value is not None else "<unknown>"


# --------------------------------------------------------------------------- #
# Title + subject (the card header)
# --------------------------------------------------------------------------- #


def kind_title(change: Change) -> str:
    """The human noun shown as the card title (plain text, caller escapes)."""
    kind = change.kind
    entity = _entity_addremove(kind)
    if entity is not None:
        noun, action = entity
        return f"{noun} {action}"
    if kind.endswith("_renamed"):
        noun = _KIND_NOUN.get(_str(change.details.get("entity_kind")), "Entity")
        return f"{noun} renamed"
    union = _union_parts(kind)
    if union is not None:
        ctx, action = union
        return f"{_UNION_NOUN[ctx]} {_UNION_VERB[action]}"
    if kind in ("annotation_changed", "annotation_added", "annotation_removed"):
        return _annotation_title(change)
    if kind in _TITLES:
        return _TITLES[kind]
    # Forward-compatible: humanise an unknown kind ("foo_bar_baz" → "Foo bar baz").
    return kind.replace("_", " ").capitalize()


def card_subject(change: Change, prefixes: dict[str, str]) -> str | None:
    """The IRI for the card subtitle chip, or ``None`` when the summary carries it.

    Renames show ``before &rarr; after`` in the summary, so they need no subtitle.
    """
    if change.kind.endswith("_renamed"):
        return None
    details = change.details
    for key in ("entity_iri", "property_iri", "ontology_iri"):
        value = details.get(key)
        if value:
            return str(value)
    return change.subject or None


# --------------------------------------------------------------------------- #
# Summary dispatch
# --------------------------------------------------------------------------- #


def render_change_summary(change: Change, prefixes: dict[str, str]) -> str:
    """Render the card's summary line for ``change`` as HTML.

    Dispatches to the per-kind renderer; unknown kinds fall back to the
    producer's escaped ``summary`` so a v1.1 kind never breaks the v1 renderer.
    """
    if _entity_addremove(change.kind) is not None:
        return _render_entity(change)
    if change.kind.endswith("_renamed"):
        return _render_rename(change, prefixes)
    if _union_parts(change.kind) is not None:
        return _render_union(change, prefixes)
    renderer = _SUMMARY_RENDERERS.get(change.kind)
    if renderer is not None:
        return renderer(change, prefixes)
    return f"<p>{escape_html(change.summary)}</p>"


# --------------------------------------------------------------------------- #
# Per-kind summary renderers
# --------------------------------------------------------------------------- #


def _render_entity(change: Change) -> str:
    """Entity add/remove: the optional ``"Label"@lang`` suffix (subject is the title)."""
    label = change.details.get("label")
    if not label:
        return ""
    language = change.details.get("language")
    suffix = f"@{escape_html(str(language))}" if language else ""
    return f'<span class="label">&quot;{escape_html(str(label))}&quot;{suffix}</span>'


def _render_rename(change: Change, prefixes: dict[str, str]) -> str:
    """Rename: ``before &rarr; after`` plus the confidence + evidence list."""
    details = change.details
    before = iri_chip(_str(details.get("before_iri")), prefixes)
    after = iri_chip(_str(details.get("after_iri")), prefixes)
    body = f'<div class="rename-arrow">{before} {_ARROW} {after}</div>'
    return body + _evidence_list(change)


def _evidence_list(change: Change) -> str:
    """The ``EvidenceList`` under a rename: confidence line + one bullet per evidence."""
    details = change.details
    confidence = _str(details.get("confidence"))
    conf_text = confidence if confidence == "certain" else f"{confidence} confidence"
    items = [
        f'<li class="confidence-line"><span class="confidence">{escape_html(conf_text)}</span></li>'
    ]
    for evidence in details.get("evidence", []):
        items.append(f"<li>{escape_html(str(evidence))}</li>")
    return '<ul class="oc-evidence">' + "".join(items) + "</ul>"


def _render_restriction(change: Change, prefixes: dict[str, str]) -> str:
    """Restriction add/remove/change: the producer's readable form in a code span."""
    return f'<code class="restriction">{escape_html(_summary_tail(change))}</code>'


def _render_domain_range(change: Change, prefixes: dict[str, str]) -> str:
    """Domain/range changed: ``<del>before</del> &rarr; <ins>after</ins>``."""
    details = change.details
    before = _str(details.get("before"))
    after = _str(details.get("after"))
    if before == "<unknown>" or after == "<unknown>":
        # added/removed variants carry a single value, not before/after.
        value = details.get("value")
        if value is not None:
            return iri_chip(str(value), prefixes)
        return f'<code class="restriction">{escape_html(_summary_tail(change))}</code>'
    return _arrow_change(
        escape_html(_short(before, prefixes)), escape_html(_short(after, prefixes))
    )


def _render_pairwise(symbol: str) -> SummaryRenderer:
    """Build a renderer for an ``A {symbol} B`` pairwise relation (equivalent/disjoint)."""

    def render(change: Change, prefixes: dict[str, str]) -> str:
        entity = iri_chip(_str(change.details.get("entity_iri")), prefixes)
        other = iri_chip(_str(change.details.get("other_iri")), prefixes)
        return f'{entity} <span class="rel">{symbol}</span> {other}'

    return render


def _render_parent(verb: str) -> SummaryRenderer:
    """Build a renderer for a hierarchy edge ("gained"/"lost" the parent chip)."""

    def render(change: Change, prefixes: dict[str, str]) -> str:
        parent = iri_chip(_str(change.details.get("parent_iri")), prefixes)
        return f"{verb} {parent}"

    return render


def _render_reparented(change: Change, prefixes: dict[str, str]) -> str:
    """Reparent: ``{old parents} &rarr; {new parents} (direction)``."""
    old = _parent_set(change.details.get("parents_before"), prefixes)
    new = _parent_set(change.details.get("parents_after"), prefixes)
    direction = escape_html(_str(change.details.get("direction")))
    return f'{_arrow_change(old, new)} <span class="direction">({direction})</span>'


def _render_annotation(change: Change, prefixes: dict[str, str]) -> str:
    """Annotation changed/added/removed: the language tag + before/after values."""
    details = change.details
    language = details.get("language")
    lang = f' <span class="lang">({escape_html(str(language))})</span>' if language else ""
    if change.kind == "annotation_changed":
        before = escape_html(_annotation_value(details.get("before")))
        after = escape_html(_annotation_value(details.get("after")))
        body = _arrow_change(f"&quot;{before}&quot;", f"&quot;{after}&quot;")
        return f"{body}{lang}"
    value = details.get("value")
    if value is None:
        return f"<p>{escape_html(change.summary)}</p>"
    if details.get("is_iri_value"):
        return iri_chip(str(value), prefixes) + lang
    return f'<span class="label">&quot;{escape_html(str(value))}&quot;</span>{lang}'


def _render_ontology_metadata(change: Change, prefixes: dict[str, str]) -> str:
    """Ontology-header edit: ``predicate: <del>before</del> &rarr; <ins>after</ins>``."""
    details = change.details
    predicate = iri_chip(_str(details.get("predicate_iri")), prefixes)
    before = escape_html(_annotation_value(details.get("before")))
    after = escape_html(_annotation_value(details.get("after")))
    body = _arrow_change(f"&quot;{before}&quot;", f"&quot;{after}&quot;")
    return f"{predicate} {body}"


def _render_deprecation(change: Change, prefixes: dict[str, str]) -> str:
    """Deprecation: the subject is in the title; the summary needs no extra body."""
    return ""


def _render_summary_tail(change: Change, prefixes: dict[str, str]) -> str:
    """Generic: the producer summary after the first ``": "`` in a code span.

    Used by the datatype-facet and ``replaced_by`` kinds, whose producer
    summaries already carry the prefixed, readable form.
    """
    return f'<code class="restriction">{escape_html(_summary_tail(change))}</code>'


def _render_union(change: Change, prefixes: dict[str, str]) -> str:
    """Component 12.5 union change: a clean member diff (the flagship card).

    For a stable-shape change, renders the added (``+``) and removed (``-``)
    members as IRI chips — the visible proof that decoded ``owl:unionOf`` data
    surfaces as one card, not a dozen ``_list:`` noise rows. Flatten / unflatten
    reshapes fall back to the producer's readable summary phrasing.
    """
    details = change.details
    shape = details.get("shape_change")
    if shape in ("flattened", "unflattened"):
        return f"<p>{escape_html(_summary_tail(change))}</p>"
    added = [str(m) for m in details.get("added_members", [])]
    removed = [str(m) for m in details.get("removed_members", [])]
    items = [f'<li class="member-add">+ {iri_chip(m, prefixes)}</li>' for m in added]
    items += [f'<li class="member-del">&minus; {iri_chip(m, prefixes)}</li>' for m in removed]
    if not items:
        return f"<p>{escape_html(_summary_tail(change))}</p>"
    return '<ul class="member-list">' + "".join(items) + "</ul>"


# --------------------------------------------------------------------------- #
# Details list (the <dl> revealed on card expansion)
# --------------------------------------------------------------------------- #


def details_list(change: Change, prefixes: dict[str, str]) -> str:
    """Render the change's ``details`` as a semantic ``<dl>`` definition list.

    Leads with Kind / Severity / Subject / Change ID, then every remaining detail
    field (sorted, Tier 3 bookkeeping excluded). All values are HTML-escaped.
    """
    rows: list[tuple[str, str]] = [
        ("Kind", f"<code>{escape_html(change.kind)}</code>"),
        ("Severity", f"<code>{escape_html(change.severity)}</code>"),
    ]
    if change.subject:
        rows.append(("Subject", f"<code>{escape_html(change.subject)}</code>"))
    change_id = change.details.get("change_id")
    if change_id:
        rows.append(("Change ID", f"<code>{escape_html(str(change_id))}</code>"))
    for key in sorted(change.details):
        if key in _HIDDEN_DETAIL_KEYS or key == "change_id":
            continue
        rows.append((_humanise_key(key), _render_detail_value(change.details[key])))
    body = "".join(f"<dt>{escape_html(label)}</dt><dd>{value}</dd>" for label, value in rows)
    return f'<dl class="details-list">{body}</dl>'


def _render_detail_value(value: object) -> str:
    """Stringify one detail value for the ``<dl>``, escaping all text."""
    if value is None:
        return "&mdash;"
    if isinstance(value, list):
        if not value:
            return "&mdash;"
        return ", ".join(f"<code>{escape_html(str(item))}</code>" for item in value)
    if isinstance(value, dict):
        parts = [f"{escape_html(str(k))}={escape_html(str(v))}" for k, v in sorted(value.items())]
        return f"<code>{', '.join(parts)}</code>"
    return f"<code>{escape_html(str(value))}</code>"


def _humanise_key(key: str) -> str:
    """``entity_iri`` → ``Entity iri`` for a definition-list term."""
    return key.replace("_", " ").capitalize()


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def _entity_addremove(kind: str) -> tuple[str, str] | None:
    """Split ``class_added`` → ``("Class", "added")`` for entity kinds, else ``None``."""
    for action in ("added", "removed"):
        suffix = f"_{action}"
        if kind.endswith(suffix):
            entity_kind = kind[: -len(suffix)]
            if entity_kind in _KIND_NOUN:
                return _KIND_NOUN[entity_kind], action
    return None


def _union_parts(kind: str) -> tuple[str, str] | None:
    """Split ``domain_union_changed`` → ``("domain", "changed")``, else ``None``."""
    for ctx in _UNION_NOUN:
        for action in ("added", "removed", "changed"):
            if kind == f"{ctx}_union_{action}":
                return ctx, action
    return None


def _annotation_title(change: Change) -> str:
    """Title for an annotation change: Label / Comment / Annotation + the action."""
    predicate = _str(change.details.get("predicate_short"))
    noun = {"label": "Label", "comment": "Comment"}.get(predicate, "Annotation")
    action = change.kind.rsplit("_", 1)[-1]  # added / removed / changed
    return f"{noun} {action}"


def _summary_tail(change: Change) -> str:
    """The producer summary after the first ``": "`` (synthetic URNs shortened)."""
    summary = " ".join(shorten_synthetic_iri(tok) for tok in change.summary.split(" "))
    _, sep, tail = summary.partition(": ")
    return tail if sep else summary


def _parent_set(parents: object, prefixes: dict[str, str]) -> str:
    """Comma-joined parent IRI chips, or ``(none)`` for an empty set."""
    if not isinstance(parents, list) or not parents:
        return '<span class="none">(none)</span>'
    return ", ".join(iri_chip(str(p), prefixes) for p in parents)


def _annotation_value(payload: object) -> str:
    """Pull the ``value`` out of an annotation ``before`` / ``after`` payload."""
    if isinstance(payload, dict):
        return str(payload.get("value", ""))
    if payload is None:
        return ""
    return str(payload)


# Dispatch table for kinds whose summary doesn't follow the entity / rename /
# union pattern. Kinds absent here (and not entity/rename/union) fall back to the
# producer ``summary`` — the spec's forward-compatible default.
_SUMMARY_RENDERERS: dict[str, SummaryRenderer] = {
    "restriction_added": _render_restriction,
    "restriction_removed": _render_restriction,
    "restriction_changed": _render_restriction,
    "domain_changed": _render_domain_range,
    "range_changed": _render_domain_range,
    "domain_added": _render_domain_range,
    "domain_removed": _render_domain_range,
    "range_added": _render_domain_range,
    "range_removed": _render_domain_range,
    "equivalent_class_added": _render_pairwise("&equiv;"),
    "equivalent_class_removed": _render_pairwise("&equiv;"),
    "disjoint_added": _render_pairwise("&perp;"),
    "disjoint_removed": _render_pairwise("&perp;"),
    "class_parent_added": _render_parent("gained"),
    "class_parent_removed": _render_parent("lost"),
    "property_parent_added": _render_parent("gained"),
    "property_parent_removed": _render_parent("lost"),
    "class_reparented": _render_reparented,
    "property_reparented": _render_reparented,
    "annotation_changed": _render_annotation,
    "annotation_added": _render_annotation,
    "annotation_removed": _render_annotation,
    "ontology_metadata_changed": _render_ontology_metadata,
    "entity_deprecated": _render_deprecation,
    "entity_undeprecated": _render_deprecation,
    "datatype_facet_added": _render_summary_tail,
    "datatype_facet_removed": _render_summary_tail,
    "datatype_facet_changed": _render_summary_tail,
    "datatype_base_changed": _render_summary_tail,
    "replaced_by_set": _render_summary_tail,
    "replaced_by_unset": _render_summary_tail,
}
