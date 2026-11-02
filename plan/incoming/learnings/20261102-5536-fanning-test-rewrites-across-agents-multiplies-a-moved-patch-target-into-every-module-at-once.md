---
title: "Fanning test rewrites across parallel agents turns one moved patch target into a break in every module at once"
type: learning
timestamp: "2026-11-02T17:30:00Z"
source: ISSUE-5536
signal: theme-candidate
---

**Trigger.** You are about to split a test rewrite across parallel subagents in
one worktree, and the same change moves a name that the *other* test modules
patch — a helper lifted into a new module, a call that now resolves somewhere
else, a re-export deleted.

**Claim.** Splitting by module bounds each agent's reading, not its blast
radius. A moved patch target breaks every module that patches it, including the
ones no agent owns, and each agent meets the break as a failure in a file it was
told not to edit. The outcomes are all bad: an agent repairs files outside its
brief (two agents may repair the same file), an agent reports the break and
leaves the suite red, or an agent concludes the source is wrong. The cheap
ordering is **move the name and repair its patchers first, alone, before fanning
out**, because that work is mechanical, is one commit, and is exactly the work
that cannot be partitioned by module.

**Evidence.** #5536 lifted `open_coordinated_cast`'s body into a new
`story_cast.open_story_cast`, so `reset_datalayer` and `get_actor_by_id` stopped
resolving on `coordinated_story`. Six agents were running: one owned
`test_coordinated_story.py` and repointed its three patches; the other five met
`AttributeError: module 'vultron.demo.helpers.coordinated_story' does not have
the attribute 'reset_datalayer'` in four coordinator-first modules nobody owned.
Two of them reported it as a source defect and left it; one repaired all four
and flagged the overreach. The issue that plans the next split (#5592) had
already written this hazard into its own body — "the split moves every
monkeypatch target … silently passing tests otherwise" — and #5534 had hit it
twice, so the knowledge existed and the fan-out still walked into it.

**How to apply.**

1. Before fanning out, diff the branch for names that moved modules or lost a
   re-export, and `grep` the whole test tree for `patch.object(<old home>,`
   and `patch("<old dotted path>` on each. That list is the unpartitionable
   work.
2. Land that repair as its own commit, with the suite green, *then* start the
   agents. A green base is what lets each agent treat a failure in a file it
   does not own as someone else's regression rather than a question.
3. If the repair cannot precede the fan-out, name every affected module in
   every agent's brief and say which agent owns it — "do not edit other test
   modules" is a worse instruction than "agent 3 owns these four".
4. A patch that no longer reaches the code does not necessarily fail: it can
   pass over nothing. So check the repair by making the patched collaborator
   raise and asserting the test notices, not by the suite going green.

**What would confirm it.** A second parallel fan-out — #5592's package split is
the obvious candidate, and #5537's `path=` retirement touches the same
modules — where a moved or deleted name reaches modules outside every agent's
brief. The counter-evidence would be a fan-out whose agents each repaired only
their own module because the move had been landed first.
