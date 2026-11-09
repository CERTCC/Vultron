---
title: "Protocol Specification: Known Gaps"
description: >
  The protocol and foundation requirements that the tests do not show the
  reference implementation's main branch fully meets, generated from the test
  suite.
stakeholder_type: [platform-developer]
level: 400
page_type: reference
subject: neutral
---

# Protocol Specification Known Gaps

This page lists each `protocol` and `foundation` requirement of the [Vultron Protocol Specification](index.md) that the tests do not show the `main` branch of the reference implementation fully meets.
It is generated from the tests on `main`, so it cannot fall behind them.
When the tests show that `main` meets all of a requirement, the requirement leaves this page.

The page has three sections.
The first lists the requirements that a test shows `main` does not yet meet, with the issues that track the work.
The second lists the requirements that `main` meets only in part.
Some of their tests pass, but at least one test shows a part that `main` does not yet do, and the issues that track that part are named.
The third lists the requirements that no test checks.
A requirement in the third section is not known to be missing from `main`: no test shows `main` does it.

The page describes the reference implementation, not the protocol.
For the questions that the specification itself leaves unresolved, see [Open Questions](open-questions.md).
Each requirement links to its row in the [Requirements Catalog](requirements/index.md).

{% include-markdown "./_known-gaps.md" %}
