# Comment Resolution Guide

## Resolution Strategy

After code fixes and tests pass, the skill resolves review comments
**individually** with explanations. This ensures:

1. Each comment is addressed or explained
2. Reviewers know the status of their feedback
3. No comments are accidentally left unresolved

## Resolution Process

For each unresolved comment in the PR:

1. **Read the comment** — understand what was asked
2. **Check the code changes** — do they address it?
3. **Resolve or reply**:
   - ✅ Fully addressed → Resolve with explanation
   - ⚠️ Partially addressed → Reply explaining why
   - ❌ Cannot address → Reply explaining why

## Example Resolutions

### ✅ Fully Addressed

**Original comment**:
> "Line 42 should use the `NonEmptyString` validator for this field."

**Resolution message**:
> "Addressed in commit abc1234: Changed line 42 to use `NonEmptyString` validator as suggested. This ensures the field rejects empty strings."

### ⚠️ Partially Addressed

**Original comment**:
> "This linting error should be fixed, and we should also consider refactoring the entire module for consistency."

**Reply**:
> "Addressed the immediate linting issue (line 42) in commit abc1234. The broader refactoring concern is important but would be better as a separate effort—I've created issue #999 to track it. Want to discuss priorities?"

### ❌ Cannot Address / Needs Discussion

**Original comment**:
> "This changes the dispatcher architecture. Won't this break existing handlers?"

**Reply**:
> "Good catch. This change does modify dispatcher behavior, but only for the new CaseActor participant type—existing handlers are not affected (see ADR-007 for the architectural boundaries). Would you like me to add a code comment documenting this invariant?"

## Handling Non-Code Feedback

### Documentation Requests

**Original comment**:
> "This feature needs documentation on how to use it."

**Action**:

- If docs already updated → Resolve with pointer: "Documented in `docs/reference/...`"
- If docs needed → Reply: "I'll add this to issue #XXX for the documentation pass"

### Architecture/Design Questions

**Original comment**:
> "Why did you choose approach X instead of approach Y?"

**Action**:

- If decision is explained in ADR or design notes → Resolve with reference
- If deserves discussion → Reply: "Good question. Let's discuss in the design doc / ADR comment thread"
- Do NOT mark as resolved without addressing the concern

### Process/Style Feedback

**Original comment**:
> "Please update the AGENTS.md file to document this pattern."

**Action**:

- If documentation updated → Resolve with reference
- If deferred → Reply: "I've added this to the documentation backlog (issue #XXX)"

## Avoiding False Resolutions

**Do NOT resolve if**:

1. The code change doesn't actually address the comment
2. The comment asks for something that requires reviewer decision
3. The comment suggests a breaking change needing discussion
4. The comment is about future work that's been deferred

**Better to reply and ask**: "Is it OK to defer this to issue #XXX?" rather than
mark resolved prematurely.

## When a Comment Needs Follow-Up

If a comment asks for something you can't or shouldn't implement:

1. **Reply on the thread** explaining why
2. **Reference an issue** if the concern has been tracked elsewhere
3. **Ask for clarification** if the request is ambiguous
4. **Suggest a discussion** if it's architectural
5. **Leave unresolved** — let the reviewer close it when satisfied

Example:

> "I want to address this, but it would require changing the core dispatcher
> architecture. That's tracked in issue #XXX and might be out of scope for
> this PR. Can we discuss whether this should be a blocker or a follow-up?"

## Batch Resolution vs Individual

**This skill resolves individually** (not as a bulk action) because:

1. Each comment deserves a specific explanation
2. Different comments may have different resolution paths
3. Some comments may surface new issues or dependencies
4. Reviewers appreciate thoughtful responses

## After All Comments Resolved

Final check before closing the skill:

- [ ] All unresolved comments have been resolved or replied to
- [ ] All tests pass (unit and integration as needed)
- [ ] CI will be green on merge
- [ ] Commit history is clean and descriptive

If all checks pass, the PR is ready for merge approval.

## Edge Case: Reviewer Didn't Provide Feedback on Updates

Sometimes reviewers approve after fixes but leave comments "resolved."

**What this skill does**: Checks if the code change actually addresses the
original comment, then resolves manually with an explanation like:

> "Updated in commit abc1234 per your feedback. Let me know if this addresses
> your concern."

This is respectful to the reviewer and keeps the thread clean.
