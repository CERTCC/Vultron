---
description: >
  What Vultron is, the coordination problem it addresses, and the outcomes a
  Coordinated Vulnerability Disclosure case is trying to reach.
stakeholder_type: [cvd-practitioner, platform-developer, process-researcher]
level: 200
contents: generated
---

# Background

!!! tip inline end "Prerequisites"

    The [Explanation](../index.md) section assumes that you have:
    
    - an interest in learning about the Vultron Protocol
    - familiarity with the Coordinated Vulnerability Disclosure (CVD) process in general

    If you are already familiar with the Vultron Protocol, and are looking for implementation advice, see [How-to Guides](../../howto/index.md).
    For technical reference, see [Reference](../../reference/index.md).
    If you're trying to understand the CVD process, we recommend that you start with the [CERT Guide to Coordinated Vulnerability Disclosure](https://certcc.github.io/CERT-Guide-to-CVD){:target="_blank"}.

!!! tip "New to Vultron?"

    If you want a concise overview of what Vultron is, why it exists, and whether it is relevant to your organization, start with [What Is Vultron?](what-is-vultron.md).

These pages explain the problem Vultron addresses and the goals it is designed toward.
Each one builds on the ones before it.

<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml nav or a listed page's description: frontmatter, then run `uv run docs-site --write` -->

- [What Is Vultron?](what-is-vultron.md) — What kind of thing Vultron is: an open protocol that lets the systems organizations already use for vulnerability disclosure coordinate a case with each other, the way email servers exchange mail.
- [CVD as a Coordination Problem](cvd-coordination-problem.md) — Why Vultron treats every Coordinated Vulnerability Disclosure case as a multi-party coordination problem, and where the protocol sits among the CERT/CC's other work on the CVD process.
- [Interoperability](interoperability.md) — Why organizations coordinating a vulnerability case need shared meaning, not only a shared message format, and what this documentation gives you toward it.
- [Defining CVD Success](cvd_success.md) — The outcomes a Coordinated Vulnerability Disclosure case is trying to reach, stated as twelve ordering preferences over six case events, and how a Coordinator acts on them during a case.

<!-- END GENERATED SECTION CONTENTS -->
