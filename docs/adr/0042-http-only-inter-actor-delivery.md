---
status: accepted
date: 2026-07-28
deciders: Vultron maintainers
consulted: CERT/CC CVD research team
informed: Vultron contributors
---

# Deliver All Inter-Actor Communication over HTTP; Retire the In-Process ASGI Delivery Shortcut

## Context and Problem Statement

Vultron's outbound delivery port (`ActivityEmitter`) currently has a
production default adapter, `ASGIEmitter`, that special-cases delivery to
**co-located** actors: when a recipient's scheme+netloc matches the local
server, the emitter delivers the activity *in-process* by invoking the local
ASGI application directly (via `httpx.ASGITransport`), bypassing a real HTTP
request. Only recipients on a different host/port fall through to HTTP POST
(`DemoHttpDeliveryAdapter`).

This in-process shortcut makes the co-located case behave differently from
the remote case. Vultron's protocol model treats every actor as an
**independent, autonomous federated peer** whose only knowledge of the world
comes from Activities it has *received* over its inbox (the Actor Knowledge
Model, AKM-01). The ASGI shortcut violates the spirit of that model in
practice: demos and tests that run actors co-located in one process exercise
a delivery path that would not exist if those actors were deployed as
separate containers. The result is false confidence — inter-actor delivery
bugs (addressing, serialization, inbox routing) can be masked in-process and
only surface once actors are genuinely separated.

The shortcut also carries accidental complexity that exists *solely* to
support in-process delivery: a `contextvars` reentrancy guard, scheme+netloc
locality classification, and mount-prefix stripping (root cause of several
delivery bugs: #531, #534, #557, and #558).

Should Vultron keep the co-located ASGI fast path, or deliver everything
uniformly over HTTP as if every recipient were remote?

## Decision Drivers

- **Fidelity to the autonomous-actor model.** "Something that works for
  remote must work for local too." Actors are independent peers; delivery
  should not depend on co-location.
- **Bug visibility.** In-process delivery hides inter-actor delivery defects
  that would appear in a real multi-container deployment.
- **Simplicity.** The reentrancy guard, locality check, and mount-prefix
  stripping exist only because of the in-process shortcut.
- **Agent/developer confusion.** Two delivery mechanisms behind one port read
  as two rival "paths"; contributors are unsure which to follow when
  diagnosing delivery failures (the originating concern, #1723).

## Considered Options

- **Option A — Keep `ASGIEmitter` as the production default** (status quo).
- **Option B — Deliver all inter-actor communication over HTTP; retire the
  in-process ASGI shortcut.** A single HTTP delivery adapter becomes the sole
  production `ActivityEmitter`. Co-located recipients are delivered to over
  HTTP loopback exactly like remote recipients, including the CaseActor's
  `cc:`-to-self ledger-authoring copy.

## Decision Outcome

Chosen option: **Option B — HTTP-only inter-actor delivery.**

All inter-actor communication is delivered over the REST inbox/outbox HTTP
API. The `ActivityEmitter` production default is a single HTTP delivery
adapter (`HttpDeliveryAdapter`, renamed from `DemoHttpDeliveryAdapter`). There
is no co-located special case: a recipient hosted on the same server receives
its activity via HTTP POST to `{actor}/inbox/` just like any remote recipient.
The CaseActor's canonical-ledger self-delivery (adding its own URI to `cc:`
so a copy loops back to its own inbox) is delivered over **HTTP loopback** to
its own inbox — the same code path as every other recipient.

**Application code MUST NOT construct `httpx.ASGITransport` directly.** The
sole exception is FastAPI's `TestClient`, which uses `ASGITransport`
internally to drive a *single* application's own endpoints; that is the
standard FastAPI test tool and is not an inter-actor delivery mechanism.

### Consequences

- Good — co-located and remote delivery are identical; demos faithfully model
  autonomous actors.
- Good — inter-actor delivery bugs surface in-process instead of hiding.
- Good — removes the reentrancy guard, locality classification, and
  mount-prefix stripping.
- Good — one delivery adapter behind the port; no "which path?" ambiguity.
- Bad — the in-process demo test suite must route cross-actor delivery through
  each actor's `TestClient` rather than a hand-rolled `ASGITransport`; the
  test infrastructure must change before the production adapter is retired.
- Neutral — production co-located deployments incur a real HTTP loopback
  request per co-located delivery instead of an in-process call; acceptable
  for a protocol prototype and consistent with the autonomous-actor model.

## Validation

- The production `ActivityEmitter` default resolves to `HttpDeliveryAdapter`;
  `ASGIEmitter` is deleted.
- A ratchet/grep test asserts no application module (outside FastAPI
  `TestClient` usage) constructs `httpx.ASGITransport`.
- Existing demo and multi-actor integration tests pass with delivery routed
  over HTTP.

## More Information

Supersedes the ASGIEmitter design recorded in `specs/architecture.yaml`
ARCH-17 (ASGIEmitter Base URL / reentrancy guard). Affected specs and notes:
`architecture.yaml` ARCH-17, `multi-actor-demo.yaml` DEMOMA-01,
`case-ledger-processing.yaml` CLP-10, `outbox.yaml` OX-08, and
`notes/architecture-adapters.md` / `vultron/adapters/driven/AGENTS.md`.

Source concern: #1723. Related bugs originally caused by the in-process
shortcut: #531, #534, #557, #558.

Generated spec requirements: `outbox.yaml` OX-12-001 through OX-12-004
(uniform HTTP delivery, ASGIEmitter removal, no direct `ASGITransport` in
application code, HTTP loopback self-delivery). Supersedes
`architecture.yaml` ARCH-17-001 and ARCH-17-002.
