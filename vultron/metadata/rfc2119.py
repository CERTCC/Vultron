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
"""RFC 2119 keywords in prose, and the code spans that only quote one.

Two checks count keywords: the Protocol Specification fragment check
(:mod:`vultron.metadata.docs.rfc2119_keywords`, DF-12-013) and the compound
requirement check (:mod:`vultron.metadata.specs.statement_style`, MS-03-001).
Both read a keyword inside an inline code span as a quoted name, not an
obligation, so both strip the spans with :func:`strip_code_spans` first.

A negated keyword (``MUST NOT``, ``SHALL NOT``, ``NOT RECOMMENDED``) is one
match: :data:`KEYWORD_RE` matches its keyword word, and ``NOT`` is not one.
"""

from __future__ import annotations

import re

KEYWORD_RE = re.compile(
    r"\b(?:MUST|SHALL|SHOULD|MAY|REQUIRED|RECOMMENDED|OPTIONAL)\b"
)
"""One RFC 2119 keyword, matched in capitals only (RFC 8174)."""

CODE_SPAN_RE = re.compile(r"(?<!`)(`+)(?!`).+?(?<!`)\1(?!`)")
"""One inline code span, delimited by a matching run of backticks."""


def strip_code_spans(text: str, replacement: str = "") -> str:
    """Return *text* with each inline code span replaced by *replacement*."""
    return CODE_SPAN_RE.sub(replacement, text)


def keywords_in(text: str) -> list[str]:
    """The RFC 2119 keywords in *text* outside its inline code spans."""
    return KEYWORD_RE.findall(strip_code_spans(text))


__all__ = ["CODE_SPAN_RE", "KEYWORD_RE", "keywords_in", "strip_code_spans"]
