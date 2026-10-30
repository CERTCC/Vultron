---
description: >
  The call-out boxes this documentation uses, and how to tell a normative page
  from an informative one.
stakeholder_type: ALL
level: 100
page_type: reference
subject: neutral
---

# Documentation Conventions

{% include-markdown "../includes/not_normative.md" %}

This page describes the conventions the documentation uses to mark different kinds of information.
It covers the call-out boxes that appear throughout the site, the badge that names each page's kind, and the banners that say whether a page states requirements.
The mathematical and diagram notation used in the formal treatment of the protocol is in [Annex C Notation Reference](vultron-spec/annex-c-notation.md) of the Protocol Specification.

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

## Page-type badges

A badge above a page's title says which of four kinds of page it is.

| Badge | What the page holds |
|---|---|
| Tutorial | A guided lesson, such as running a demo |
| How-to guide | The steps for one task the reader already knows they need to do |
| Explanation | Why the protocol and the Coordinated Vulnerability Disclosure (CVD) process work the way they do |
| Reference | Facts to look up: messages, fields, states, terms |

Pages that only point to other pages, such as the home page and the start pages, carry no badge.
The badge names the kind of page, not whether it states requirements; the banners below say that.

## Normative and non-normative pages

Not everything in this documentation about the Vultron Protocol is a normative requirement.
The normative text is the [Vultron Protocol Specification](vultron-spec/index.md), whose [§14 Requirements Catalog](vultron-spec/requirements/index.md) holds the `protocol` and `foundation` requirements.
Three banners say where a page stands relative to it.

!!! info "Recognizing normative pages"

    {% include-markdown "../includes/normative.md" %}

    The normative pages carry this banner at the top of the page.
    They are the body sections of the Protocol Specification, including its Requirements Catalog, which holds the Protocol and Foundation requirements.
    The specification's landing page, its single-page edition, its annexes, and its open questions do not carry it.

!!! info "Recognizing pages that explain the protocol's design"

    {% include-markdown "../includes/specification_governs.md" %}

    Pages that explain how the protocol is designed carry this banner at or near the top of the page.
    They include the Formal Protocol pages, the Report Management, Embargo Management, and Case State process models, the case lifecycle and behavior logic pages, and the Protocol Design pages.
    They are informative, and they predate the Protocol Specification, so they can lag it.
    Where such a page and the specification differ, the specification governs.

!!! info "Recognizing non-normative pages"

    {% include-markdown "../includes/not_normative.md" %}

    Pages that do not contain normative requirements are marked with this banner at or near the top of the page, as this one is.
    The banner may be omitted where a page contains no requirement-like statements.
    It appears where that might not be clear, for example on a page that describes a specific implementation in SHOULD, MUST, and MAY statements that are not normative requirements of the protocol.

## Further reading

- [Annex C Notation Reference](vultron-spec/annex-c-notation.md) — the mathematical and diagram notation used in the formal treatment of the protocol
- [Glossary](glossary.md) — the terms this documentation uses, with the aliases to avoid
