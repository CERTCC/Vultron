"""Check a PR body against each rule: :func:`lint_body` and its per-rule checks."""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

from vultron.metadata.markdown_tables import fenced_lines
from vultron.metadata.planning.pr_body_lint.facts import BodyFacts
from vultron.metadata.planning.pr_body_lint.rules import (
    BODY_LIMIT,
    DOCS_PLACEHOLDER,
    MANIFEST_LINES,
    RULES,
    RULES_BY_ID,
    PrType,
    Stage,
)

#: A reference GitHub closes on merge: a keyword, an optional colon, then
#: ``#N``, ``owner/repo#N`` or an issue URL.
_CLOSING_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?):?\s+"
    r"(?:[\w.-]+/[\w.-]+#\d+|#\d+"
    r"|https://github\.com/[\w.-]+/[\w.-]+/issues/\d+)",
    re.I,
)


_CLOSES_BULLET_RE = re.compile(r"^- (?:Closes|Fixes|Resolves) #\d+$")


#: An inline code span; GitHub reads no closing keyword inside one.
_CODE_SPAN_RE = re.compile(r"(`+)(?!`).*?(?<!`)\1(?!`)")


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


_SECTION_LEVEL = 2


_BLOCK_LEVEL = 3


_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


_ISSUES_RE = re.compile(r"^Issues: closed \d+, opened \d+\b")


_QUESTIONS_RE = re.compile(r"^Questions: asked \d+, filed \d+\b")


_RANGE_RE = re.compile(r"\b[A-Z]+-\d\d(?:-\d{3})?\.\.")


_ATTRIBUTION_RE = re.compile(r"Generated with \[[^\]]+\]\([^)]+\)")


_DOCS_FINAL_RE = re.compile(
    r"^Docs: (?:updated \S.*|no docs impact — \S.*|deferred to #\d+)$"
)


#: The fourth final form, which answers only the maintainer-docs question: a
#: final form only on a PR with a maintainer-docs gap (PRB-12), since it says
#: nothing about ``docs/`` pages (PD-03-013).
_DOCS_MAINTAINER_ONLY_RE = re.compile(
    r"^Docs: no maintainer docs impact — \S.*$"
)


#: A ``Docs:`` line that accounts for a maintainer-docs gap (PRB-12): it names
#: the follow-up issue, or says why no maintainer doc needs the change. Each
#: clause starts the line or follows a ``; `` separator, so a reason that
#: merely mentions a deferral does not count. The reader-facing
#: ``no docs impact`` verdict does not count either: it answers whether a
#: ``docs/`` page describes the change, not whether a maintainer doc does.
_DOCS_GAP_RE = re.compile(
    r"(?:^Docs: |; )(?:deferred to #\d+(?:;|$)|no maintainer docs impact — \S)"
)


#: ``Part of #N``, the reference a split's non-final PR carries in place of
#: ``Closes #N`` (``bundling.md`` § "Split PRs"). Twinned in
#: ``.github/scripts/stale_claim_sweeper.py``, which cannot import this module.
_PART_OF_RE = re.compile(r"\bPart of #(\d+)\b", re.I)


@dataclass(frozen=True)
class Finding:
    """One rule violation."""

    rule_id: str
    message: str

    def render(self) -> str:
        """``PRB-NN name: message``."""
        return (
            f"{self.rule_id} {RULES_BY_ID[self.rule_id].name}: {self.message}"
        )


@dataclass
class _Body:
    """The body split into lines and ``##`` sections.

    HTML comments are blanked (line count kept), and a line inside a fenced
    code block is never read as a heading or a closing reference: a manifest
    pasted in a ```` ```text ```` fence still belongs to its section.
    """

    text: str
    lines: list[str] = field(init=False)
    fenced: list[bool] = field(init=False)
    sections: dict[str, list[str]] = field(init=False)
    section_fenced: dict[str, list[bool]] = field(init=False)

    def __post_init__(self) -> None:
        bare = _COMMENT_RE.sub(
            lambda m: "\n" * m.group(0).count("\n"), self.text
        )
        self.lines = bare.splitlines()
        inside = fenced_lines(bare)
        self.fenced = [n in inside for n in range(1, len(self.lines) + 1)]
        self.sections = {}
        self.section_fenced = {}
        current: str | None = None
        for line, fenced in zip(self.lines, self.fenced, strict=True):
            heading = None if fenced else _HEADING_RE.match(line)
            if heading and len(heading.group(1)) == _SECTION_LEVEL:
                name: str = heading.group(2)
                current = name
                self.sections.setdefault(name, [])
                self.section_fenced.setdefault(name, [])
                continue
            if current is not None:
                self.sections[current].append(line)
                self.section_fenced[current].append(fenced)

    def section(self, name: str) -> list[str] | None:
        """The lines under ``## <name>`` up to the next ``##``, or ``None``."""
        return self.sections.get(name)


