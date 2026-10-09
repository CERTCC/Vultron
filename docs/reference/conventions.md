---
description: >
  The call-out boxes this documentation uses, and how to tell a normative page
  from an informative one.
stakeholder_type: ALL
level: 100
---

# Documentation Conventions

{% include-markdown "../includes/not_normative.md" %}

This page describes the conventions the documentation uses to mark different kinds of information.
It covers the call-out boxes that appear throughout the site and the banners that say whether a page states requirements.
The mathematical and diagram notation used in the formal treatment of the protocol is on the [Notation](notation.md) page.

## Call-out boxes

This documentation uses the [*admonitions*](https://squidfunk.github.io/mkdocs-material/reference/admonitions/){:target="_blank"} (call-out boxes) provided by [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/){:target="_blank"} to set specific kinds of information apart from the surrounding text.
Each kind of box has one meaning, shown below.

!!! note ""

    Statements in boxes like this are normative requirements.
    The words SHOULD, MUST, MAY, and their negations follow the [Request for Comments (RFC) 2119](https://tools.ietf.org/html/rfc2119){:target="_blank"} conventions.

!!! note "Formalisms"

    Boxes with a title, like this one, hold a formal statement of something the surrounding text says in prose.

    $$A = A$$

    The text is written so that a reader can follow the protocol without reading the formalisms.
    They are included for completeness.

!!! info

    Statements in boxes like this are informative notes.
    They add information that helps in understanding the normative requirements but does not itself state a requirement.

!!! tip

    Statements in boxes like this are tips.
    They point to other resources or add context that helps in understanding the protocol.

!!! quote

    Boxes like this quote another document, such as the *CERT Guide to Coordinated Vulnerability Disclosure* or a standard.
    The text before or after the box says where the quotation comes from.

!!! example

    Boxes like this hold a worked example: a concrete case, message, or sequence of events that illustrates the surrounding text.

!!! question

    Boxes like this pose a question the protocol has not yet settled, or one a reader is likely to ask.
    The text that follows gives the current answer, or says that there is none yet.

!!! success

    A box like this at the top of a page says that the page contains normative content.
    The [next section](#normative-and-non-normative-pages) shows the banner itself.

!!! warning

    Boxes like this warn of a real hazard — an embargo breach, a protocol violation, a loss of data — or, as the banner at the top of this page does, that a page's SHOULD and MUST statements are not normative.
    They are not used for emphasis.

Material for MkDocs supports a number of other [admonitions](https://squidfunk.github.io/mkdocs-material/reference/admonitions/){:target="_blank"}.
This documentation keeps its usage consistent with the admonition names in the Material for MkDocs [documentation](https://squidfunk.github.io/mkdocs-material/reference/admonitions/){:target="_blank"}, and the ones used here are listed above for completeness.
An admonition used on some page but not listed here, or an inconsistency with the meanings above, can be reported by [opening an issue](https://github.com/CERTCC/Vultron/issues){:target="_blank"}.

## Normative and non-normative pages

Not everything in this documentation about the Vultron Protocol is a normative requirement.
The banners below say whether a page contains normative requirements.

!!! info "Recognizing normative pages"

    {% include-markdown "../includes/normative.md" %}

    Pages that contain normative requirements are marked with this banner at or near the top of the page.

!!! info "Recognizing non-normative pages"

    {% include-markdown "../includes/not_normative.md" %}

    Pages that do not contain normative requirements are marked with this banner at or near the top of the page, as this one is.
    The banner may be omitted where a page contains no requirement-like statements.
    It appears where that might not be clear, for example on a page that describes a specific implementation in SHOULD, MUST, and MAY statements that are not normative requirements of the protocol.

## Further reading

- [Notation](notation.md) — the mathematical and diagram notation used in the formal treatment of the protocol
- [Glossary](glossary.md) — the terms this documentation uses, with the aliases to avoid
