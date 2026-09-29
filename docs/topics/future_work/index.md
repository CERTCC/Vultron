---
stakeholder_type: [platform-developer, project-contributor]
level: 300
contents: generated
---

# Future Work

This section gives the design areas that Vultron plans but does not supply.
It lets you find the difference between two conditions.
In the first condition, the protocol excludes a capability.
In the second condition, the project has not built the capability.
Almost all of the content in this section is in the second condition.

The prototype shows the coordination logic of the protocol.
It is not a service for deployment.
A deployment needs message signing, encryption, actor discovery, and federation across instances.
This section gives those subjects, and the prototype does not supply them.
Where a design exists, this section identifies it.
Where the design is open, this section says so.

<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml nav or a listed page's description: frontmatter, then run `uv run docs-site --write` -->

- [Federation](federation.md) — The federation model for organizations that each operate their own coordination service: what the services interchange, who has authority for a case, and how trust is built.
- [Open Questions](open_questions.md) — Every unresolved design question in the Future Work section, collected in one place with the issue or epic that records it.

<!-- END GENERATED SECTION CONTENTS -->

## How to read this section

A statement about the obligations of a deployment gives a requirement identifier.
Those requirements are in the specifications, and their scope is not uniform.
Some have `scope: production`, and the prototype does not obey them.
Each requirement in `specs/encryption.yaml` is of this type.
Others apply to the prototype as well, and the prototype does obey them.
The text says which condition applies at each point.

Open questions are in call-out boxes.
Each open question is at the point in the text where it first applies.
The [Open questions](open_questions.md) page also collects all of them.
Each open question identifies the issue or the epic that records it.
You can go to that issue or epic for the current condition of the discussion.
