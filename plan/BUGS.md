# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

## mkdocs build errors — FIXED

These failures are blocking a PR merge.

Following is an example from `mkdocs build` output, but this may not be the
only such error. These all originate from the fact that `vultron` modules
have been refactored and reorganized and the `docs` files were not updated
to reflect those changes.

```text
DEBUG   -  Running `page_markdown` event from plugin 'autorefs'
DEBUG   -  mkdocstrings: Matched '::: vultron.case_states'
DEBUG   -  mkdocstrings: Using handler 'python'
DEBUG   -  mkdocstrings: Collecting data
ERROR   -  mkdocstrings: vultron.case_states could not be found
ERROR   -  Error reading page 'reference/code/case_states.md':
ERROR   -  Could not collect 'vultron.case_states'
```

These errors may be masking other problems, so the fix needs to continue
until all errors are resolved and the build completes successfully.

Done when `mkdocs build` completes successfully without ERROR messages.
