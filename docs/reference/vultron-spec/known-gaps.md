---
title: "Protocol Specification: Known Gaps"
description: >
  The protocol and foundation requirements that no passing test shows the
  reference implementation's main branch meets, generated from the test suite.
stakeholder_type: [platform-developer]
level: 400
page_type: reference
subject: neutral
---

# Protocol Specification Known Gaps

This page lists each `protocol` and `foundation` requirement of the [Vultron Protocol Specification](index.md) that no passing test shows the `main` branch of the reference implementation meets.
It is generated from the tests on `main`, so it cannot fall behind them.
When a test that shows `main` meets a requirement is added, the requirement leaves this page.

The page has two sections.
The first lists the requirements that a test shows `main` does not yet meet, with the issues that track the work.
The second lists the requirements that no test checks.
A requirement in the second section is not known to be missing from `main`: no test shows `main` does it.

The page describes the reference implementation, not the protocol.
For the questions that the specification itself leaves unresolved, see [Open Questions](open-questions.md).
Each requirement links to its row in the [Requirements Catalog](requirements/index.md).

{% include-markdown "./_known-gaps.md" %}