def _check_closing(body: _Body) -> Iterator[Finding]:
    """PRB-01 and PRB-02."""
    in_opening = True
    for number, (line, fenced) in enumerate(
        zip(body.lines, body.fenced, strict=True), start=1
    ):
        stripped = line.strip()
        if not stripped:
            continue
        if fenced:
            in_opening = False
            continue
        refs = _CLOSING_RE.findall(_CODE_SPAN_RE.sub("", stripped))
        if in_opening and refs:
            if len(refs) > 1 or not _CLOSES_BULLET_RE.match(stripped):
                yield Finding(
                    "PRB-02",
                    f"line {number} is not a single `- Closes #N` bullet: "
                    f"{stripped!r}",
                )
            continue
        in_opening = False
        if refs:
            yield Finding(
                "PRB-01",
                f"line {number} carries a closing reference after the opening "
                f"block ({', '.join(refs)}); move it to the top as its own "
                f"`- Closes #N` line, or reword it so GitHub does not close "
                f"the issue",
            )


def _check_sections(body: _Body, facts: BodyFacts) -> Iterator[Finding]:
    """PRB-03, PRB-04, PRB-07 and PRB-13."""
    for name in ("Summary", "Changes"):
        if body.section(name) is None:
            yield Finding("PRB-03", f"no `## {name}` section")
    summary = body.section("Summary")
    if facts.pr_type is PrType.IMPLEMENTATION and summary is not None:
        lines = [ln.strip() for ln in summary if ln.strip()] or [""]
        has_questions = bool(_QUESTIONS_RE.match(lines[-1]))
        issues = lines[-2] if has_questions and len(lines) > 1 else lines[-1]
        if not _ISSUES_RE.match(issues):
            yield Finding(
                "PRB-04",
                "`## Summary` does not end with `Issues: closed N, opened M` "
                "(followed only by the `Questions:` line)",
            )
        if not has_questions:
            yield Finding(
                "PRB-13",
                "the last line of `## Summary` is not `Questions: asked N, "
                "filed M`",
            )
    if facts.py_changed and body.section("Verification") is None:
        yield Finding(
            "PRB-07",
            "the diff changes `.py` files but there is no "
            "`## Verification` section",
        )


def _check_specs(body: _Body, facts: BodyFacts) -> Iterator[Finding]:
    """PRB-05 and PRB-06."""
    if facts.pr_type is not PrType.IMPLEMENTATION:
        return
    specs = body.section("Specs")
    if specs is None:
        yield Finding("PRB-05", "no `## Specs` section")
        return
    stripped = [ln.strip().lstrip("-*+ ").replace("*", "") for ln in specs]
    for label in MANIFEST_LINES:
        if not any(ln.startswith(label) for ln in stripped):
            yield Finding(
                "PRB-05",
                f"`## Specs` has no `{label}` line; paste the Spec manifest "
                f"deepen-context returned, not a list of IDs",
            )
    for line in specs:
        if _RANGE_RE.search(line):
            yield Finding(
                "PRB-05",
                f"`## Specs` writes an ID range ({line.strip()!r}); list every "
                f"ID in full",
            )
    if facts.manifest is not None:
        present = {ln.strip() for ln in specs}
        for line in facts.manifest.splitlines():
            if line.strip() and line.strip() not in present:
                yield Finding(
                    "PRB-06",
                    f"the resolved manifest line {line.strip()!r} is not in "
                    f"`## Specs` verbatim; copy the manifest file, do not "
                    f"retype it",
                )


def _docs_lines(body: _Body) -> list[str]:
    """Every unfenced line of *body* that begins ``Docs:``, stripped."""
    return [
        ln.strip()
        for ln, fenced in zip(body.lines, body.fenced, strict=True)
        if not fenced and ln.strip().startswith("Docs:")
    ]


