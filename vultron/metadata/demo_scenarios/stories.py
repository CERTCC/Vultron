#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Render each scenario's plot as a numbered domain-terms story (DEMOCI-11-067).

The plot manifest (:mod:`.plots`) lists a story's items by code name, which a
CVD domain expert cannot review.  This module renders the same items as prose:
one ``{% include-markdown %}`` fragment per registered scenario, committed
beside the narrative pages that include it and drift-checked with the other
registry artifacts (:mod:`.sync`, DEMOCI-11-005, DEMOCI-11-069).

Two shapes of line, one per story item, numbered together so a reader can
count the steps:

- a **fragment** renders as its docstring's opening sentence, the one sentence
  that says what the step does in domain terms
  (:func:`~vultron.demo.helpers.story.fragment_sentence`, DEMOCI-11-065);
- a **choice** renders as ``"<deciding role> decides: <presenter label>"``,
  both read from the branch-point table, which is where a prompt and a label
  are declared and nowhere else (DEMOCI-11-013, DEMOCI-11-050).

A choice line carries no full stop and a fragment line does, because the
presenter label is quoted verbatim rather than rewritten into a sentence.  The
difference is useful: it is how a reader tells a decision from a step.

**The rendering never replaces the narrative.**  Each page's hand-written
narrative (#2204) is written without reading the code, so it can contradict
the code and be believed; a rendering of the code can only ever agree with it.
That is why the fragment is included *after* the narrative rather than in
place of it (DEMOCI-11-067).

Two checks live here rather than in :mod:`.narrative_pages`, because both read
the heading and the directive that only this module knows:
:func:`missing_story_includes` reports a page that does not end with its story
(DEMOCI-11-067) and :func:`orphan_story_fragments` a left-behind fragment no
registered scenario derives.  Both are aggregated by
:func:`.prose_checks.consistency_problems`, so they reach
``uv run demo-scenarios --check`` — the pre-commit hook — as well as the unit
suite.

This module imports the demo helper library for the same reason :mod:`.plots`
does, and at the same cost: reading a story's items needs
:class:`~vultron.demo.helpers.story.Choose`.  See that module's docstring.

Requirements: ``specs/demo-ci.yaml`` DEMOCI-11-005, DEMOCI-11-013,
DEMOCI-11-065 through DEMOCI-11-069; ``specs/documentation-framework.yaml``
DF-09-007.
Design: ``notes/demo-scenario-tree.md`` § "Composition"; ADR-0098.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from vultron.demo.helpers.story import Choose, fragment_sentence
from vultron.demo.scenario.branch_points import BRANCH_POINTS
from vultron.demo.scenario.registry import (
    AssembledStory,
    ScenarioSpec,
    discover_scenarios,
)
from vultron.enums.roles import CVDRole
from vultron.metadata.base import repo_root
from vultron.metadata.demo_scenarios.narrative_pages import (
    NARRATIVE_DIR,
    narrative_dir,
)
from vultron.metadata.markdown_tables import MarkdownSection, iter_sections

#: Heading the generated story sits under on every narrative page.  One
#: spelling, read by the renderer that writes it and by the check that looks
#: for it, so the two cannot disagree (DEMOCI-11-067).
STORY_HEADING = "The story as the code tells it"

#: The whole heading line a narrative page carries it as.  The level is part
#: of what :func:`missing_story_includes` asks — a ``###`` nested inside the
#: last narrative section is not a section of its own — so the two live
#: together.
STORY_SECTION = f"## {STORY_HEADING}"

#: The prose between the heading and the numbered list, generated rather than
#: hand-written on each page.  Eleven hand-copied copies of it would be the
#: one part of the section that could drift page to page with nothing to catch
#: it, the heading and the directive both being machine-written (CS-22-001,
#: DF-10-002).  One whole sentence per line (SG-38).
PREAMBLE = (
    "This is the plot of the scenario as the demo code composes it, "
    "generated from that code.\n"
    "It is here so a reader can check the narrative above against what the "
    "demo actually runs; where the two disagree, the narrative is the one "
    "written independently, so read it as the claim and this as the "
    "evidence."
)

#: How a deciding role is written in a story line.  Declared per member rather
#: than derived from the value, because ``"cve_numbering_authority".title()``
#: is "Cve Numbering Authority" — a spelling the glossary does not use, which a
#: future branch point for that role would silently publish.
#: ``test_every_role_has_a_story_label`` keeps this exhaustive.
DECIDING_ROLE_LABELS: Mapping[CVDRole, str] = MappingProxyType(
    {
        CVDRole.REPORTER: "Reporter",
        CVDRole.VENDOR: "Vendor",
        CVDRole.DEPLOYER: "Deployer",
        CVDRole.COORDINATOR: "Coordinator",
        CVDRole.OBSERVER: "Observer",
        CVDRole.CASE_OWNER: "Case Owner",
        CVDRole.CASE_MANAGER: "Case Manager",
        CVDRole.CVE_NUMBERING_AUTHORITY: "CVE Numbering Authority",
    }
)


def story_path(scenario: str) -> str:
    """Return the repo-relative path of *scenario*'s generated story fragment.

    Beside the narrative page that includes it, in the directory
    :mod:`.narrative_pages` owns the name of (DEMOCI-11-003).  A
    ``_``-prefixed name, so the page checks treat it as the include fragment
    it is rather than as a narrative page of its own (DEMOCI-11-046,
    DF-09-007), and ``mkdocs.yml``'s ``not_in_nav: _*.md`` keeps it out of
    the nav.
    """
    return f"{NARRATIVE_DIR}/_{scenario}-story.md"


def include_directive(scenario: str) -> str:
    """Return the directive a narrative page includes *scenario*'s story with.

    Relative to the including page, which is a sibling of the fragment, and
    written by this module so the page and the generator cannot disagree about
    the file name.
    """
    name = PurePosixPath(story_path(scenario)).name
    return f'{{% include-markdown "./{name}" %}}'


def choice_line(item: Choose) -> str:
    """Return *item* as ``"<deciding role> decides: <presenter label>"``.

    Both halves come from the branch-point table.  ``Choose`` validates its
    branch point and choice against that table when it is constructed
    (``validate_path``), so neither lookup here can miss.
    """
    branch_point = BRANCH_POINTS[item.branch_point]
    role = DECIDING_ROLE_LABELS[branch_point.role]
    return f"{role} decides: {branch_point.choice(item.choice).label}"


def story_lines(scenario: str, story: AssembledStory) -> list[str]:
    """Return *story*'s items in order, each as one line of prose.

    Args:
        scenario: The scenario the story belongs to, for error attribution.
        story: Its assembled story.

    Raises:
        DemoStoryError: As
            :func:`~vultron.demo.helpers.story.fragment_sentence`, which owns
            the rule about how a fragment says what it does. The tooling layer
            raises no ``VultronError`` of its own (MS-17-006).
    """
    return [
        choice_line(item)
        if isinstance(item, Choose)
        else fragment_sentence(item, scenario=scenario)
        for item in story.items
    ]


def render_story(
    scenario: str, story: AssembledStory, write_command: str
) -> str:
    """Return the full contents of *scenario*'s generated story fragment.

    Args:
        scenario: The scenario the story belongs to.
        story: Its assembled story.
        write_command: The command that rewrites the artifact, quoted in the
            file so a reader who found it by grep learns not to hand-edit it.

    Raises:
        DemoStoryError: As :func:`story_lines`.
    """
    numbered = "\n".join(
        f"{number}. {line}"
        for number, line in enumerate(story_lines(scenario, story), start=1)
    )
    # One whole sentence per line, unwrapped, as every other line under
    # docs/ is (SG-38): the comment is not rendered, but the style check
    # reads the source file it sits in (DF-09-007).
    return (
        "<!--\n"
        f"Generated by `{write_command}` from the {scenario} scenario's "
        "story (vultron/metadata/demo_scenarios/stories.py).\n"
        "Do not edit by hand: edit the story's fragments and choices, or a "
        "fragment's opening sentence, and re-run the command.\n"
        "-->\n"
        "\n"
        f"{PREAMBLE}\n"
        "\n"
        f"{numbered}\n"
    )


def story_fragments(
    specs: Iterable[ScenarioSpec], write_command: str
) -> dict[str, str]:
    """Return ``{path: desired contents}`` for every scenario's story fragment.

    One entry per registered scenario, in registry order.  Every spec is
    listed: ``ScenarioSpec`` requires a story, so there is no scenario whose
    page would have nothing to include (DEMOCI-11-024).

    Raises:
        DemoStoryError: As :func:`story_lines`.
    """
    return {
        story_path(spec.name): render_story(
            spec.name, spec.story, write_command
        )
        for spec in specs
    }


#: Glob matching a generated story fragment in :data:`NARRATIVE_DIR`, the
#: naming convention :func:`story_path` writes, read back.
_STORY_GLOB = "_*-story.md"


def _last_section_with_content(text: str) -> MarkdownSection | None:
    """Return the last section of *text* that holds anything, or ``None``.

    Document order, so "last" is what a reader reaches last.  A section whose
    body is only blank lines is skipped: a bare heading is not where the story
    is, and a trailing one would otherwise hide the real answer.
    """
    for section in reversed(iter_sections(text)):
        if any(line.strip() for _number, line in section.lines):
            return section
    return None


def _unfenced_body(section: MarkdownSection) -> str:
    """Return *section*'s body with its fenced code blocks dropped.

    A page that *documents* the include directive in a code block under the
    story heading would otherwise satisfy the check while including nothing.
    """
    return "\n".join(line for _number, line in section.unfenced_lines)


def _section_label(section: MarkdownSection | None) -> str:
    """Return how *section*'s heading is written, for a message.

    With its hashes, because the level is part of what the check asks: a
    ``### The story as the code tells it`` nested under the last narrative
    section is the "spliced in among the narrative's own steps" case, and a
    message naming only the text would read as though the heading were right.
    """
    if section is None or not section.heading:
        return "(no heading)"
    return f"{'#' * section.level} {section.heading}"


def missing_story_includes(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> list[str]:
    """Return registered scenarios whose page does not end with its story.

    Each narrative page includes its generated story *after* the hand-written
    narrative (DEMOCI-11-067), which is read here as the last section of the
    page: its heading is :data:`STORY_HEADING` and its body holds the include
    directive.  Reading it as "last" rather than "somewhere below the
    narrative" is what makes the position checkable — a page's narrative has
    no end marker, and a story spliced in among the narrative's own steps
    would read as part of it.

    A registered scenario whose page does not exist is skipped:
    :func:`.sync.missing_derived_paths` already reports it, and naming the
    same repair twice under two requirements tells a reader less.

    Raises:
        FileNotFoundError: If :data:`NARRATIVE_DIR` does not exist.
    """
    base = root or repo_root()
    resolved = discover_scenarios() if specs is None else specs
    # Asked for its refusal, not its result: a moved directory would make
    # every page below unreadable and this check pass over all of them
    # (DF-09-009).
    narrative_dir(base)
    problems: list[str] = []
    for spec in resolved:
        page = base / spec.narrative_path
        if not page.is_file():
            continue
        last = _last_section_with_content(page.read_text(encoding="utf-8"))
        if last is None or (last.heading, last.level) != (STORY_HEADING, 2):
            problems.append(
                f"{spec.narrative_path} ends with "
                f"{_section_label(last)!r}, not with a "
                f"'{STORY_SECTION}' section"
            )
        elif include_directive(spec.name) not in _unfenced_body(last):
            problems.append(
                f"{spec.narrative_path}'s '{STORY_SECTION}' section does not "
                f"include {story_path(spec.name)}"
            )
    return problems


def orphan_story_fragments(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> list[str]:
    """Return generated story fragments that no registered scenario derives.

    A retired scenario's page and demo module are deleted by hand, and its
    story fragment is as easy to leave behind — and once it is, nothing
    regenerates it, so it keeps publishing a story the code no longer tells.
    Neither :func:`.unregistered_narrative_pages`, which skips every
    ``_``-prefixed file (DEMOCI-11-046), nor the drift check, which compares
    only the paths the registry derives, can see it.

    Raises:
        FileNotFoundError: If :data:`NARRATIVE_DIR` does not exist.
    """
    base = root or repo_root()
    resolved = discover_scenarios() if specs is None else specs
    derived = {story_path(spec.name) for spec in resolved}
    return [
        relative
        for fragment in sorted(narrative_dir(base).glob(_STORY_GLOB))
        if (relative := fragment.relative_to(base).as_posix()) not in derived
    ]


__all__ = [
    "DECIDING_ROLE_LABELS",
    "PREAMBLE",
    "STORY_HEADING",
    "STORY_SECTION",
    "choice_line",
    "include_directive",
    "missing_story_includes",
    "orphan_story_fragments",
    "render_story",
    "story_fragments",
    "story_lines",
    "story_path",
]
