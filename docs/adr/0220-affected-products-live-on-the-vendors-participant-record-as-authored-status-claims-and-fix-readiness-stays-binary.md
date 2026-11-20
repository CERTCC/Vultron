---
status: proposed
date: 2026-11-20
created: 2026-11-20
updated: 2026-11-20
revision: 1
deciders: Allen D. Householder
consulted: Vultron maintainers
informed: Vultron implementers
stakeholder_type: [project-contributor]
---

# Affected Products Live on the Vendor's Participant Record as Authored Status Claims, and Fix Readiness Stays Binary

## Context and Problem Statement

A case holds its vulnerabilities as items, and an item holds none of the per-vulnerability state of a CSAF vulnerability entry, such as product status or remediations ([ADR-0187](0187-a-cases-vulnerabilities-are-csaf-shaped-items-that-participants-offer-and-the-case-manager-admits.md)).
So the case holds no products, and a CSAF projection of the case can only be a CSAF Base document ([ADR-0219](0219-a-csaf-projection-is-a-case-preview-cut-by-its-call-sites-profile-then-rendered-to-csaf.md)).
The Vulnerability Report and Security Advisory profiles of CSAF both need a product tree and a status for each product.

Most statements about which products a vulnerability affects come from the products' vendor.
Other parties also make them.
A report can name affected products, as a CSAF Vulnerability Report does.
A coordinator can state that a vendor's product is affected before the vendor answers.
A vendor can state that its own product is affected because it bundles another vendor's product.
The Case Owner can state that a vendor's product is affected when nobody has reached that vendor.

Each vendor participant also declares one fix readiness for the whole case: no fix ready, or fix ready (F).
A vendor with several affected products can have a fix ready for some and not for others.

**Where does the case hold affected products and their status, who may state them, and how does product-level fix status relate to a vendor's fix readiness?**

## Decision Drivers

- The vendor is the usual source of statements about its products, so its participant record is the natural home for them.
- Statements by other parties are real coordination information, and a vendor may disagree with them; neither should erase the other.
- Every stored state should be named and should match what its author sent.
- The six-event case-state model, the event history derived from the ledger, and the action rules all read fix readiness as two values.
- Readers of fix readiness ask two different questions: whether someone can act on a fix that exists, and whether a vendor is done.
- A CSAF document must give each product one status per vulnerability, and it is its publisher's statement.

## Considered Options

For where statements live:

- Only the vendor states the status of its products.
- An admitted statement becomes the product's status, whoever made it.
- Each statement keeps its author and sits beside the others on the vendor's participant record.

For partial fix readiness:

- Add a third fix-readiness value, "some fixes ready", to the vendor's state.
- Keep fix readiness binary, meaning any fix ready.
- Keep fix readiness binary, meaning every planned fix ready, and derive partial readiness from product statements.

## Decision Outcome

Chosen options: "each statement keeps its author and sits beside the others on the vendor's participant record", and "keep fix readiness binary, meaning every planned fix ready, and derive partial readiness from product statements".
The first is the only option that keeps both a vendor's word and a third party's word.
The second is the only option that answers both reader questions without changing the case-state model.

The decision has seven parts.

1. **A product is a shared object held on its vendor's participant record.**
   A product has the shape of a CSAF full product name: a name, its place in the vendor's product hierarchy, and identification helpers such as CPE and PURL values.
   It has an identity of its own, so statements by different authors about the same product name the same object.
   A participant offers a new product or an update of a held one, and the CASE_MANAGER admits or declines the offer, as for vulnerability items (ADR-0187).
   An admitted update merges identification helpers and does not shrink a list.
2. **A product status is an authored statement about one product and one vulnerability item.**
   Every product status records its author, the vendor's own included.
   An active participant declares a product status, and the CASE_MANAGER admits it when the sender, its target and its values pass the protocol's checks; no one decides whether it is true.
   Statements by different authors about the same product and vulnerability sit side by side, and none replaces another.
   An author's later statement about the same pair supersedes its own earlier one, which stays in its history.
   The CASE_MANAGER or the Case Owner may state product statuses on the record of a vendor that is on the case but is not an active participant.
3. **A product status has two named dimensions.**
   Affectedness is one of unknown, under investigation, affected, not affected with a justification, or fixed (this product contains the fix).
   For an affected product, the fix plan is one of none available, fix planned, fix available with the fixed product it points at, or no fix planned with a reason, such as the product's end of life.
   A version that contains a fix is a product of its own, so an affected version does not become fixed.
4. **A combined product is a configuration, not a dependency claim.**
   A product may be a combination of held products, including another vendor's, joined by the relationship categories of a CSAF product path, such as "installed on" or "default component of".
   A status of the combination says nothing about any of its parts, as in CSAF, where a product path is declared when a product is vulnerable only when installed together with another.
   A combination is held on the record of the vendor of the product that begins its path.
   This implementation reads a combined product this way; another may infer a claim about a component.
