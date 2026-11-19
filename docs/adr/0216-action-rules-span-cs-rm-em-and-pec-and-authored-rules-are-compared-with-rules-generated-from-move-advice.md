---
status: proposed
date: 2026-11-18
created: 2026-11-18
updated: 2026-11-19
revision: 2
deciders: Allen D. Householder
consulted: Claude Opus 5.5; Epic #6668 (analyst feedback on the case shadow tool); ADR-0060; ADR-0190; ADR-0200; #6492
informed: Vultron implementers
stakeholder_type: [project-contributor]
---

# Action Rules Span CS, RM, EM and PEC, and Authored Rules Are Compared With Rules Generated From Move Advice

## Context and Problem Statement

The CVD action rules in `CS_ACTION_RULES` (`vultron/core/states/cs_actions.py`, ADR-0060) name the actions that a compound case state makes possible.
Each rule reads only the six case-state events.
Thus a rule cannot say that an embargo extension suits an active embargo, or that a fix deployment suits a vendor whose report is accepted.
The code keeps no role and no reason for a rule.
The table that the rules come from (`docs/topics/other_uses/action_rules.md`) gives each rule a role and a reason, but each reason is a tag, such as "Exit criteria met" or "SA", and no tag names a desideratum.
Thus an analyst cannot see what a rule is for, and nothing can check whether the rule serves it.
The table and the code have drifted apart: the table splits or merges some rules, two of its patterns are typos, and some rules of the code have no row.
The rules also predate the RM, EM and PEC state machines, so a rule whose action belongs to one of those machines, such as negotiating an embargo, does not say in which of its states the action exists.

