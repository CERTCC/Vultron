#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Field descriptions for the configuration reference page, cleaned safely.

A description is a field's ``Attributes:`` docstring entry, else its
``Field(description=...)``. Every heuristic here either applies cleanly or
raises :class:`ConfigReferenceError`, so the strict docs build fails instead
of publishing a mangled row.
"""

from __future__ import annotations

import inspect
import re

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from vultron.metadata.docs.config_reference.errors import (
    ConfigReferenceError,
    field_ref,
)

_ATTRIBUTES_HEADER = "Attributes:"
_ATTRIBUTE_ENTRY = re.compile(r"^(?P<name>\w+):\s*(?P<text>.*)$")
# A sentence ends at a period followed by space, except after "e.g." / "i.e.".
_SENTENCE_BREAK = re.compile(r"(?<!e\.g\.)(?<!i\.e\.)(?<=\.)\s+")
# A sentence that starts like one of the dropped kinds below ...
_DROP_CANDIDATE = re.compile(r"^(?:Defaults?\b|Override via\b|See ``)")
# ... is dropped only when it is nothing but the default, the variable or the
# pointer; anything longer raises rather than lose what it adds.
_DEFAULT_SENTENCE = re.compile(
    r"^(?:Defaults? to|Default:?)\s+"
    r"(?:``[^`]+``|an empty list|[\d.]+(?:\s*[a-z]+)?(?:\s*\([^()]*\))?)\.$"
)
_OVERRIDE_SENTENCE = re.compile(r"^Override via ``(?P<var>VULTRON_\w+)``\.$")
_POINTER_SENTENCE = re.compile(r"^See ``[\w.]+``\.$")
_SPHINX_ROLE = re.compile(r":(?:class|func|data|attr|meth|mod):`~?([\w.]+)`")
# An issue number is dropped only where it sits in a citation list: after a
# comma or semicolon, or first inside a parenthesis. Anywhere else (``see #12``)
# dropping it would leave a dangling phrase, so it stays and fails the build.
_ISSUE_REF = re.compile(
    r"[,;]\s*(?:issue\s+)?#\d+|(?<=\()(?:issue\s+)?#\d+(?:[,;]\s*)?"
)
_EMPTIED_PARENS = re.compile(r"\s*\(\s*\)")
_DOUBLE_BACKTICK = re.compile(r"``(.+?)``")
_CODE_SPAN_SPLIT = re.compile(r"(``.+?``)")
# Markup a cleaned description must not keep: an unconverted role anywhere,
# and in its prose an unbalanced RST span, punctuation orphaned by a removed
# pointer, or an issue number outside a citation list.
_LEFTOVER_MARKUP = re.compile(r"``|\(\s*\)|\s[.,;]|#\d")
_LEFTOVER_ROLE = re.compile(r":\w+:`")
_MARKDOWN_CODE_SPAN = re.compile(r"(?<!`)`[^`]+`(?!`)")

#: Python literals in code spans, rewritten into the page's vocabulary. ``None``
#: becomes the plain word the Type and Default columns use, not a code span.
_LITERAL_WORDS = {"None": "unset", "True": "`true`", "False": "`false`"}


def _docstring_attributes(model: type[BaseModel]) -> dict[str, str]:
    """Return the ``Attributes:`` entries of *model*'s docstring by field name.

    An entry starts at the indent of the section's first entry; a deeper line
    continues the current entry. A blank line ends the current entry, and the
    next line at the docstring's own indent ends the section.
    """
    doc = inspect.cleandoc(model.__doc__ or "")
    entries: dict[str, list[str]] = {}
    current: str | None = None
    entry_indent: int | None = None
    in_section = False
    for line in doc.splitlines():
        if line.strip() == _ATTRIBUTES_HEADER:
            in_section = True
            continue
        if not in_section:
            continue
        if line and not line.startswith(" "):
            break
        stripped = line.strip()
        if not stripped:
            current = None
            continue
        indent = len(line) - len(line.lstrip())
        if entry_indent is None:
            entry_indent = indent
        match = _ATTRIBUTE_ENTRY.match(stripped)
        if match and indent == entry_indent:
            name = match.group("name")
            entries[name] = [match.group("text")]
            current = name
        elif current is not None:
            entries[current].append(stripped)
    return {name: " ".join(parts) for name, parts in entries.items()}


def _literal_span(match: re.Match[str]) -> str:
    text = match.group(1)
    return _LITERAL_WORDS.get(text, f"`{text}`")


def _strip_prose_pointers(text: str) -> str:
    """Drop issue numbers and their emptied parentheses outside code spans."""
    parts = _CODE_SPAN_SPLIT.split(text)
    for index in range(0, len(parts), 2):  # even indices are prose
        prose = _ISSUE_REF.sub("", parts[index])
        parts[index] = _EMPTIED_PARENS.sub("", prose)
    return "".join(parts)


def _keeps_sentence(sentence: str, env_var: str, ref: str) -> bool:
    """Return whether *sentence* stays in the description.

    Raises:
        ConfigReferenceError: *sentence* starts like a default, override or
            pointer sentence but says more, or names another variable.
    """
    if not _DROP_CANDIDATE.match(sentence):
        return True
    override = _OVERRIDE_SENTENCE.match(sentence)
    if override and override.group("var") != env_var:
        raise ConfigReferenceError(
            f"{ref} says {sentence!r}, but the setting's variable is"
            f" {env_var}; correct the docstring."
        )
    if (
        override
        or _DEFAULT_SENTENCE.match(sentence)
        or _POINTER_SENTENCE.match(sentence)
    ):
        return False
    raise ConfigReferenceError(
        f"{ref}: {sentence!r} starts like a default, override or pointer"
        " sentence, which the reference page drops, but it says more; move"
        " the extra fact into its own sentence so the page keeps it."
    )


def _clean_description(text: str, env_var: str, ref: str) -> str:
    """Turn docstring prose into table-cell Markdown without the default.

    Raises:
        ConfigReferenceError: A sentence cannot be dropped safely (see
            :func:`_keeps_sentence`), or the cleaned text is empty or keeps
            markup the page cannot render.
    """
    text = " ".join(text.split())
    text = _SPHINX_ROLE.sub(
        lambda m: f"``{m.group(1).rsplit('.', 1)[-1]}``", text
    )
    text = _strip_prose_pointers(text)
    kept = [
        sentence
        for sentence in _SENTENCE_BREAK.split(text)
        if sentence and _keeps_sentence(sentence, env_var, ref)
    ]
    text = _DOUBLE_BACKTICK.sub(_literal_span, " ".join(kept)).strip()
    if not text:
        raise ConfigReferenceError(
            f"{ref}'s description is empty once the default and override"
            " sentences are dropped; say what the setting does."
        )
    leftover = _LEFTOVER_ROLE.search(text) or _LEFTOVER_MARKUP.search(
        _MARKDOWN_CODE_SPAN.sub("x", text)
    )
    if leftover:
        raise ConfigReferenceError(
            f"{ref}'s cleaned description keeps {leftover.group()!r}, which"
            f" the reference page cannot render: {text!r}"
        )
    return text.replace("|", "\\|")


def field_description(
    model: type[BaseModel], name: str, field: FieldInfo, env_var: str
) -> str:
    """Return the Markdown description of *model*'s field *name*.

    Raises:
        ConfigReferenceError: The field has neither an ``Attributes:``
            docstring entry nor a ``description``, or its description cannot
            be cleaned safely (see :func:`_clean_description`).
    """
    raw = _docstring_attributes(model).get(name) or field.description
    if not raw:
        raise ConfigReferenceError(
            f"{field_ref(model, name)} has no entry under the"
            f" {model.__name__} docstring's Attributes: section and no"
            " Field(description=...); the configuration reference page needs"
            " one to describe the setting."
        )
    return _clean_description(raw, env_var, field_ref(model, name))
