---
stakeholder_type: [platform-developer]
level: 300
---

# Message Semantics

This page explains two basic design decisions that shape how Vultron messages
work. If you understand these decisions before you build, you will not make
errors that are hard to find later.

---

## Messages are announcements, not commands

A Vultron message is a statement that **a state change has already occurred**.
It is not a request for another party to perform an action.

When you send a message, you declare:

> "My state changed. Here is what I now know."

When you receive a message, you are told:

> "The sender observed or performed a transition. Update your model of the world."

Nothing in the message tells you to act. Your own logic decides what to do
in response.

This is easy to mis-read. A message named "Fix Deployed" sounds like a
command. It is not. It is a report: the sender deployed the fix, and you
are now being told.

### Work happens outside the protocol

Participants do much work that the protocol never sees:

- Reproducing a vulnerability
- Root cause analysis
- Developing a fix
- Deploying a patch
- Preparing a public advisory

When that work produces a protocol-relevant outcome — a vendor is now aware, a
fix is ready, an embargo is accepted — the actor sends a message. **The work
causes the message. The message does not cause the work.**

### What receiving a message requires

Although messages are not commands, they still require action on receipt:

1. Validate the message against expected protocol state.
2. Update your local record of the case — participants, embargo status,
   case events, prior transitions.
3. Run whatever local behaviors your logic requires next.

The distinction that matters: the message tells you *what happened*. Your
implementation decides *what to do about it*.

### Why this design

The alternative — command-based messages — connects senders to receivers. A
sender would need to know what the receiver must do. The receiver would be
required to obey. In a multi-party protocol where participants span different
organisations with different systems and policies, those connections will not
work.

Announcement-based messages let each actor maintain its own state
independently. The sender reports its transition. The receiver reads the report
and acts according to its own logic. This keeps the actors loosely connected
and makes the protocol available in any language or framework.

!!! note "Relationship to Protocol Event Flow"

    This page focuses on what individual messages *mean*. For how messages
    cause chains of automated consequences, see
    [Protocol Event Flow](protocol_flow.md).

---

## Object verbosity and selective disclosure

Vultron messages carry objects inline. When you send a message about a case,
the case object travels with it. When you send a message about a report, the
report object is included.

The default is **full inline objects**. The receiver can process the message
without querying the sender's data store, because everything needed is in the
message.

There is a tradeoff. Full objects are large, and they share all their fields
with everyone who receives the message. For most messages in a running case,
that is fine. For some, it is not.

### The selective disclosure problem

Consider inviting a new participant to a case. The case contains sensitive
vulnerability details. The participant has not yet agreed to the embargo. You
want them to have enough information to decide whether to accept the invitation
— but you do not want to share the full vulnerability details before they have
agreed to the embargo terms.

Sending a full case object to an unconfirmed participant defeats the purpose
of the embargo. But sending a message with no case object at all leaves the
participant without enough context to decide.

The solution is a **stub object**. This is a small object that carries only
enough information for the message to be routed and understood, without
sharing restricted content.

### The stub object pattern

The protocol specification defines the stub the protocol uses, the **case stub**, in [§11.2 Invitation and Acceptance](../reference/vultron-spec/index.md#112-invitation-and-acceptance-n).
In the specification's words, it is "a minimal description of the case carrying enough for the invitee to decide, and no vulnerability detail."
The specification, not this page, says what that description contains.
At the wire level a stub carries at least the case's `id`, which lets the recipient match it to the full case later, and its `type`, which lets messages be routed and matched correctly ([MV-10-001](../reference/specs/protocol.md#mv-10)).

A minimal stub is still valid ActivityStreams 2.0.
Almost all AS2 properties are optional, so an object with only `id` and `type` is standards-conformant.

When a recipient receives a stub, they look up the full case in their own records by its `id`, and use it if they already hold it.
If they do not, the stub is a placeholder: it does not create a new case record, and the full case is delivered separately once the invitee has been admitted and its [embargo consent](behavior_logic/use-cases/embargo-lifecycle.md) resolved ([MV-10-004, MV-10-005](../reference/specs/protocol.md#mv-10)).
A stub never overwrites a full case the recipient already holds ([MV-10-003](../reference/specs/protocol.md#mv-10)).

### When to use each

| Situation | Object form |
|---|---|
| Normal protocol messages (Create, Accept, Announce) | Full inline object |
| Inviting a participant before embargo acceptance | Case stub ([§11.2](../reference/vultron-spec/index.md#112-invitation-and-acceptance-n)) |
| Case content already confirmed with recipient | Full inline object |
| Privacy-sensitive fields must be withheld | Redacted object (a stub is permitted only for a case, [MV-10-001](../reference/specs/protocol.md#mv-10)) |

### `None` is not the same as redacted

A related concept is explicit redaction: a field is present but intentionally
withheld, not absent because the value is unknown.

In most serialization formats, `null` and a missing field are equivalent. In a
privacy-aware protocol, they are different:

- **Missing field** — the sender does not know this value, or it is not
  applicable.
- **Null / `None`** — the field exists but has no value.
- **Redacted** — the field has a value, but the sender is not sharing it with
  this recipient.

If an implementation cannot represent redaction explicitly, a receiver has a
problem. The receiver cannot tell the difference between "the case has no name"
and "the case name is withheld from you." For protocol-correct behavior,
implementations must treat these as different cases rather than combining them
into a single null value.

---

## Summary

| Concept | Statement |
|---|---|
| Message semantics | Messages announce completed transitions. They are not commands. |
| Sender role | "My state changed. Here is what I now know." |
| Receiver role | Update your model; your own logic decides what to do next. |
| Work and messages | Work causes messages. Messages do not cause work. |
| Full objects | Default for protocol messages; receivers can process without querying sender. |
| Stub objects | A case stub ([§11.2](../reference/vultron-spec/index.md#112-invitation-and-acceptance-n)); used when full object disclosure is premature. |
| Redaction | Explicit "withheld" is different from null or absent. |

---

## Further reading

- [Protocol Event Flow](protocol_flow.md) — how messages cause chains of consequences
- [The Case Model](case_lifecycle/case_model.md) — the shared record that messages coordinate around
- [Capability Model](capability_model/index.md) — external services that supply judgements actors cannot make alone