5. **A statement waits for its vendor's record.**
   The case holds no product statement about a vendor that is not a participant.
   The statements in a case's original report stay in the report, and an actor may read them again when they become relevant.
   When the case is created and its Case Owner holds the VENDOR role, the report's statements about the products it lists under the Case Owner's own name join the Case Owner's record, authored by the reporter.
   When the Case Owner invites an actor, it may say which vendor names in the original report that actor is, and the report's statements about those names then join the new participant's record, authored by the reporter.
   This reads only the first report's statement, the one occasion when a CSAF document speaks for its sender ([ADR-0184](0184-a-csaf-document-travels-as-a-report-attachment-and-speaks-for-the-sender-only-at-the-first-report.md)), and no vendor name is matched to an invitee by its spelling alone.
6. **Fix readiness stays binary and means every planned fix is ready.**
   A vendor declares fix ready only when every product it states as affected has a fix available or no fix planned, and the CASE_MANAGER refuses a declaration that disagrees with the vendor's own statements.
   A vendor that states no product status declares fix readiness as before.
   Partial readiness is a reading derived from the vendor's own statements, not a stored state, with named values for no statements, no product affected, no fix ready, some fixes ready, every planned fix ready, and no fix planned for any product.
   A statement made after the vendor reached fix ready is admitted, the vendor's fix readiness does not move back, and the derived reading shows partial readiness again.
   Each reader that needs to decide whether "some fixes ready" is enough chooses its reading where it decides.
   A reader asking whether someone can act on an existing fix counts a vendor's own fix-available statement for that product, and a reader asking whether a vendor is done counts only every planned fix.
7. **A projection gives each product one status.**
   The profile of the call site chooses whether the projection shows only the vendor's and the projecting actor's own statements, or the statements of every author.
   Where several statements are shown, the status of a product takes the vendor's own statement, else the projecting actor's own, else the most recent one.
   Every shown statement that does not give the status is rendered as a note that names its author, so a disagreement stays visible.

Deployment status per product and deployer is not decided here, and neither is splitting a case when a new affected product appears after its vendor reached fix ready.

### Consequences

- Good, because a CSAF projection can have a product tree and product status, so it can meet the Vulnerability Report and Security Advisory profiles.
- Good, because a vendor's word and a third party's word both stay on the record, and a disagreement between them is visible.
- Good, because a vendor that never engages can still have its products described by the parties that know them.
- Good, because the case-state model, the event history and the action rules keep their two-valued fix readiness.
- Good, because "some fixes ready" stays visible to readers such as the Case Owner deciding whether to end an embargo early.
- Bad, because a vendor can state "some fixes ready" only by naming its products.
- Bad, because a vendor at fix ready can again have an affected product with no fix, and only the derived reading shows it.
- Bad, because each reader of fix readiness must say which reading it uses.
- Neutral, because every admitted product and statement is a ledger entry like any other case-file change.

## Pros and Cons of the Options

### Only the vendor states the status of its products

- Good, because it matches fix readiness, which only the vendor may declare.
- Bad, because a coordinator's or a reporter's knowledge of affected products has no place in the case.
- Bad, because a vendor that never engages has no product status at all.

### An admitted statement becomes the product's status, whoever made it

- Good, because it reuses the vulnerability-item flow unchanged.
- Bad, because a later statement by one party overwrites an earlier one by another, and the vendor's own word can be lost.
- Bad, because the CASE_MANAGER would have to decide which party is right.

### Each statement keeps its author and sits beside the others on the vendor's participant record

- Good, because nothing is overwritten and every statement says who made it.
- Good, because a projection can choose whose statements to show.
- Bad, because a reader can face several statements about one product and must choose among them.

### Add a third fix-readiness value, "some fixes ready", to the vendor's state

- Good, because a vendor can say "some fixes ready" without naming products.
- Bad, because the case-state model, its valid histories, the event history and the action rules all assume two values.

### Keep fix readiness binary, meaning any fix ready

- Good, because a deployer can act as soon as one fix exists.
- Bad, because the rules on starting embargoes, ending them and extending them for trailing vendors read fix readiness as "the vendor is done", and would need another source.

### Keep fix readiness binary, meaning every planned fix ready, and derive partial readiness from product statements

- Good, because the stored state keeps its two values and its meaning for the rules that read it.
- Good, because partial readiness is still readable wherever it matters.
- Bad, because a reader that can act on one fix needs a product-level check as well as fix readiness.

## More Information

The build plan, the table of decision points that read fix readiness, and the requirement text the implementation adds are in `notes/affected-products.md`.
Requirements land with the code that tests them.
Concern [#5140](https://github.com/CERTCC/Vultron/issues/5140) still tracks deployment per product and deployer.