def _is_final_docs_line(line: str, facts: BodyFacts) -> bool:
    """Whether *line* takes a final ``Docs:`` form for this PR.

    The bare ``no maintainer docs impact — …`` form is final only on a PR
    with a maintainer-docs gap (PRB-12).
    """
    return bool(
        _DOCS_FINAL_RE.match(line)
        or (
            facts.undocumented_tooling and _DOCS_MAINTAINER_ONLY_RE.match(line)
        )
    )


def _not_final_message(line: str, facts: BodyFacts) -> str:
    """The finding text for a ``Docs:`` line in no final form."""
    forms = "`updated <page>, ...`, `no docs impact — <reason>`, "
    if facts.undocumented_tooling:
        forms += "`no maintainer docs impact — <reason>`, "
    return f"{line!r} is not a final `Docs:` form: {forms}or `deferred to #N`"


def _check_docs(body: _Body, facts: BodyFacts) -> Iterator[Finding]:
    """PRB-08."""
    if not facts.needs_docs_line:
        return
    docs = _docs_lines(body)
    if not docs:
        yield Finding(
            "PRB-08",
            f"no `Docs:` line; create-pr writes `{DOCS_PLACEHOLDER}` and "
            f"check-docs-sync replaces it",
        )
        return
    if facts.stage is not Stage.FINAL:
        return
    for line in docs:
        if line == DOCS_PLACEHOLDER:
            yield Finding(
                "PRB-08",
                "the `Docs:` line is still the placeholder; replace it with "
                "the line check-docs-sync reported (PD-03-013)",
            )
        elif not _is_final_docs_line(line, facts):
            yield Finding("PRB-08", _not_final_message(line, facts))


def _check_maintainer_docs(body: _Body, facts: BodyFacts) -> Iterator[Finding]:
    """PRB-12 (PD-03-014).

    On a PR that PRB-08 covers, PRB-08 already reports a missing line and
    the placeholder at the final stage, so this rule stays silent there; on
    any other PR it reports both itself, and a line in no final form. The
    gap test is coarse: any maintainer-facing doc in the diff closes it, so
    whether that doc covers the change is left to review (``pr-triage``).
    """
    if not facts.undocumented_tooling:
        return
    shown = ", ".join(facts.undocumented_tooling[:3])
    if len(facts.undocumented_tooling) > 3:
        shown += f" and {len(facts.undocumented_tooling) - 3} more"
    docs = _docs_lines(body)
    if not docs:
        if not facts.needs_docs_line:
            yield Finding(
                "PRB-12",
                f"the diff changes workflow or tooling files ({shown}) and "
                f"no maintainer-facing doc, but the body has no `Docs:` "
                f"line; add `Docs: deferred to #N` naming the follow-up "
                f"docs issue, or `Docs: no maintainer docs impact — <reason>`",
            )
        return
    if facts.stage is Stage.FINAL:
        yield from _judge_maintainer_docs_line(docs, facts, shown)


def _judge_maintainer_docs_line(
    docs: Sequence[str], facts: BodyFacts, shown: str
) -> Iterator[Finding]:
    """PRB-12 at the final stage, on a body that has a ``Docs:`` line."""
    if facts.needs_docs_line:
        if any(line == DOCS_PLACEHOLDER for line in docs):
            return
    else:
        # PRB-08 does not judge a docs PR's line, so this rule checks its
        # form; a line in no final form is reported once, as that.
        unfinished = [ln for ln in docs if not _is_final_docs_line(ln, facts)]
        for line in unfinished:
            yield Finding("PRB-12", _not_final_message(line, facts))
        if unfinished:
            return
    if not any(_DOCS_GAP_RE.search(line) for line in docs):
        yield Finding(
            "PRB-12",
            f"the diff changes workflow or tooling files ({shown}) and no "
            f"maintainer-facing doc, but the `Docs:` line names no follow-up "
            f"issue; update the maintainer docs in this PR, or add "
            f"`deferred to #N` naming the follow-up docs issue, or "
            f"`no maintainer docs impact — <reason>` when no maintainer doc "
            f"needs the change",
        )


