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
  - "#6788"   # epic: products and product statuses on the vendor's record
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

- **CSAF's full product name is the record format, held on the vendor's record.**
  A product is a CSAF full product name with its branch path below the vendor
  (`product_name`, `product_version`, `product_version_range` and the other branch
  categories) and its `product_identification_helper` (`cpe`, `purls` and the
  rest), in the structure of the pinned schema in `third_party/csaf/`
  (CSAF-05-002); Vultron adds only the object's id. The vendor branch is the
  record's own vendor, so the product does not repeat it.
- **Its own id, so statements meet on one object.** "X 2.1" stated by the vendor
  and "X v2.1" stated by a coordinator are one product once the CASE_MANAGER has
  admitted them as one; a status points at the product by id.
- **Offer it as vulnerability items are offered.** `Offer(Add(Product,
  target=<participant>))` and `Offer(Update(Product))`, answered with `Accept` or
  `Reject`, decided by a call-out point whose default asks; an admitted update
  merges helpers and does not shrink a list (CM-34-004 to CM-34-011). Reuse the
  vulnerability-item offer tree and its list merge rather than copying it
  (CS-22-001; `notes/vulnerability-items.md` § "The offers").
- **A combined product is a CSAF product path.** It names a beginning product, then
  an ordered list of (relationship category, next product) steps, using CSAF's five
  categories. Its parts may be other vendors' held products. It is held on the record of
  the beginning product's vendor. Its status says nothing about any part: CSAF
  declares a path when "a product is e.g. vulnerable only when installed together
  with another" (CSAF 2.1 prose, § Product Tree Property - Product Paths, at the
  pinned commit).

## The Product Status

- **One status per (author, product, vulnerability item), with a history.** The
  author's statuses for the pair are kept oldest first, the last current, as a
  participant's statuses are; another author's statuses do not replace them.
- **`attributed_to` is always set, the vendor's own included.** An empty author
  meaning "the vendor said it" would be a state stored as an absence, and the
  projection's vendor-only filter would read meaning into it.
- **The record format is CSAF's, adopted, not mirrored.** A product status is the
  per-product slice of a CSAF vulnerability entry, in CSAF's own structure, field
  names and values; Vultron adds only the author, the product and the
  vulnerability item it is about (ADR-0220). There is no Vultron record that CSAF
  values are copied into, so a CSAF document maps in and out with no translation
  table. Its parts:
  - `product_status`: the CSAF status lists this product is in, from the nine
    (`known_affected`, `known_not_affected`, `under_investigation`, `unknown`,
    `fixed`, `first_affected`, `last_affected`, `first_fixed`, `recommended`).
    One product may be in several lists, as in CSAF, but not in lists that
    contradict each other (CSAF mandatory test 6.1.6).
  - `remediations`: CSAF remediation objects (`category` such as `vendor_fix`,
    `fix_planned`, `no_fix_planned`, `none_available`, `workaround`, `mitigation`,
    `optional_patch`, with `details`, `url`, `date` and the other CSAF fields), less
    `product_ids` and `group_ids`, which the status's own product replaces.
  - `flags`: CSAF flag objects (`label` such as `vulnerable_code_not_present`), the
    justification of a `known_not_affected` product.
- **No Vultron-only enum beside them.** End of life is a `no_fix_planned`
  remediation whose `details` says so; a fixed version is a product of its own in
  `fixed`. Generate the types from the pinned schema's definitions
  (`vultron/wire/csaf/models/`) or import them, so a draft change is one regeneration
  (CSAF-05-002).
- **Declared, not offered.** `Add(ProductStatus, target=<participant>)` to the
  CASE_MANAGER, admitted whole or refused whole on checks alone, as a participant
  status is (RSH-09-001, RSH-09-002): the sender is an active participant (CM-10-004),
  or the CASE_MANAGER or Case Owner for a vendor that is not active; the target
  holds `VENDOR`; the product is held on that record; the vulnerability item is held
  by the case; the status lists do not contradict each other (CSAF test 6.1.6).
  The ledger entry and the replica copy follow
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
  CSAF document again and adds the products and the reporter's statuses for those
  names; the stored claims reading (`ReportClaims`) holds only
  `known_affected_vendors` today. No vendor name is matched to an invitee by
  spelling; the Case Owner states the link. At case creation the comparison is
  with the Case Owner's own `name`, the one CSAF-04-007 already makes. Reuse the
  reader's vendor-by-product map (`vultron/wire/csaf/reader.py`,
  `_vendors_by_product`), which today feeds only the candidate-parties signal
  (CSAF-04-007).
- **CSAF-02-002 changes with this code.** One of its clauses forbids changing case
  data from a CSAF document on a report that already belongs to a case. The general
  rule replacing that clause: an actor may read the original report again, CSAF or
  not, when its information becomes relevant. This is still the first report's
  statement, the one ADR-0184 admits, so the clauses on a document on another
  activity or of another category stay.

## Fix Readiness Reads Product Statuses

- **Fix readiness stays `vf`, `Vf` or `VF`.** `VF` means every planned fix is ready.
- **Affected means a CSAF affected list.** A product is affected for these checks
  when the vendor's own current status puts it in `known_affected`,
  `first_affected` or `last_affected`.
