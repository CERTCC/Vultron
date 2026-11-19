---
title: "Projecting a CSAF Document From a Case (Design Direction)"
status: draft
kind: plan
tracks:
  - "#6705"
  - "#6706"
  - "#6707"
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
- **No case or ledger read in the renderer.** The renderer's inputs are the
  preview and what the call site passes beside it: its fixed settings
  (category, `tracking.status`), its profile's TLP and versioned name, the
  projecting actor (for `publisher`), the commit time of the ledger entry at the
  preview's position (for every document date), and the acknowledgments
  (ADR-0218). A renderer that reads the case can show what the profile withheld.
- **A redaction renders as an absence**, with no note that lists what is left
  out: a projection is a deliberate publication, not a statement of what it omits
  (ADR-0219).

## The Preview Carries a Ledger List

`CasePreview` (`vultron/core/models/case_preview.py`; #6372 and #6692 build its
profile model and `CasePreview.from_case`) gains an optional list of ledger
entries (#6705), which only a render-bound profile fills. This extends ADR-0217,
whose preview holds case fields only (ADR-0219).
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
| `content`, `notes` | omit | include |
| Reports | omit | include |
| Case Owner (`attributed_to`) | omit | include |
| Current case status (CS P, X, A) | substitute: current entry | substitute: current entry |
| Embargo register | omit | include |
| Participants and their status histories | omit | include |
| Ledger entries | omit | substitute: entries with a CSAF meaning, each payload snapshot cut by this profile |
| `ledger_position` | include | include |
| `stub_summary` | omit | omit |
| Indexes, pending proposals, genesis hash, related cases | omit | omit |
| Any other AS2 property | omit | omit |

- **Public omits participants.** A case records no public credit (ADR-0218), so
  the public document does not take its acknowledgments from the participant
  list (see "Rendering Rules").
- **Joined is not the invitation profile.** A recipient outside Vultron needs the
  report content and the vul details to act; an invitee does not get them before
  it accepts the embargo (ADR-0219, ADR-0217).
- **Joined cuts each ledger payload.** A ledger entry's `payload_snapshot` holds
  the activity verbatim, so an entry carried whole would show values the same
  profile omits, such as a pending proposal. The renderer must never be the only
  step that withholds (ADR-0219).
- **The public profile has no involvement.** It omits the ledger, so the
  document has no `document.involvement`.

## Rendering Rules

- **Category `csaf_base` for every call site.** The case holds no products
  (ADR-0187), and the Vulnerability Report and Security Advisory profiles require
  `product_tree` and product status. A projection never copies a reporter's
  product tree: that republishes the reporter's claim as the projector's.
- **A projection is a pure function of its identity.** No revision counter is
  kept. `document.tracking.id` is derived from the case ID, the versioned profile
  name (`public-v1`, `joined-v1`), the `log_index` of the preview's ledger
  position, and, only when the caller supplies acknowledgments, a short digest of
  that input. The profile version is bumped whenever a profile or renderer change
  alters the output.
- **Every projection is version 1.** Integer versioning: `document.tracking.version`
  is `1`, and the one `revision_history` entry has `number` `1`, so the document
  passes CSAF mandatory test 6.1.21. Regenerating a document re-issues the same
  version; it is not a revision.
- **Dates from the position, never a clock.** Every document date
  (`tracking.initial_release_date`, `tracking.current_release_date`, the
  revision entry's `date`) is the commit time of the ledger entry at the
  preview's position, so one `tracking.id` always yields a byte-identical
  document (ADR-0176).
- **One reference names the snapshot.** A `document.references` entry of category
  `self` names the case ID and the entry hash of the ledger position.
- **TLP is fixed by the profile.** Public: `CLEAR`. Joined: `AMBER+STRICT`. How a
  label appears inside Vultron is #5133; this label belongs only to the document.
- **`tracking.status` is fixed by the call site.** Publication: `final`. Joined
  endpoint: `interim`, because the case continues to change.
- **Publisher from the projecting actor.** `publisher.name` is the actor's name,
  `publisher.namespace` the origin of its ID, and `publisher.category` follows the
  first participant role it holds, in this order: VENDOR → `vendor`,
  COORDINATOR → `coordinator`, REPORTER → `discoverer`, else `other`.
- **Acknowledgments from the caller.** A projection takes its acknowledgments
  from its caller, never from case data alone (ADR-0218). With no caller input,
  the call site supplies ADR-0218's default, the participants that hold the
  REPORTER role, derived from the case; that default needs no digest in the id.
  In `csaf_base` an absent list carries no "no credit wanted" meaning; the
  Vulnerability Report rule of ADR-0218 applies once a projection can use that
  category (#6707).
- **Involvement from the cut ledger.** `document.involvement.actions[]` holds one
  item per act whose ledger entries have a CSAF meaning, by the rules of the
  crosswalk concept mapping page
  (`docs/reference/csaf_crosswalk/concept_mapping.md`); an act's follow-on
  entries (CLP-07-021) go into that act's action, and other entries are dropped.
  Status is derived at the preview's position: `completed` for a ledger fact;
  `outstanding`, `deferred` or `discontinued` where state supports it; never
  `attempted` (an outbox fact) or `planned` (Vultron records no intentions). When
  no entry maps, `document.involvement` is left out, because its lists may not be
  empty.
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
  renderer, in the pattern of `WireRenderPort` (`notes/core-wire-rendering-port.md`).
  It is a new port, not `WireRenderPort`: that port renders one object for
  delivery, while this one takes the preview with the call site's inputs
  (settings, projecting actor, dates, acknowledgments).
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
  profile of its call site and the inputs its call site passes; the renderer MUST
  NOT read the case or its ledger.
- MUST NOT: A CSAF projection MUST NOT contain a value that its profile redacts
  or omits.
- MUST: The draft step of the publication pipeline MUST use the public profile,
  and the operator CSAF endpoint MUST use the joined profile.
- MUST: Every profile MUST name one operation for every case field.
- MUST: A CSAF projection MUST be of category `csaf_base` and MUST pass the pinned
  CSAF 2.1 schema.
- MUST: `document.tracking.id` MUST be derived from the case ID, the versioned
  profile name, the log index of the preview's ledger position and, when the
  caller supplies acknowledgments, a digest of that input.
- MUST: `document.tracking.version` MUST be `1`, and the revision history MUST
  hold one entry numbered `1`.
- MUST: Every date in a CSAF projection MUST be the commit time of the ledger
  entry at the preview's position, so the same inputs give an identical document.
- MUST: A CSAF projection MUST carry a `document.references` entry that names the
  case ID and the entry hash of its ledger position.
- MUST: A CSAF projection MUST take its acknowledgments from its caller, or from
  the REPORTER participants when the caller supplies none, and MUST NOT derive
  them from other case data (ADR-0218).
- MUST: The involvement status of a projection MUST be `completed` for a ledger
  fact, and MUST NOT be `attempted` or `planned`.
- MUST: The TLP label of a projection MUST be `CLEAR` for the public profile and
  `AMBER+STRICT` for the joined profile.
- MUST NOT: The operator CSAF endpoint MUST NOT write to the DataLayer, add a
  ledger entry or send an activity.
