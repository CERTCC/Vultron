"""Tests for the case-state reference page generator."""

from __future__ import annotations

import frontmatter
import pytest

from vultron.core.case_states.make_doc import print_readme


@pytest.mark.spec("DF-11-005")
def test_readme_keeps_the_description_its_landing_page_lists(tmp_path):
    print_readme(model_dir=str(tmp_path))
    post = frontmatter.loads((tmp_path / "index.md").read_text())
    assert post.metadata["description"] == (
        "An annotated listing of every state in the case state model.\n"
    )
    assert post.content.startswith("<!-- This file is auto-generated.")
