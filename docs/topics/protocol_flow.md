# Protocol Event Flow

## Overview

This page explains how events move through Vultron at run time. It is for implementers who want to understand *why* the protocol behaves as it does, in any programming language.

Read this page to learn three things:

- Each actor works like a worker that reads messages from a queue.
- One message can cause a chain of further messages. This is a **cascade**.
- Some steps stop because the actor must ask another actor for permission. The actor asks, and then it stops. It does not wait.

---

## An actor is a worker with two queues

Each actor in Vultron has an **inbox** and an **outbox**.

- The inbox holds messages that other actors sent to this actor.
- The outbox holds messages that this actor sends to other actors.

The actor takes one message from its inbox. It processes that message. If the result is that other actors must be told something, the actor puts new messages in its outbox. Delivery then moves each outbox message to the inbox of the actor it is addressed to.

```text
   ┌────────── Actor A ──────────┐          ┌────────── Actor B ──────────┐
   │  inbox → process → outbox   │  ──────► │  inbox → process → outbox   │
   └─────────────────────────────┘          └─────────────────────────────┘
```

This model has one important consequence. **An actor never reaches into another actor's state.** It can only send a message. The other actor decides what that message means and what to do about it. Every rule in the protocol follows from this limit.

!!! note "The queue model is a way to think, not a required design"

    Vultron does not require message-broker software. The reference
    implementation is a single process and uses ordinary HTTP requests for
    delivery. The queue model is useful because it shows the intended flow of
    information, and because it keeps a distributed implementation possible
    later.

---

## Primary events and cascades

Two kinds of things happen in Vultron, and the difference matters.

A **primary event** comes from outside the protocol. Something in the world changed, and a person, a service, or another organisation must tell Vultron. Examples:

- A finder submits a vulnerability report.
- A vendor decides the report is valid.
- A participant proposes an embargo period.

A **cascade** is everything that follows automatically from a primary event. The actor that received the primary event updates its own state and sends the messages the protocol requires. Each actor that receives one of those messages runs its own cascade. Together these form a chain.

For example, one primary event — a finder submits a report — causes this chain:

```text
finder submits report
   └── vendor records the report
         └── vendor opens a case
               └── vendor adds the finder as a participant
                     └── vendor tells the finder the case exists
```

Nobody instructs the vendor to open a case. The vendor does it because it received a report. This is the central design rule: **supply the primary event only, and let the protocol produce the consequences.**

### Why this rule is useful

The rule gives you a test for correctness. If you must send a second message by hand to make the process continue, then one of two things is true:

- That step is genuinely a new primary event, because new information from outside was needed.
- Or the implementation has a gap, because the step should have happened automatically.

The test tells you which kind of problem you have. It is the reason Vultron test scenarios inject only primary events and then check the resulting state.

---

## Causal order, not time order

It is natural to describe a process as a list of steps in time: *A, then B, then C*. The protocol is not built on time. It is built on cause: *A, and therefore B, and therefore C*.

The difference is not a matter of style. Delivery and processing take time, and they can fail. So "B happened five seconds after A" tells you almost nothing, while "B happened because A happened" tells you the process is correct.

A single step between two actors is really a chain of smaller events:

```text
A addresses → A sends → arrives at B → B processes → B records → B replies
                                                          ▲
                                                   the only proof
```

Only the last links prove anything. That a message was *sent* proves only that the sender tried. That it *arrived* proves only that the network worked. That the receiver **recorded** it proves the receiver accepted it and acted.

If you write tests or monitoring for a Vultron implementation, check the recorded state of the actor that owns the effect, and read it from that actor. Do not accept elapsed time as evidence, and do not accept an acknowledgement of receipt as evidence that processing succeeded.

---

## When an actor must ask permission

Some steps in a cascade cannot be automatic, because the actor is not allowed to decide alone. A participant may report that a vulnerability is now public. Whether that report becomes the shared, agreed state of the case is not the reporting participant's decision. The case owner decides.

Here Vultron does something that surprises people. The actor **asks, and then it stops.**

```text
1. Actor needs permission.
2. Actor sends the case owner a request that carries a deadline.
3. Actor finishes.  Its work succeeded, because asking was the work.
4. Later, the case owner replies: agreed, or refused.
5. That reply is a new message. It arrives in an inbox, and it starts new work.
```

Step 3 is the part worth understanding. **Success means "I asked", not "I was told yes."** Nothing is left waiting or held open. The work is divided at the question rather than paused there. Asking is one complete piece of work; acting on the answer is another piece of work, and the answer's arrival is what starts it.

This is why the request carries a **deadline**. The deadline is part of the message, so the case owner can see how long they have, and the asking actor knows when the question has gone stale.

### What happens while the actor waits

Nothing is held open, so the case must be in a sensible state during the wait. It usually already is. In the example above, the participant's report is recorded as *what that participant claims*. Only its promotion to *what the case agrees* waits for permission. Those are two different facts, and recording the first while the second is undecided is honest and useful.

This gives a rule for implementers: **you may only ask about an action whose not-yet-done state can be described.** If "not yet decided" cannot be represented, the actor must refuse instead of asking, because there is nowhere for the case to rest.

### Asking twice, and not asking twice

Because an actor stops after asking, it may reach the same point again later — for instance, when the same participant reports the same thing again. So an actor that reaches a step needing permission first works out **where the conversation stands**:

| What the actor finds | What it does |
|---|---|
| A reply agreeing | Do the action. |
| A reply refusing | Do not do the action. Record the refusal. |
| A request already sent, deadline not passed | Nothing. Do not ask twice. |
| A request already sent, deadline passed | Ask again, with a new deadline. |
| No request yet | Record the not-yet state, ask, and stop. |

