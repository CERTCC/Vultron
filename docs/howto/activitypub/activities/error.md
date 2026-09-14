# Error Handling

Vultron partitions fault reporting by **failure mode**, not by state machine.
Three mechanisms cover all cases (MSM-05-001):

| Mechanism | When to use |
|---|---|
| `Create(ProcessingFault)` | Message received but **not understood** (format error, unknown type, parse failure) |
| `as:Reject` | Message received and understood but **declined** (invalid state, rule violation, unauthorized) |
| `Create(Note)` / `Add(Note)[target=VulnerabilityCase]` | Condition requires **narrative explanation** (human attention needed) |

!!! warning "as:Reject is overloaded"

    `as:Reject` also carries ordinary protocol refusals such as `close_report`,
    `reject_invite_to_embargo_on_case`, `reject_invite_actor_to_case`,
    `reject_case_proposal`, and `reject_case_ownership_transfer`.
    A receiver MUST NOT infer error semantics from `as:Reject` alone
    (MSM-05-003).

The formal protocol defines per-model error shorthands — $RE$ (RM), $EE$ (EM),
$CE$ (CS), and $GE$ (General) — but these have no direct AS2 wire counterpart.
The failure-mode partition above is how those shorthands are realised on the
wire. See [Message Types](../../../reference/formal_protocol/messages.md) and
`specs/message-semantics-mapping.yaml` MSM-05.

!!! note "Name note"

    `VultronError` in `vultron/errors.py` is a Python exception base class,
    unrelated to protocol wire-level error messages.