The case shadow tool already has a second source of advice: move advice puts each open move in a band by its outcome shift for each vendor (ADR-0200).
Move advice states nothing as a rule, and it has known blind spots: for example, the chance model cannot see that an active embargo protects the end desiderata (#6492).
A rule that a person writes can be wrong too.

The question: **what do the action rules read, what does each one claim, and how do the rules relate to move advice, so that the analyst sees both a person's judgment and the model's evidence, and sees where they disagree?**

## Decision Drivers

- A rule says why: it has a reason, and where that reason is a desideratum it names it from the desiderata list that move advice uses.
- A rule can read every state machine of a participant's position: CS, RM, EM and PEC.
- A rule and move advice read the same positions, so that each can check the other.
- Neither a rule nor the chance model is ground truth.
  A disagreement marks a wrong rule or a blind spot in the model, and only a person can say which.
- A disagreement is shown.
  Nothing resolves it silently.
- An action rule is advice.
  It fires no trigger and moves no state, so it is read for one vendor at a time, as move advice is.
- An action rule suggests an action and never forbids one.
  A person can always take an action that no rule names, or one that a rule shows to be costly.
- The CS action rules stay equal to the legacy test oracle (ADR-0060).
- The demo stories already compare an authored narrative with "the story as the code tells it".
  The action rules use the same pattern: the claim beside the evidence.

## Considered Options

- Authored rules only
- Generated rules only
- Both, with the generated rule replacing the authored rule where they disagree
- Both, compared, with each rule disagreement shown

## Decision Outcome

Chosen option: "Both, compared, with each rule disagreement shown", because it is the only option that keeps a person's judgment and the model's evidence side by side, so that each one can find the other's errors.

1. **An action rule reads one vendor's position.**
   The position is the vendor's RM state, the vendor's compound CS state, the case's EM state, and the vendor's PEC state for the embargo in force and for an open proposal.
   Each part of a rule's pattern names a set of states, or matches any state.
   The CS part keeps the six-position `vfdpxa` pattern of `CS_ACTION_RULES`.
   A rule names the CVD roles that may take the action, such as the vendor itself or a coordinator, or it names any role, which constrains no role.
   A rule for another role matches once for each vendor whose position matches it, and names that vendor.
   When several proposals are open, a rule whose PEC part reads a proposal matches once for each proposal, and names it.
   A rule is advice about one vendor, as each scope of move advice is (ADR-0200 rule 1).
   It fires no trigger, so it does not aggregate over the vendors, and it sets no threshold over them.
   A case-level trigger or behavior-tree node that acts on such advice still aggregates over the participants.
2. **A part that the reading does not hold is unknown, not false.**
   When a case reading holds no state for a part of the position, such as a reading that records no embargo consent, a rule that constrains that part is undecided at that position.
   It is shown as undecided, never as matched or unmatched (CRD-02-005).
3. **An action rule names an action, its reason, and the desiderata that its reason is.**
   The action is a move or a CVD action that changes no state.
   A move is named as move advice names it, by its machine and its trigger.
   A CVD action that changes no state, such as monitoring for attacks, is named by its member of `Actions`, and so is an action that is a move at some positions only, such as a publication.
   Every rule has a reason.
   A reason need not be a desideratum: situation awareness, detection, defense and housekeeping are reasons, and they order no events.
   Where the reason is a desideratum, the rule names it from the desiderata list that move advice uses; otherwise the rule names no desideratum.
   A rule that names desiderata and whose action is a move claims that the move serves the vendor that the rule matches.
   A rule that names no desideratum claims nothing a band could check, so the comparison shows it with its reason and no number.
   An action that causes a CS event causes it only the first time.
   A publication is any publication, such as an advisory, exploit details, a detection or a mitigation, and it is always a valid action.
   The first publication causes P, and a later one is still a valid action that changes no state, because P happens only once.
   The same holds for X and for A.
   So at a position where the action's event has already happened, the action is a CVD action that changes no state, not a misplaced rule.
   The public's awareness is not a publication: a public exploit makes the public aware that the vul exists, which the CS model forces as P, but no participant has published information that defenders can use.
   So at a position where a public exploit forces P next, a publication does not cause P, and it is not joined to that move.
   A rule suggests and never forbids: a move that no rule names stays open in move advice, and a rule that names a costly move, such as publishing before the vendor is aware, is kept and shown with its cost.
4. **Authored action rules are the claim.**
   A person writes them in one authored table.
   Each authored rule holds one pattern and one action.
   Each pattern and action of `CS_ACTION_RULES` carries over as one or more authored rules, and each carried-over rule records the pattern and action that it came from.
   A person sets each carried-over rule's roles, reason and desiderata, which replace the source table's role and tag.
   A person may narrow a carried-over rule, never widen it: the rule then matches only positions that its source pattern matches.
   The carried-over rules predate the RM, EM and PEC machines, so a rule is narrowed with RM, EM or PEC parts where those states change what the rule is.
   For example, negotiating an embargo at `..dpxa` becomes a proposal at EM NONE, and at EM PROPOSED an acceptance by the case owner or a participant's answer to the proposal.
   A rule whose action is an EM move is narrowed to the EM states from which that move exists.
   A source rule whose action belongs to several roles or several moves becomes one authored rule for each, with the same source.
   Closing the case is the RM move `rm.close`, suggested to each participant whose RM state is not Closed.
   Initiating the US government's Vulnerabilities Equities Process is not a move of the protocol, so its rule does not carry over.
   A wrong source pair is changed in `CS_ACTION_RULES` and its legacy oracle (ADR-0060), not in the authored table.
   One mapping gives the move name for each `Actions` member that changes state, so that the carried-over rules name moves as rule 3 says.
   `CS_ACTION_RULES` stays as it is, and `test_cs_actions.py` still holds it equal to the legacy oracle.
5. **Generated action rules are the evidence.**
   Generated rules are read off move advice.
   A move's **band for one vendor** is ADR-0200 rule 5 applied to that vendor's scope alone: the deciding part is the vendor's end part, or its embargo part when the end part is zero, and the move is harm-free for the vendor when that part is positive and unhelpful for the vendor when it is not.
   It can differ from the move's band in the whole case, because the rule is about one vendor.
   For each open move and each valid position of one vendor, the generated verdict is the move's band for that vendor.
   Move advice reads a position's history as well as its states: a desideratum that is already met or broken changes by nothing, so two histories that leave different desiderata open can give one move two bands at one position.
   For example, at RM Deferred, `Vfdpxa` and EM NONE, accepting the report is harm-free when the report was never accepted, and unhelpful when it was accepted before it was deferred.
   A generated rule groups the positions in which a move gets the same band, whatever desiderata are still open, into one or more patterns, written in the same pattern language as the authored rules, with the role that move advice gives the move.
   At a position where the band depends on the history, the generated rules state a conditional verdict: each band, with the desiderata whose being open gives it.
   They neither pick one history nor leave the position blank.
   A verdict on an event that the position forces next, such as P beside a public exploit, is marked as forced.
   That role is the vendor for an RM or CS move, which names the vendor whose state it moves, and, for an EM move, the role that the EM trigger roles table gives its trigger, or any role when the table names none.
   One command rebuilds the generated rules, and nobody edits them by hand.
   A check fails when the move advice changes and the generated rules were not rebuilt.
   A move that move advice does not score, such as a PEC move while move advice has no PEC moves (#6677), has no generated rule.
6. **The comparison is made position by position, not pattern by pattern.**
   An authored rule joins the advice on the move name and on the participant: for an RM or CS move, the matched vendor whose state the move changes; for an EM move, the participant in the rule's role that move advice lists as able to make it.
   For each position, each authored rule that matches it, and each generated verdict at it, the comparison gives one of five results:
   - An **agreement**: an authored rule claims that a move serves the vendor, and the move is harm-free for that vendor.
   - A **rule disagreement**: an authored rule claims that a move serves the vendor, and the move is unhelpful for that vendor.
   - A **misplaced rule**: an authored rule names a move that the state machines do not allow at a position that the rule matches, or a move that the rule's role may not make.
     It is an authoring error.
   - An **unclaimed move**: a move is harm-free for the vendor, and no authored rule names it at that position.
   - An **unscored rule**: an authored rule whose action is allowed but has no band, such as a CVD action that changes no state, or a move that move advice does not score, or an authored rule that names no desideratum.

   An unhelpful move that no authored rule names gives no result.
   Each agreement and each rule disagreement shows the deciding part of the vendor's shift, and the change in each desideratum that the rule names, so that the analyst sees whether the move's band rests on the desiderata the rule claims.
   A rule disagreement, a misplaced rule and an unclaimed move are shown, not resolved.
   The comparison edits neither table.
   A person who judges a rule wrong changes the rule.
   A person who judges a disagreement a blind spot of the chance model cites, on the authored rule, the issue that tracks the blind spot, and the disagreement stays shown, with that citation.
   An unscored rule is shown as advice with no number, never as an agreement.
7. **On a live case, the comparison reads the case's own advice.**
   For the point in the case that the analyst looks at, the case shadow tool shows the authored rules that match each vendor's position, beside the bands.
   It compares each rule with the move's band for the matched vendor, read from the case's own outcome shifts.
   Thus a trade-off move shows as an agreement for a vendor that it helps and as a rule disagreement for a vendor that it harms.
8. **The generated rules and the disagreements have a docs page.**
   A generated page in the measuring-CVD docs lists the generated rules and the result of the comparison over every valid position of one vendor.
   The positions on the page hold no PEC state, because the chance model has none, so an authored rule with a PEC part is undecided there (rule 2).
   The command that rebuilds the generated rules rebuilds the page too, and the same staleness check covers it.
   The table in `docs/topics/other_uses/action_rules.md` is generated from the carried-over authored rules by the same command, with each rule's pattern, roles, action and desiderata, so that the two tables do not disagree.
9. **The action rules endpoint does not change.**
   The endpoint of AR-07 and CM-07 still reads the legacy module (ADR-0060).
   Whether it reads the authored table is a later decision.

### Consequences

- Good, because each rule says which desiderata it serves, so the analyst sees what the rule is for.
- Good, because a rule can read RM, EM and PEC, so it can say when a move suits a position and not only a case state.
- Good, because a rule disagreement finds either a wrong rule or a blind spot in the chance model.
  For example, an authored rule that a coordinator proposes an extension to buy time for `D ≺ P` disagrees with move advice, which puts the extension in the unhelpful band (#6492).
- Good, because a misplaced rule finds an authoring error that a list of possible actions hides.
- Good, because the generated rules state move advice in the language of the rules, so that a person can read and review it, rule by rule.
- Good, because the comparison resolves nothing, so neither the model nor a person overrides the other in silence.
- Good, because a rule is about one vendor, so no rule chooses a threshold over the vendors.
- Good, because a carried-over rule can be narrowed with RM, EM and PEC parts, so a person can correct a rule without losing the legacy oracle that checks its source.
- Bad, because a rule cannot read the state of a participant that is not a vendor, such as a coordinator's own RM state.
  Such rules wait for scopes for those participants (Epic #6461).
- Bad, because the verdict is a band from all the desiderata of the vendor's scope, not from the desiderata that the authored rule names.
  An authored rule that names an end desideratum agrees with a move whose band comes from its embargo part only.
  The comparison shows the deciding part and the named desiderata's changes, so that the analyst can see this.
- Bad, because the generated rules read one vendor's position, so a trade-off between vendors shows only on a live case, not on the generated page.
- Bad, because two tables must be kept, and the authored table needs a person to write the roles and desiderata for each of the carried-over CS rules, and to narrow those that act in another machine.
- Neutral, because an authored rule for a move that move advice does not score, such as a PEC move (#6677), is an unscored rule.
- Neutral, because the endpoint of AR-07 and CM-07 still reads the legacy module.

## Validation

`test_cs_actions.py` still holds `CS_ACTION_RULES` equal to the legacy oracle over every valid compound state.
A test holds the source pairs of the carried-over authored rules equal to the pattern and action pairs of `CS_ACTION_RULES`, less the Vulnerabilities Equities Process pair, and holds each carried-over rule within its source pattern.
A test pins the rule disagreement of #6492: an authored rule that serves `D ≺ P` by an embargo extension, against the unhelpful band that move advice gives it.
The staleness check holds the generated rules and the generated page to the current move advice.

## Pros and Cons of the Options

### Authored rules only

- Good, because one table is simple to read and to keep.
- Bad, because nothing checks a rule: a wrong rule stays wrong until a person sees it.
- Bad, because the advice of the chance model stays apart from the rules, so the analyst must compare the two by eye.

### Generated rules only

- Good, because the rules follow the model, so they never drift from the advice.
- Bad, because each blind spot of the chance model becomes a rule, such as an extension that never serves (#6492), and nothing shows it.
- Bad, because a generated rule says which band a move is in, not why a person would make it.

### Both, with the generated rule replacing the authored rule where they disagree

- Good, because the analyst sees one answer for each position.
- Bad, because it treats the chance model as ground truth, so it hides each blind spot of the model behind a rule that looks authored.
- Bad, because it resolves each disagreement in silence.

### Both, compared, with each rule disagreement shown

- Good, because each kind can find the other's errors.
- Good, because the analyst sees the claim and the evidence side by side.
- Bad, because the analyst must judge each disagreement.

## More Information

Decided in the planning session for Epic #6668 on 2026-11-18, from analyst feedback on the case shadow tool.
The work is #6676.
Revision 2 (2026-11-19) records the user's rule-by-rule review while #6676 was built.
A rule's reason need not be a desideratum, a history-dependent band is stated as a conditional verdict, and the public's awareness is not a publication.
Ideas from that review: how an embargo ends (#6709), mitigations and detections as case facts (#6714), embargo terms (#6715), case completion (#6716), and time gaps between events (#6717).
The desiderata list that the reasons name is the move-advice definition that the desiderata table of #6669 reads.
PEC moves in move advice are #6677, consent as part of a participant's status is #6615, and an embargo's protection in the chance model is #6492.
The CS action rules and their legacy oracle are [ADR-0060](0060-re-express-legacy-cs-invariants.md).
The case shadow tool is [ADR-0190](0190-shadow-mode-is-a-standalone-read-only-advisor-that-translates-a-case-on-request.md), and the bands are [ADR-0200](0200-move-advice-puts-moves-in-bands-by-outcome-shift-not-by-one-case-score.md).

The spec groups that carry these rules are in `specs/case-shadow.yaml`, beside the move advice group SHD-03:

- **SHD-05 Action Rules**: the pattern, role, action and reason of a rule (rule 1 to rule 3), the authored table and the CS carry-over (rule 4), the generated rules and their rebuild and staleness check (rule 5), and the comparison and its five results (rule 6).
- **SHD-06 Action Rules on the Page**: the case shadow tool's display of the matching authored rules beside the bands, with each rule disagreement flagged (rule 7), and the generated docs page (rule 8).

CSB-17 keeps the CS validity rules that the CS part of a pattern reads.
AR-07 and CM-07 do not change (rule 9).

Generated spec requirements: `case-shadow.yaml` SHD-05-001 through SHD-05-030 and SHD-06-001 through SHD-06-007.
