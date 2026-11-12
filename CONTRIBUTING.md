# Contributing to Vultron

Thank you for your interest in contributing to Vultron!

Please review our [Contribution Instructions](https://github.com/CERTCC/Vultron/blob/main/ContributionInstructions.md)
before submitting any Pull Requests.

<!--
## Code of Conduct

TODO write me 
-->

## How Can I Contribute?

There are a number of ways you can contribute to the development of Vultron.

### Participate in Discussions

- Participate in an existing [Discussion](https://github.com/CERTCC/Vultron/discussions)
  or start a new one.

### Report Bugs

- Check and see if an [Issue](https://github.com/CERTCC/Vultron/issues) already exists
- Create a new [Issue](https://github.com/CERTCC/Vultron/issues/new)

### Suggest Enhancements

- Check and see if an [Issue](https://github.com/CERTCC/Vultron/issues) already exists
- Create a new [Issue](https://github.com/CERTCC/Vultron/issues/new)
- If you've got an idea that might still need some more consideration before becoming a
  suggestion, consider opening a
  [Discussion](https://github.com/CERTCC/Vultron/discussions) thread instead.

### Submit Pull Requests

- Potential contributors should review
[ContributionInstructions.md](https://github.com/CERTCC/Vultron/blob/main/ContributionInstructions.md)
before submitting a PR.
- Before making any significant changes that you expect to result in a pull request, we
  encourage you to discuss your plans with the maintainers first, whether that be in the
  form of an [Issue](https://github.com/CERTCC/Vultron/issues) or a
  [Discussion](https://github.com/CERTCC/Vultron/discussions).
- Python code is formatted and linted with [ruff](https://docs.astral.sh/ruff/). Run
  `uv run ruff check` and `uv run ruff format --check` before committing; both read
  their scope from `pyproject.toml`, so they take no path arguments.

## Cutting a Release (Maintainers)

A release promotes a commit the site already published: one with a
`publish-YYYY-MM-DD.N` tag made by the
publish workflow (`.github/workflows/deploy_site.yml`). That commit passed CI and
the site checks, and was live.

To cut a Vultron release:

1. Open **Actions → Promote a publish to a release** and click **Run workflow**.
   Keep **Use workflow from** set to `main`; a run from any other branch or tag
   is refused.
2. Leave **publish-tag** empty to promote the newest publish, which is what the
   site shows now, or enter an older `publish-*` tag. A tag pushed by hand is
   refused.
3. The run tags that commit with the next three-component CalVer tag,
   `vYYYY.M.P`, for the current UTC month (ADR-0006), and opens a **draft**
   GitHub Release. The run summary links to the draft. The run never publishes it.
   When the drafts register (`docs/reference/vultron-spec/drafts.yaml`) at that
   commit names the new tag as a draft's release, the draft release already
   carries that draft's frozen pages, `vultron-spec-draft-N.tar.gz`, and their
   SHA-256 manifest, `vultron-spec-draft-N.sha256` (ADR-0188). Mark the draft
   released in the register, with the tag this run will make, before you run it.
4. Edit the draft in the GitHub release editor:
   - Keep the title, which is the version tag (e.g., `v2026.11.0`).
   - The notes start with the statement that all interfaces are experimental,
     followed by notes generated since the previous release. Keep the statement.
   - Once #3658 ships, the notes MUST also include the list of requirement IDs
     added and removed since the previous release.
   - **Leave the Pre-release box unchecked** so the repository has a Latest
     release.
   - Do not remove or replace the two frozen-draft files: once the release is
     published it is immutable, and no asset can be added to it.
5. Click **Publish release**.

A promote that fails deletes the draft release it created and keeps the tag, so
run it again. A re-run that finds a complete draft release refuses and leaves it
waiting for you to publish. Never publish a draft release that a run reported as
incomplete.

Every site publish, and the docs check of every pull request that touches the
site, serves each released draft's frozen pages at `spec/draft-N/` from its
published release (DOCBW-08-028). Until you publish the release, that address
shows a placeholder page and the run summary names the draft. Once the release
is published, a missing or mismatched archive fails every publish and files a
failure issue, and an immutable release cannot be repaired in place, so check
both files are attached before you click **Publish release**. A rollback to a
commit older than the step that serves the drafts is refused.

Do not tag a release by hand or from the **Draft a new release** dialog: the
dialog's default target is the tip of `main`, which is usually not what the site
shows. A `v*` tag pushed by hand whose commit has no `publish-*` tag files a
failure issue through the release tag check (`.github/workflows/release_tag_check.yml`).
Release and publish tags are append-only, so a wrong tag cannot be moved or
deleted; cut a new release instead.

`snapshot-YYYYQn` tags are checkpoints; they do not get a GitHub Release.
