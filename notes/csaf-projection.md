---
title: "Projecting a CSAF Document From a Case (Design Direction)"
status: draft
kind: plan
tracks:
  - "#5134"
  - "#5130"
description: >
  Design direction for producing a CSAF 2.1 document from a participant's case
  replica (ADR-0219): a call site's profile cuts the case and its ledger into a
  preview, and a CSAF renderer translates only the preview. Holds the two
  profiles, the renderer's rules, the two call sites, the layer placement and the
  requirement text the implementation adds to specs/csaf-report-content.yaml.
related_specs:
  - specs/csaf-report-content.yaml
  - specs/case-management.yaml (CM-17)
  - specs/message-validation.yaml (MV-12)
  - specs/behavior-tree-integration.yaml (BT-20-004)
related_notes:
  - notes/selective-disclosure.md
  - notes/csaf-report-content.md
  - notes/vulnerability-items.md
  - notes/core-wire-rendering-port.md
  - notes/wire-core-boundary.md
relevant_packages:
  - vultron/core/models
  - vultron/wire/csaf
  - vultron/core/behaviors/report
  - vultron/adapters/driving/fastapi
---

# Projecting a CSAF Document From a Case (Design Direction)

A participant produces a CSAF 2.1 document from its replica in two steps: its call
site's profile cuts the case into a preview, then a renderer translates the
preview into CSAF (ADR-0219). The cut uses the four operations and the per-field
profile of ADR-0217, which `notes/selective-disclosure.md` describes for the
invitation preview. Nothing here is built yet.

## The Renderer Reads Only the Preview

- **The profile withholds; the renderer selects.** The renderer may leave out a
  value the preview shows, because CSAF cannot express it. It never relies on
  leaving a value out to withhold it, so a later CVE or text renderer of the same
  preview cannot leak it (ADR-0219).
- **No case or ledger read in the renderer.** The renderer's only input is the
  preview, plus the call site's fixed settings (category, status, TLP). A
  renderer that reads the case can show what the profile withheld.
- **A redaction renders as an absence**, with no note that lists what is left
  out: a projection is a deliberate publication, not a statement of what it omits
  (ADR-0219).

## The Preview Carries a Ledger List

