---
description: >
  Crosswalks of the Vultron Protocol against the ISO/IEC standards on
  vulnerability handling and disclosure, against SSVC, and against the CSAF
  2.1 draft, each routed to the explanation that covers it and to the
  specification section that governs it.
stakeholder_type: [cvd-practitioner]
level: 200
page_type: routing
contents: generated
---

# Standards Crosswalks

{% include-markdown "../../includes/not_normative.md" %}

Three ISO/IEC standards, one prioritization framework, and one advisory format overlap with the Vultron Protocol.
Each ISO/IEC crosswalk below maps that document's clauses to two places: the explanation page that covers the same ground, and the section of the [Vultron Protocol Specification](../vultron-spec/index.md) that states the normative requirement.
A program that already follows one of these standards can use its crosswalk to find which protocol behavior each clause it satisfies corresponds to.
Each crosswalk opens with a link to the document it maps.
The CSAF 2.1 crosswalk maps concepts instead of clauses, because CSAF is a document format and not a process standard.

<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml nav or a listed page's description: frontmatter, then run `uv run docs-site --write` -->

<!-- markdownlint-disable MD007 -->
- [ISO 30111](iso_30111_2019.md) — Clause-by-clause mapping of ISO/IEC 30111:2019 vulnerability handling processes to the Vultron Protocol's states, messages, and specification sections.
- [ISO 29147](iso_29147_2018.md) — Clause-by-clause mapping of ISO/IEC 29147:2018 vulnerability disclosure to the Vultron Protocol's states, messages, and specification sections.
- [ISO 5895](iso_5895_2022.md) — Clause-by-clause mapping of ISO/IEC TR 5895:2022 multi-party coordinated vulnerability disclosure to the Vultron Protocol's states, messages, and specification sections.
- **CSAF 2.1 Crosswalk**
    - [CSAF 2.1 and Vultron](../csaf_crosswalk/overview.md) — How the Common Security Advisory Framework (CSAF) 2.1 draft relates to a Vultron case, and a summary of where the two models are the same, close, or different.
    - [Proposals](../csaf_crosswalk/proposals.md) — Changes that the Common Security Advisory Framework (CSAF) 2.1 draft and the Vultron Protocol could make, each with its reason and its cost if nothing changes.
    - [Conclusions](../csaf_crosswalk/conclusion.md) — What the comparison of the Common Security Advisory Framework (CSAF) 2.1 draft with Vultron shows, and the follow-up work it opens on each side.
    - [Concept Mapping](../csaf_crosswalk/concept_mapping.md) — Each Vultron concept with its counterpart in the Common Security Advisory Framework (CSAF) 2.1 draft, the granularity of the match, and the type of mapping in each direction.
    - [Coverage Differences](../csaf_crosswalk/coverage.md) — Concepts that Vultron has and the Common Security Advisory Framework (CSAF) 2.1 draft does not, and concepts that CSAF has and Vultron does not.
- [SSVC Crosswalk](../ssvc_crosswalk.md) — A crosswalk of the Vultron Protocol against Stakeholder-Specific Vulnerability Categorization (SSVC).
<!-- markdownlint-enable MD007 -->

<!-- END GENERATED SECTION CONTENTS -->

The specification's own account of how it relates to these standards is [§1.3 Relationship to Existing Standards](../vultron-spec/introduction.md#13-relationship-to-existing-standards).

{% include-markdown "../../start/_paths/coordinate-cases/reference__iso_crosswalks__index.md" %}
