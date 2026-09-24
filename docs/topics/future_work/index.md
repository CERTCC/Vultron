---
stakeholder_type: [platform-developer, project-contributor]
level: 300
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

<div class="grid cards" markdown>

- :material-lan-connect: [Federation](federation.md)
- :material-help-circle-outline: [Open questions](open_questions.md)

</div>

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
