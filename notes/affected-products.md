---
title: "Affected Products and Product Status: Implementation Plan"
status: draft
kind: plan
tracks:
  - "#6780"   # products on the vendor's record
  - "#6781"   # authored product statuses
  - "#6782"   # fix readiness agrees with product statuses
  - "#6783"   # report statements reach vendors' records
  - "#6785"   # CSAF projection renders products
  - "#6234"   # epic: vulnerability items and references
  - "#5413"   # epic: fix states per role
  - "#5130"   # epic: Vultron cases and CSAF 2.1
description: >
  How this codebase gives a vendor's participant record its products and the
  authored product statuses that participants state about them (ADR-0220): the
  product object and its offer flow, the two-dimension product status, statements
  from the original report, how fix readiness reads product statuses, and what the
  CSAF projection renders. Holds the table of decision points that read fix
  readiness and the requirement text the implementation adds.
related_specs:
  - specs/case-management.yaml
  - specs/csaf-report-content.yaml
  - specs/cs-behavior.yaml
  - specs/received-status-handling.yaml
  - specs/participant-role-management.yaml
  - specs/em-behavior.yaml
  - specs/vultron-protocol-spec.yaml
related_notes:
  - notes/vulnerability-items.md
  - notes/csaf-projection.md
  - notes/csaf-case-inputs-on-proposal.md
relevant_packages:
  - vultron.core.models
  - vultron.core.behaviors
  - vultron.core.use_cases
  - vultron.wire.as2
  - vultron.wire.csaf
---

# Affected Products and Product Status: Implementation Plan

A vendor's participant record holds its products, and every participant's
statements about them, as authored product statuses (ADR-0220). Nothing here is
built yet.

## Order

- **Product first, statuses second, the rest after.** A status names a product
  and a vulnerability item, so it needs both to exist. The report backfill, the
  fix-readiness check and the projection each read statuses, and they can be built
  in parallel once statuses land.
- **The projection waits for the CSAF Base renderer** (#6705). It adds the product
  tree and product status to a renderer that exists, and the category choice is
  made only where a preview meets a category's requirements.

## The Product

- **CSAF's full product name, held on the vendor's record.** A name, its branch
  path below the vendor (`product_name`, `product_version`, `product_version_range`
  and the other branch categories) and the identification helpers (`cpe`, `purls`
  and the rest of `product_identification_helper`), copied field by field from the
  pinned schema in `third_party/csaf/` (CSAF-05-002). The vendor branch is the
  record's own vendor, so the product does not repeat it.
- **Its own id, so statements meet on one object.** "X 2.1" stated by the vendor
  and "X v2.1" stated by a coordinator are one product once the CASE_MANAGER has
  admitted them as one; a status points at the product by id.
- **Offer it as vulnerability items are offered.** `Offer(Add(Product,
  target=<participant>))` and `Offer(Update(Product))`, answered with `Accept` or
  `Reject`, decided by a call-out point whose default asks; an admitted update
  merges helpers and never shrinks a list (CM-34-004 to CM-34-011). Reuse the
  vulnerability-item offer tree and its list merge rather than copying it
  (CS-22-001; `notes/vulnerability-items.md` § "The offers").
- **A combined product is a CSAF product path.** It names a beginning product, then
  an ordered list of (relationship category, next product) steps, using CSAF's five
  categories. Its parts may be other vendors' products. It is held on the record of
  the beginning product's vendor. Its status says nothing about any part: CSAF
  declares a path when "a product is e.g. vulnerable only when installed together
  with another" (CSAF 2.1 prose, § Product Tree Property - Product Paths, at the
  pinned commit).

## The Product Status

- **One status per (author, product, vulnerability item), with a history.** The
  author's statuses for the pair are kept oldest first, the last current, as a
  participant's statuses are; another author's statuses never replace them.
- **`attributed_to` is always set, the vendor's own included.** An empty author
  meaning "the vendor said it" would be a state stored as an absence, and the
  projection's vendor-only filter would read meaning into it.
- **Two dimensions, each a named enum.**

  | Dimension | Values | CSAF |
  |---|---|---|
  | Affectedness | `UNKNOWN`, `UNDER_INVESTIGATION`, `AFFECTED`, `NOT_AFFECTED` (+ justification), `FIXED` | the matching `product_status` list; the justification is a `flags[].label` |
  | Fix plan (only when `AFFECTED`) | `NONE_AVAILABLE`, `FIX_PLANNED`, `FIX_AVAILABLE` (+ the fixed product), `NO_FIX_PLANNED` (+ reason `END_OF_LIFE` or `OTHER`, and text) | `remediations[]` of category `none_available`, `fix_planned`, `vendor_fix`, `no_fix_planned` |

  `first_affected`, `last_affected`, `first_fixed` and `recommended` mark version
  ranges and the version to pick; the renderer derives them, they are not states.
  `workaround` and `mitigation` remediations are additions to a status, not
  fix-plan values. CSAF has no end-of-life value: the renderer writes the reason
  into the `no_fix_planned` remediation's `details`.