`CasePreview` (`vultron/core/models/case_preview.py`, built in #6372 and #6692)
gains an optional list of ledger entries, which only a render-bound profile fills.
The profile cuts the list by element, as it cuts the status history to its
current entry, so a preview may hold an incomplete ledger. The invitation profile
omits it, because ledger bookkeeping means nothing to an invitee (ADR-0217). The
drift test that checks the preview against `VulnerabilityCase` needs an explicit
exception for this list, because the ledger is not a case field.

## Two Profiles, One per Call Site

The call site picks the profile; the participant does not choose one per document
(ADR-0219). Each profile names one ADR-0217 operation for every case field, so a
new case field fails the profile check until it is classified.

| Field group | Public (publication draft step) | Joined (operator endpoint) |
|---|---|---|
| Name, summary, `published`, `updated` | include | include |
| Vulnerability items, case references | include | include |
| Reports | omit | include |
| Current case status (CS P, X, A) | substitute: current entry | substitute: current entry |
| Embargo register | omit | include |
| Participants and their status histories | omit | include, contact details omitted |
| Ledger entries | omit | include |
| `ledger_position` | include | include |
| Indexes, pending proposals, genesis hash, `case_activity`, related cases | omit | omit |

- **Public omits participants** until #5135 decides whether a case records
  public-credit preferences; crediting a participant without that decision
  publishes a name it may not want published.
- **Joined is not the invitation profile.** A recipient outside Vultron needs the
  report content and the vul details to act; an invitee does not get them before
  it accepts the embargo (ADR-0219, ADR-0217).
- **The public profile has no involvement.** It omits the ledger, so the
  document has no `involvement` list.

## Rendering Rules

- **Category `csaf_base` for every call site.** The case holds no products
  (ADR-0187), and the Vulnerability Report and Security Advisory profiles require
  `product_tree` and product status. A projection never copies a reporter's
  product tree: that republishes the reporter's claim as the projector's.
- **Version from the ledger position.** Integer versioning:
  `document.tracking.version` is `ledger_position.log_index + 1`, and the one
  `revision_history` entry has the same `number`. The projector keeps no record of
  earlier documents, so it lists no earlier revisions.
- **Identifier from case and profile.** `document.tracking.id` comes from the case
  ID and the profile name. Without the profile name, a public and a joined
  projection at one position share an id and a version but differ in content.
- **One reference names the snapshot.** A `document.references` entry of category
  `self` names the case ID and the entry hash of the ledger position.
- **TLP is fixed by the profile.** Public: `CLEAR`. Joined: `AMBER+STRICT`. How a
  label appears inside Vultron is #5133; this label belongs only to the document.
- **`tracking.status` is fixed by the call site.** Publication: `final`. Joined
  endpoint: `interim`, because the case continues to change.
- **Publisher from the projecting actor.** `publisher.name` is the actor's name,
  `publisher.namespace` the origin of its ID, and `publisher.category` follows its
  participant role: VENDOR → `vendor`, COORDINATOR → `coordinator`, FINDER or
  REPORTER → `discoverer`, else `other`.
- **Involvement from the cut ledger.** One `involvement` item per ledger entry that
  has a CSAF meaning, by the rules of the crosswalk concept mapping page
  (`docs/reference/csaf_crosswalk/concept_mapping.md`); other entries are dropped.
  Status is derived at the preview's position: `completed` for a ledger fact;
  `outstanding`, `deferred` or `discontinued` where state supports it; never
  `attempted` (an outbox fact) or `planned` (Vultron records no intentions).
- **Schema-valid.** Build the document with the generated models in
  `vultron/wire/csaf/models/` and check it against the pinned schema
  (CSAF-05-001, CSAF-05-002).

## Where the Code Goes

- **Profiles in core**, beside the invitation profile and `CasePreview.from_case`
  (#6692): a profile is a statement about case fields.
- **Renderer in `vultron/wire/csaf/`**, because CSAF is a wire format. Wire may
  import `core/models` (ARCH-22-001).
- **The draft step reaches the renderer through a port.** Core never imports wire
  (ARCH-01-001), so the deterministic backend of `DraftAdvisoryArtifact`
  (`vultron/core/behaviors/report/publish_artifact_tree.py`) cuts the preview in
  core and calls an injected render port that the adapter layer wires to the CSAF
  renderer, as `WireRenderPort` serves delivery (`notes/core-wire-rendering-port.md`).
  A missing port is a wiring error, never a fallback.
- **The operator endpoint is a read.** It reads the actor's replica, cuts it with
  the joined profile and returns the rendered JSON. It writes nothing to the
  DataLayer, adds no ledger entry and sends no activity. The operator gives the
  document to the outside party out of band.
- **No invite-site call site yet.** It waits until Vultron can invite a party that
  does not use Vultron.

## Requirement Text the Implementation Adds

These land in `specs/csaf-report-content.yaml` as group CSAF-06, "Projecting a
CSAF Document", with the code that tests them, so no requirement states a rule a
test does not check. Each cites ADR-0219.

- MUST: A CSAF projection MUST be rendered only from a case preview cut by the
  profile of its call site; the renderer MUST NOT read the case or its ledger.
- MUST NOT: A CSAF projection MUST NOT contain a value that its profile redacts
  or omits.
- MUST: The draft step of the publication pipeline MUST use the public profile,
  and the operator CSAF endpoint MUST use the joined profile.
- MUST: Every profile MUST name one operation for every case field.
- MUST: A CSAF projection MUST be of category `csaf_base` and MUST pass the pinned
  CSAF 2.1 schema.
- MUST: `document.tracking.version` MUST be the integer log index of the
  preview's ledger position plus 1, and the revision history MUST hold one entry
  with that number.
- MUST: `document.tracking.id` MUST be derived from the case ID and the profile
  name.
- MUST: A CSAF projection MUST carry a `document.references` entry that names the
  case ID and the entry hash of its ledger position.
- MUST: The involvement status of a projection MUST be `completed` for a ledger
  fact, and MUST NOT be `attempted` or `planned`.
- MUST: The TLP label of a projection MUST be `CLEAR` for the public profile and
  `AMBER+STRICT` for the joined profile.
- MUST NOT: The operator CSAF endpoint MUST NOT write to the DataLayer, add a
  ledger entry or send an activity.
