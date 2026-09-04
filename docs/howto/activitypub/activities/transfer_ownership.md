# Transferring Case Ownership

{% include-markdown "../../../includes/not_normative.md" %}

Transfer if case ownership was not part of the original Vultron protocol, but it seems like a
reasonable extension that could be useful in some cases, such as transferring a
case

- from a researcher to a vendor
- from a vendor to an upstream vendor
- from a vendor to a coordinator
- from a coordinator to a vendor
- between coordinators

The presumption here is that the initial creator of a case is its owner.
Subsequent to that, the existing owner can offer to transfer ownership to
another participant. The new owner can then accept or reject the offer.

We use a sequence diagram instead of a flow chart since the process is
relatively simple and the sequence diagram is easier to read.

```mermaid
sequenceDiagram
    actor A as Current Case Owner
    participant CA as Case Actor
    actor B as Potential Case Owner
    A ->> CA: Offer(object=Case)
    note over CA: Record offer; forward to transferee
    CA ->>+ B: Offer(object=Case)
    note over B: Consider offer
    alt Accept Offer
        B -->> CA: Accept(object=Offer)
        CA ->> CA: Update(object=Case, new owner=B)
        note over CA: Case has new owner; broadcast
    else Reject Offer
        B -->> CA: Reject(object=Offer)
        note over CA: Case ownership unchanged
    end
    deactivate B
```

!!! info "CaseActor routing (ADR-0053, CM-21-005, CM-21-006)"

    Per ADR-0053, both the `Offer` and the `Accept` MUST be routed through the
    **Case Actor**, not sent directly between the current and prospective owners.
    The current owner sends `Offer(VulnerabilityCase)` to the Case Actor's inbox;
    the Case Actor forwards it to the transferee. The transferee addresses their
    `Accept` or `Reject` to the Case Actor, which then applies the role change and
    broadcasts the result to all participants.

!!! note "What the demo shows"

    The demo follows the diagram above: it POSTs the `Offer` to the Case Actor's
    inbox, waits for the Case Actor's *forwarded* `Offer` to reach the transferee,
    and addresses the transferee's `Accept` or `Reject` back to the Case Actor.

    The forwarded `Offer` is a **new** activity with its own id, so the demo finds
    it by matching on its properties (`Offer` whose `target` is the transferee and
    whose `object` is the case) rather than by looking up the original offer's id —
    which only ever exists in the Case Actor's own store.

    The demo also needs a Case-Actor-owned case to route through: a case minted by
    the vendor itself has no `CASE_MANAGER` participant, and with no Case Actor to
    address the routing falls back to the direct path (CM-24-003).

## Offer Case Ownership Transfer

The current owner of a case can offer to transfer ownership of the case to
another participant.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import offer_case_ownership_transfer, json2md

print(json2md(offer_case_ownership_transfer()))
```

## Accept Case Ownership Transfer

The new owner of a case can accept an offer to transfer ownership of the case
to them.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import accept_case_ownership_transfer, json2md

print(json2md(accept_case_ownership_transfer()))
```

## Reject Case Ownership Transfer

The proposed new owner of a case can reject an offer to transfer ownership of
the case to them. In this case, the case ownership transfer is cancelled, and the
case ownership remains with the original owner.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import reject_case_ownership_transfer, json2md

print(json2md(reject_case_ownership_transfer()))
```

## Update Case

The case object is updated to reflect the new owner of the case.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import update_case, json2md

print(json2md(update_case()))
```

## Demo

!!! example "Try it: `vultron-demo transfer-ownership`"

    Run this workflow end-to-end with the unified demo CLI:

    ```bash
    vultron-demo transfer-ownership
    ```

    Or with Docker Compose:

    ```bash
    DEMO=transfer-ownership docker compose -f docker/docker-compose.yml run --rm demo
    ```
