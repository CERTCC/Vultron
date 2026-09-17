# Future Work

This section covers design areas that Vultron anticipates and does not yet implement.
It exists so that a reader can tell the difference between a capability the protocol rules out and one that has not been built yet.
Almost everything here falls in the second category.

The prototype demonstrates coordination logic.
It is not a deployable service, and several of the things a deployment would need — message signing, encryption, actor discovery, multi-instance federation — are described here rather than implemented.
Where a design exists, this section says so and points at it.
Where the decision is genuinely open, it says that instead.

<div class="grid cards" markdown>

- :material-lan-connect: [Federation](federation.md)
- :material-help-circle-outline: [Open questions](open_questions.md)

</div>

## How to read this section

Statements about what a deployment must do carry a requirement identifier, and those requirements live in the specifications with `scope: production`.
They describe an obligation that the prototype does not yet meet.

Open questions appear as call-outs, inline at the point where they first matter and collected on the [Open questions](open_questions.md) page.
Each names the issue or epic where it is tracked, so a reader who wants the current state of a discussion can find it.