These situations do not overlap, so returning to this step is always safe. The actor never repeats work it has already done, because it never enters that path a second time.

### What a late reply means

Some questions are still worth answering late. Whether to admit a new participant to a case is one — the answer is as useful next week as it is today.

Other questions are not. Permission to change the agreed state of a case is granted against the case as it was when the question was asked. If the reply arrives after the deadline, the case may have moved on: an embargo may have been agreed, or another participant may have published. Acting on that permission would apply an old decision to a new situation.

So each kind of request declares which it is. For requests of the second kind, **a late reply does not grant permission**, and the asking actor must ask again if it still wants to act. This is the same caution applied to time that the protocol already applies to identity: the request, not the reply, is the authority for what was permitted.

### The request is the authority

When a reply arrives, the asking actor reads what to do from **the request it sent**, and not from the contents of the reply.

This matters for security. If the actor took its instructions from the reply, the actor answering could change what it was agreeing to — granting broader permissions than were requested, and granting them to itself. A reply is only a yes or a no. The request states what was asked.

---

## Keeping track of open questions

An actor may have several questions outstanding at once, in both directions: questions it asked and is waiting on, and questions others asked that it owes an answer to.

Both lists matter, for different reasons.

The **questions I asked** list stops an actor asking the same thing twice, and lets it notice when a deadline has passed.

The **questions I owe** list is more important than it first appears. It is the list a person, an interface, or an automated service works from. Without it, a case owner has no way to discover that a decision is waiting for them, so permission could only ever be granted by accident. This list is what makes the case owner's role something they can actually perform.

Both lists are working notes. They say what is outstanding. They never say what was permitted — for that, an actor reads the recorded history of the case, which is the shared, verifiable record. Keeping these apart matters: a working note could be rebuilt or damaged, and it must never be able to authorise anything on its own.

---

## Deadlines need something to notice them

A deadline passing is not an event. No message arrives when time runs out. So something must look.

Vultron uses two mechanisms, and neither is a timer inside the protocol.

**Looking when you pass by.** The next time an actor reaches the step that asked the question, it notices the deadline has passed. This is often enough. When a message is lost, the sender usually sends it again, and that repeat is what causes both actors to look. In that case the other party's retry is the clock.

**An external watcher.** For prompt handling, an implementation can run a service that watches for passed deadlines and notifies the actor. This is deliberately outside the protocol: watching the clock is not a protocol behaviour, and keeping it outside means an implementation can choose how attentive to be. It also means deadline behaviour can be tested by asking for a check directly, rather than by waiting.

Noticing an expired request never sends it again by itself. Expiry is information. Whether the actor still wants to act is a fresh decision, and only the actor's own logic can make it.

---

## When a message cannot be understood

Messages sometimes arrive that an actor cannot process. The message may be malformed, or it may refer to something the actor does not know about, or the sender may not be permitted to send it.

Silence is a poor answer. A sender waiting for a reply would wait for its whole deadline over a failure that took a fraction of a second.

So an actor that cannot process a message from a **known, authenticated** sender tells that sender so. The reply says what kind of failure it was — enough for the sender to judge whether sending it differently would help. It does not describe the receiver's internal workings. Two reasons: those details are useless to the sender, and explaining exactly why a message was refused helps an attacker probe the receiver.

An actor does **not** answer a message it cannot authenticate. It cannot trust the sender's identity, so it has no reliable address to reply to, and answering would tell an unknown party how the receiver behaves.

There are three different situations here that are easy to confuse:

| Situation | Meaning |
|---|---|
| "I read what you claimed and I refuse it" | A decision. The receiver understood and declined. |
| "I read your question and my answer is no" | A decision. A reply that closes the question. |
| "I could not read what you sent" | Not a decision. Nothing was judged. |

Only the first two are decisions about content. The third is a report that communication failed.

This distinction decides what gets recorded in the shared history of a case. A message that could not be read is **not** recorded — there is nothing understood to record. But the statement *"I could not process the message you sent"* **is** recorded, because it is a clear and true statement about a message that arrived. It also explains something a later reader would otherwise find puzzling: why the same message was sent twice.

---

## Requests are visible to the case

A request for permission is recorded in the case's shared history, like other case events. Every participant can see that a decision is outstanding, and who owes it.

This is intentional. A stalled decision is something participants should be able to see, because it affects everyone in the case.

It also sets a limit: **a request must not contain anything that cannot be shown to every participant in the case.** If an actor needs to explain something privately, it sends a separate message addressed to one participant instead.

---

## Summary

| Idea | Statement |
|---|---|
| Actor model | Each actor reads messages from an inbox and sends messages from an outbox. No actor touches another's state. |
| Primary event | New information from outside the protocol. This is all you supply. |
| Cascade | Everything the protocol does automatically as a result. |
| Causal order | *A therefore B*, not *A then B*. Recorded state is the only proof. |
| Asking | The actor asks and stops. Success means "I asked". |
| Deadline | Part of the request, so both parties can see it. |
| Late reply | For some kinds of request it grants nothing. Ask again. |
| Authority | The request says what was asked. The reply is only yes or no. |
| Open questions | Two working lists: what I await, and what I owe. Neither authorises anything. |
| Faults | Tell an authenticated sender that a message could not be processed. Say little. |

---

## Further reading

- [Behavior Logic](behavior_logic/index.md) — how an actor decides what to do when a message arrives
- [Capability Model](capability_model/index.md) — how external services supply the judgements an actor cannot make alone
- [The Case Model](case_model.md) — the shared record that actors coordinate around