- **The agreement check runs at both ends.** The vendor's fix-readiness trigger and
  the CASE_MANAGER's received-status acceptance refuse `VF` when the vendor's own
  current statuses hold an affected product with neither a `vendor_fix` nor a
  `no_fix_planned` remediation. The CASE_MANAGER holds both records, so the check is
  local; extend the received-status refusal list (RSH-09-003) rather than adding a
  second path, and name the blocking products in the refusal notice (RSH-09-011).
- **The check runs only when `VF` is declared.** A status admitted after `VF` is
  not refused and does not move fix readiness back (ADR-0220).
- **No roll-up enum.** Partial readiness has no named values: each reader asks its
  own question of the vendor's statements in CSAF terms, where it decides. A
  summary for a person, such as the Case Owner weighing an early embargo end, is a
  tally of each vendor's own current statuses by CSAF status list and remediation
  category; compute it where read and do not store it.
- **The deployer gate also accepts a product-level fix.** CSB-15-004 lets a deployer
  move d→D when some vendor is at `VF`; it also passes when a vendor's own current
  status gives some affected product a `vendor_fix` remediation. Change the
  predicate (`vultron/core/predicates/participants.py`, `some_vendor_at_vf`), not
  the node that calls it.

### Which Reading Each Decision Point Uses

A decision point that reads fix readiness says which reading it uses. Only the
deployer gate changes in this plan; the rest record the reading for whoever next
changes them.

| Decision point | Reads | "Some fixes ready" counts as |
|---|---|---|
| Deployer d→D gate (CSB-15-004) | `VF`, or a vendor's own `vendor_fix` remediation | F |
| Vendor-and-deployer D guard (CSB-17-001; `vultron/core/behaviors/report/nodes/deploy_fix.py`) | its own `VF` | F for its fixed products; D per product is #5140 |
| No new embargo, reject a pending proposal (VP-14-007, CSB-10-001) | case at `VF` | f |
| Prepare to end an embargo (VP-14-008) | case at `VF` | f |
| Extensions for trailing vendors (VP-14-009, VP-14-014) | vendors not at `VF` | f: a partly fixed vendor is trailing |
| Fix-ready embargo end and its quorum (VP-09-007, EMB-13-010, EMB-13-013; `vultron/core/behaviors/embargo/nodes/chosen_cause.py`) | vendors at `VF` | policy: show the Case Owner each vendor's tally of statuses and remediations |
| Develop-fix short-circuit (`vultron/core/behaviors/report/nodes/develop_fix_conditions.py`) | own `VF` | f: work remains |
| Embargo ended on its own terms (`vultron/measure/standing/joint.py`) | every vendor `VF` | f |
| F≺P, F≺X, F≺A desiderata and event history (CEH-04-003) | the vendor's `VF` event | f: the full-F time |
| Action rules (`vultron/core/states/cs_actions.py`) | the CS position | f; a partial-fix pattern is future work |

## The Projection

- **Products and statuses get their own profile row.** Add them to the profile
  table of `notes/csaf-projection.md`, apart from the participant records they sit
  on: the public profile omits participants, but an advisory needs product status.
  Each profile substitutes a vendor record with its products and the statuses it
  shows, and every other field of the record stays as the profile already cuts it.
- **Whose statements, chosen by the profile.** A profile shows the vendor's and the
  projecting actor's own statuses only, or every author's; the call site fixes
  which, as it fixes the TLP.
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

- MUST: A product MUST be held on the participant record of its vendor.
- MUST: A participant record that holds a product MUST belong to a participant that
  holds the VENDOR role.
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
- MUST: A product and a product status MUST use the CSAF 2.1 record format for
  their content: a product is a CSAF full product name, and a product status holds
  CSAF product status lists, remediations and flags, with CSAF's field names and
  values.
- MUST_NOT: A product status MUST NOT put its product in CSAF status lists that
  contradict each other.
- MUST_NOT: The case MUST NOT hold a product or product status of a vendor that is
  not a participant.
- MAY: An actor MAY read a case's original report again when its information
  becomes relevant, and take the sender's statements in it as that sender's
  (replaces CSAF-02-002's clause on a report that already belongs to a case).
- MUST_NOT: A vendor participant MUST NOT declare `VF` while its own current product
  statuses hold an affected product with neither a `vendor_fix` nor a
  `no_fix_planned` remediation.
- MUST: The CASE_MANAGER MUST refuse a received `VF` while the vendor's own current
  product statuses hold an affected product with neither a `vendor_fix` nor a
  `no_fix_planned` remediation.
- MUST_NOT: The CASE_MANAGER MUST NOT refuse a product status because its vendor is
  at `VF`.
- MUST: A deployer that does not hold the VENDOR role MUST be permitted d→D when a
  vendor is at `VF` or a vendor's own current product status gives an affected
  product a `vendor_fix` remediation (extends CSB-15-004).
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
- **A third fix-readiness value, or a named roll-up.** Rejected in ADR-0220;
  partial readiness is each reader's own question over the CSAF statuses.
