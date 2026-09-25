"""Tests for the case-state reference page generator."""

from __future__ import annotations

import frontmatter
import pytest

from vultron.core.case_states.make_doc import print_model, print_readme


@pytest.mark.spec("DF-11-005")
def test_readme_keeps_the_description_its_landing_page_lists(tmp_path):
    print_readme(model_dir=str(tmp_path))
    post = frontmatter.loads((tmp_path / "index.md").read_text())
    assert post.metadata["description"] == (
        "An annotated listing of every state in the case state model.\n"
    )
    assert post.content.startswith("<!-- This file is auto-generated.")


@pytest.mark.spec("DF-11-012")
def test_readme_declares_itself_working_record(tmp_path):
    print_readme(model_dir=str(tmp_path))
    post = frontmatter.loads((tmp_path / "index.md").read_text())
    assert post.metadata["stakeholder_type"] == ["project-contributor"]
    assert "level" not in post.metadata


@pytest.mark.spec("DF-11-012")
def test_every_state_page_declares_itself_working_record(tmp_path):
    print_model(model_dir=str(tmp_path))
    pages = sorted(tmp_path.glob("state_*.md"))
    assert pages
    for page in pages:
        post = frontmatter.loads(page.read_text())
        assert post.metadata == {"stakeholder_type": ["project-contributor"]}
        assert post.content.startswith("<!-- This file is auto-generated.")