- **Declared, not offered.** `Add(ProductStatus, target=<participant>)` to the
  CASE_MANAGER, admitted whole or refused whole on checks alone, as a participant
  status is (RSH-09-001, RSH-09-002): the sender is an active participant (CM-10-004),
  or the CASE_MANAGER or Case Owner for a vendor that is not active; the target
  holds `VENDOR`; the product is held on that record; the vulnerability item is held
  by the case; a fix plan appears only with `AFFECTED`; a `FIX_AVAILABLE` names a
  held product of the same vendor. The ledger entry and the replica copy follow
  `notes/case-ledger-authority.md`.
- **No truth check.** The CASE_MANAGER does not judge whether a status is right; a
  disagreement is two statuses, both kept.

## Statements From the Original Report

- **At case creation, the reporter's statements about the Case Owner's products.**
  When the case comes from a report with a CSAF document and the Case Owner holds
  `VENDOR`, the products the document names under a vendor branch equal to the Case
  Owner's `name` become products on its record, and each `product_status` entry
  becomes a status authored by the reporter. Build it into the case inputs the
  receiver converts (`notes/csaf-case-inputs-on-proposal.md`), beside the
  vulnerability items of CSAF-03-008.
- **At invitation, the reporter's statements about the invitee.** The Case Owner's
  invite may name the CSAF vendor names the invitee is. When the stub Invite creates
  the invitee's record (CM-11-006), the CASE_MANAGER reads the original report's
  stored CSAF record and adds the products and the reporter's statuses for those
  names. No vendor name is matched to an actor by spelling; the Case Owner states
  the link. Reuse the reader's vendor-by-product map
  (`vultron/wire/csaf/reader.py`, `_vendors_by_product`), which today feeds only the
  candidate-parties signal (CSAF-04-007).
- **CSAF-02-002 changes with this code.** It forbids changing case data from a CSAF
  document on a report that already belongs to a case. The general rule replacing
  it: an actor may read the original report again, CSAF or not, when its
  information becomes relevant. This is still the first report's statement, the
  one ADR-0184 admits.

## Fix Readiness Reads Product Statuses

- **Fix readiness stays `vf`, `Vf` or `VF`.** `VF` means every planned fix is ready.
- **The agreement check runs at both ends.** The vendor's fix-readiness trigger and
  the CASE_MANAGER's received-status acceptance refuse `VF` when the vendor's own
  current statuses hold an `AFFECTED` product whose fix plan is neither
  `FIX_AVAILABLE` nor `NO_FIX_PLANNED`. The CASE_MANAGER holds both records, so the
  check is local; extend the received-status refusal list (RSH-09-003) rather than
  adding a second path, and name the blocking products in the refusal notice
  (RSH-09-011).
- **The check runs only when `VF` is declared.** A status admitted after `VF` is
  not refused and does not move fix readiness back (ADR-0220).
- **Fix coverage is a derived read.** Over a vendor's own current statuses:
  `UNSTATED` (none), `NOT_AFFECTED` (no product `AFFECTED`, none unknown or under
  investigation), `NONE_READY`, `PARTIAL`, `COMPLETE` (every planned fix available,
  at least one) and `NO_FIX` (every affected product `NO_FIX_PLANNED`). Compute it
  where read; never store it. A case-level read lists each vendor's coverage.
- **The deployer gate also accepts a product-level fix.** CSB-15-004 lets a deployer
  move d→D when some vendor is at `VF`; it also passes when a vendor's own current
  status is `FIX_AVAILABLE` for some product. Change the predicate
  (`vultron/core/predicates/participants.py`, `some_vendor_at_vf`), not the node
  that calls it.

### Which Reading Each Decision Point Uses

A decision point that reads fix readiness says which reading it uses. Only the
deployer gate changes in this plan; the rest record the reading for whoever next
changes them.