def _check_amended(body: _Body, facts: BodyFacts) -> Iterator[Finding]:
    """PRB-09."""
    if not facts.amended_ids:
        return
    section = body.section("Spec amended")
    if section is None:
        yield Finding(
            "PRB-09",
            f"spec-amendments.sh lists {', '.join(facts.amended_ids)} but "
            f"there is no `## Spec amended` section",
        )
        return
    fenced = body.section_fenced["Spec amended"]
    blocks = {
        m.group(2).strip()
        for ln, in_fence in zip(section, fenced, strict=True)
        if not in_fence
        and (m := _HEADING_RE.match(ln))
        and len(m.group(1)) == _BLOCK_LEVEL
    }
    for spec_id in facts.amended_ids:
        if spec_id not in blocks:
            yield Finding(
                "PRB-09", f"`## Spec amended` has no `### {spec_id}` block"
            )
    if facts.stage is Stage.FINAL and any("<TODO" in ln for ln in section):
        yield Finding(
            "PRB-09",
            "`## Spec amended` still holds a `<TODO>` field; fill it from "
            "the specs/ diff",
        )


def _check_attribution(body: _Body) -> Iterator[Finding]:
    """PRB-10."""
    filled = [(n, ln) for n, ln in enumerate(body.lines, 1) if ln.strip()]
    marked = [n for n, ln in filled if _ATTRIBUTION_RE.search(ln)]
    if marked and marked[-1] != filled[-1][0]:
        yield Finding(
            "PRB-10",
            f"the attribution line (line {marked[-1]}) is not the last line "
            f"of the body",
        )


def _check_length(text: str) -> Iterator[Finding]:
    """PRB-11."""
    if len(text) > BODY_LIMIT:
        yield Finding(
            "PRB-11",
            f"the body is {len(text):,} characters, over GitHub's "
            f"{BODY_LIMIT:,}-character limit; shorten it (a long "
            f"`## Spec amended` statement can show its changed span)",
        )


def _is_claim_branch(branch: str | None, issue: int) -> bool:
    """Whether *branch* has the claim-branch name of *issue* (PAD-04-001).

    ``claim-issue.sh`` always names it ``<prefix>/<issue>-<slug>``, so the
    name alone says GitHub linked it to *issue*. A split's sibling branch
    ``<prefix>/<issue>a-<slug>`` does not match.
    """
    if branch is None:
        return False
    _, sep, rest = branch.partition("/")
    return bool(sep) and rest.startswith(f"{issue}-")


def _part_of_refs(body: _Body) -> list[int]:
    """The issue numbers of every ``Part of #N`` outside code, in order."""
    numbers: list[int] = []
    for line, fenced in zip(body.lines, body.fenced, strict=True):
        if fenced:
            continue
        for match in _PART_OF_RE.finditer(_CODE_SPAN_RE.sub("", line)):
            number = int(match.group(1))
            if number not in numbers:
                numbers.append(number)
    return numbers


def _check_part_of(body: _Body, facts: BodyFacts) -> Iterator[Finding]:
    """PRB-14: a `Part of #N` PR must not close #N (PAD-04-008)."""
    fix = (
        "open this part from an unlinked sibling branch such as "
        "`task/<N>a-<slug>` and keep the claim branch for the final "
        '`Closes #N` PR (bundling.md § "Split PRs")'
    )
    for issue in _part_of_refs(body):
        if issue in facts.closing_refs:
            yield Finding(
                "PRB-14",
                f"the body says `Part of #{issue}`, but GitHub lists #{issue} "
                f"in this PR's closingIssuesReferences, so merging closes it; "
                f"{fix.replace('<N>', str(issue))}",
            )
        elif _is_claim_branch(facts.head_branch, issue):
            yield Finding(
                "PRB-14",
                f"the body says `Part of #{issue}`, but the head branch "
                f"`{facts.head_branch}` is #{issue}'s linked claim branch, "
                f"so merging closes #{issue}; "
                f"{fix.replace('<N>', str(issue))}",
            )


def lint_body(text: str, facts: BodyFacts) -> list[Finding]:
    """Every finding for the body *text*, in rule order."""
    body = _Body(text)
    findings = [
        *_check_closing(body),
        *_check_sections(body, facts),
        *_check_specs(body, facts),
        *_check_docs(body, facts),
        *_check_amended(body, facts),
        *_check_attribution(body),
        *_check_length(text),
        *_check_maintainer_docs(body, facts),
        *_check_part_of(body, facts),
    ]
    order = {rule.rule_id: i for i, rule in enumerate(RULES)}
    return sorted(findings, key=lambda f: order[f.rule_id])
