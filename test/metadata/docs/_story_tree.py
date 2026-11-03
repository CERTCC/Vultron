"""The story-catalog file every throwaway ``docs-site`` checkout needs.

``uv run docs-site`` generates the user-story index table and traceability
matrix from the requirement registry's ``stories:`` fields and the story-page
catalog (TRACE-01-001, TRACE-03-003), and it refuses a tree whose catalog
resolves no pages, just as it refuses one with no lookup page (DF-09-009). A
test tree built for another artifact adds :data:`STORY_FILES` through
:func:`with_stories`.

One page is enough: the artifacts enumerate the catalog, and a tree with no
``specs/`` directory loads an empty registry, so the one story renders as
uncited. A test about the story artifacts themselves writes its own catalog
(``test_story_coverage.py``).
"""

from __future__ import annotations

from vultron.metadata.docs.story_pages import STORY_DIR

#: The one story ID the seed catalog holds.
SEED_STORY = "story_2022_001"

#: ``docs/``-relative files: one story page, which is working record
#: (DF-11-012, DF-11-033) and so declares a stakeholder type and no level.
STORY_FILES: dict[str, str] = {
    f"{STORY_DIR}/{SEED_STORY}.md": (
        "---\nstakeholder_type: [project-contributor]\n---\n\n"
        "# User Story `2022_001`\n\n"
        "<!-- story-start -->As a Participant, do the thing<!-- story-end -->\n"
    )
}


def with_stories(files: dict[str, str]) -> dict[str, str]:
    """*files* with the seed story page added; *files* wins a clash."""
    return {**STORY_FILES, **files}