| Decision point | Reads | "Some fixes ready" counts as |
|---|---|---|
| Deployer d→D gate (CSB-15-004) | `VF`, or a vendor's own `FIX_AVAILABLE` | F |
| Vendor-and-deployer D guard (CSB-17-001; `vultron/core/behaviors/report/nodes/deploy_fix.py`) | its own `VF` | F for its fixed products; D per product is #5140 |
| No new embargo, reject a pending proposal (VP-14-007, CSB-10-001) | case at `VF` | f |
| Prepare to end an embargo (VP-14-008) | case at `VF` | f |
| Extensions for trailing vendors (VP-14-009, VP-14-014) | vendors not at `VF` | f: a partly fixed vendor is trailing |
| Fix-ready embargo end and its quorum (EMB-13-010, EMB-13-013; `vultron/core/behaviors/embargo/nodes/chosen_cause.py`) | vendors at `VF` | policy: list `PARTIAL` vendors apart for the Case Owner |
| Develop-fix short-circuit (`vultron/core/behaviors/report/nodes/develop_fix_conditions.py`) | own `VF` | f: work remains |
| Embargo ended on its own terms (`vultron/measure/standing/joint.py`) | every vendor `VF` | f |
| F≺P, F≺X, F≺A desiderata and event history (CEH-04-003) | the vendor's `VF` event | f: the full-F time |
| Action rules (`vultron/core/states/cs_actions.py`) | the CS position | f; a `PARTIAL` pattern is future work |

## The Projection

- **Products and statuses get their own profile row.** Add them to the profile
  table of `notes/csaf-projection.md`, apart from the participant records they sit
  on: the public profile omits participants, but an advisory needs product status.
  Each profile substitutes a vendor record with its products and the statuses it
  shows, and every other field of the record stays as the profile already cuts it.
- **Whose statements, chosen by the profile.** A profile shows the vendor's own
  statuses only, or every author's; the call site fixes which, as it fixes the TLP.
  The public profile shows only the vendor's and the projecting actor's own
  statuses, so it names no other participant, which keeps it within ADR-0218's
  no-public-credit rule; the joined profile shows every author's.
- **One status per product per vulnerability.** The status comes from the vendor's
  own statement, else the projecting actor's, else the most recent shown one. Every
  other shown statement becomes a `vulnerabilities[].notes` entry naming its author
  and its status, so CSAF test 6.1.6 (contradicting product status) still passes.
- **Product tree from the products.** One `vendor` branch per vendor record, its
  products below by their branch paths; combined products as `product_paths`.
- **Category by what the preview meets.** A call site renders
  `csaf_security_advisory` or `csaf_vulnerability_report` when the preview meets that
  profile's requirements, and `csaf_base` otherwise. The Vulnerability Report rule
  of ADR-0218 for acknowledgments applies once that category is rendered.

## Requirement Text the Implementation Adds

Each lands with the code that tests it, citing ADR-0220.

- MUST: A product MUST be held on the participant record of its vendor, and that
  record's participant MUST hold the VENDOR role.
- MUST: A participant that proposes a new product, or a change to a held product,
  MUST send the CASE_MANAGER an `Offer` of the `Add` or `Update` of that product.
- MUST: Every product status MUST name its author, its product and its
  vulnerability item.
- MUST_NOT: An admitted product status MUST NOT replace or change a product status
  by another author.
- MUST: The CASE_MANAGER MUST admit a product status from an active participant, or
  from the CASE_MANAGER or Case Owner for a vendor that is not active, when its
  target, product, vulnerability item and values pass the checks, and refuse it
  whole otherwise.
- MUST_NOT: A product status MUST NOT carry a fix plan unless its affectedness is
  `AFFECTED`.
- MUST_NOT: The case MUST NOT hold a product or product status of a vendor that is
  not a participant.
- MAY: An actor MAY read a case's original report again when its information
  becomes relevant, and take the sender's statements in it as that sender's
  (replaces CSAF-02-002).
- MUST: A vendor participant MUST NOT declare `VF`, and the CASE_MANAGER MUST refuse
  a received `VF`, while the vendor's own current product statuses hold an
  affected product whose fix plan is neither fix available nor no fix planned.
- MUST_NOT: The CASE_MANAGER MUST NOT refuse a product status because its vendor is
  at `VF`.
- MUST: A deployer that does not hold the VENDOR role MUST be permitted d→D when a
  vendor is at `VF` or a vendor's own current product status states a fix available
  (extends CSB-15-004).
- MUST: A CSAF projection MUST give a product one status per vulnerability, from
  the vendor's own statement, else the projecting actor's, else the most recent
  shown, and render every other shown statement as a note naming its author.

## Not in This Plan

- **Deployment per product and deployer.** D stays per participant; #5140 tracks
  the finer unit.
- **Splitting a case when a new affected product appears after `VF`.** Tracked as
  its own Idea (#6786).
- **Removing a product or withdrawing a status.** No message does either yet; an
  author supersedes its own status with a later one.
- **A third fix-readiness value.** Rejected in ADR-0220; partial readiness is the
  derived fix coverage read.
