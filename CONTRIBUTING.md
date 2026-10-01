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

- Participate in an existing [Discussion](https://github.com/CERTCC/Vultron/discussions) or start a new one.

### Report Bugs

- Check and see if an [Issue](https://github.com/CERTCC/Vultron/issues) already exists
- Create a new [Issue](https://github.com/CERTCC/Vultron/issues/new)

### Suggest Enhancements

- Check and see if an [Issue](https://github.com/CERTCC/Vultron/issues) already exists
- Create a new [Issue](https://github.com/CERTCC/Vultron/issues/new)
- If you've got an idea that might still need some more consideration before becoming a suggestion, consider opening a [Discussion](https://github.com/CERTCC/Vultron/discussions) thread instead.

### Submit Pull Requests

- Potential contributors should review
[ContributionInstructions.md](https://github.com/CERTCC/Vultron/blob/main/ContributionInstructions.md)
before submitting a PR.
- Before making any significant changes that you expect to result in a pull request, we encourage you to discuss your plans with
  the maintainers first, whether that be in the form of an [Issue](https://github.com/CERTCC/Vultron/issues) or a [Discussion](https://github.com/CERTCC/Vultron/discussions).
- Python code is formatted and linted with [ruff](https://docs.astral.sh/ruff/).
  Run `uv run ruff check` and `uv run ruff format --check` before committing; both read their scope from `pyproject.toml`, so they take no path arguments.

## Cutting a Release (Maintainers)

To cut a Vultron release:

1. Create a three-component CalVer tag: `git tag vYYYY.M.P` (for example, `v2026.10.0`).
   The patch component is always present — do not omit it.
   `snapshot-YYYYQn` tags are checkpoints; they do not get a GitHub Release.
2. Push the tag: `git push origin vYYYY.M.P`.
3. Create a GitHub Release for that tag.
   - Title: the version tag (e.g., `v2026.10.0`).
   - **Uncheck the Pre-release box** so the repository has a Latest release.
   - Release notes MUST include the statement that all interfaces are experimental.
   - Once #3658 ships, release notes MUST also include the list of requirement IDs
     added and removed since the previous release.
