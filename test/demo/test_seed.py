#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

"""Tests for ``vultron-demo seed`` CLI sub-command and ``seed_actor`` helper.

Tests cover:
- ``seed_actor`` helper calls ``POST /actors/`` correctly via DataLayerClient
- CLI ``seed`` invocation with various option combinations
- CLI ``seed`` with a JSON config file
- CLI ``seed`` reads actor name from environment variable
"""

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from vultron.demo.cli import main
from vultron.demo.utils import DataLayerClient, seed_actor
from vultron.wire.as2.vocab.base.objects.actors import as_Organization

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor_response(
    name: str, actor_id: str, actor_type: str = "Organization"
) -> dict:
    """Return a minimal actor JSON dict as would come from POST /actors/."""
    return {
        "type": actor_type,
        "id": actor_id,
        "name": name,
    }


def _mock_seed_actor(
    name: str, actor_id: str = "http://mock/actors/x"
) -> MagicMock:
    """Return a mock that simulates ``seed_actor`` returning an actor."""

    def _fn(client, name, actor_type="Organization", actor_id=None):
        resolved_id = actor_id or f"http://mock/actors/{name}"
        return as_Organization.model_validate(
            {"id": resolved_id, "name": name}
        )

    return MagicMock(side_effect=_fn)


# ---------------------------------------------------------------------------
# seed_actor helper (via mocked DataLayerClient.post)
# ---------------------------------------------------------------------------


class TestSeedActorHelper:
    def test_calls_post_actors_endpoint(self):
        mock_client = MagicMock(spec=DataLayerClient)
        mock_client.post.return_value = _make_actor_response(
            "TestOrg",
            "http://example.org/actors/testorg",
            "Organization",
        )
        actor = seed_actor(
            client=mock_client,
            name="TestOrg",
            actor_type="Organization",
            actor_id="http://example.org/actors/testorg",
        )
        mock_client.post.assert_called_once_with(
            "/actors/",
            json={
                "name": "TestOrg",
                "actor_type": "Organization",
                "id": "http://example.org/actors/testorg",
            },
        )
        assert actor.name == "TestOrg"

    def test_omits_id_when_not_provided(self):
        mock_client = MagicMock(spec=DataLayerClient)
        mock_client.post.return_value = _make_actor_response(
            "AutoId",
            "http://example.org/actors/generated-uuid",
        )
        seed_actor(
            client=mock_client, name="AutoId", actor_type="Organization"
        )
        payload = mock_client.post.call_args.kwargs["json"]
        assert "id" not in payload

    def test_returns_actor_with_correct_id(self):
        mock_client = MagicMock(spec=DataLayerClient)
        actor_id = "http://example.org/actors/alice"
        mock_client.post.return_value = _make_actor_response(
            "Alice", actor_id, "Person"
        )
        actor = seed_actor(
            client=mock_client,
            name="Alice",
            actor_type="Person",
            actor_id=actor_id,
        )
        assert actor.id_ == actor_id

    def test_passes_actor_type_in_payload(self):
        mock_client = MagicMock(spec=DataLayerClient)
        mock_client.post.return_value = _make_actor_response(
            "Svc", "http://example.org/actors/svc", "Service"
        )
        seed_actor(
            client=mock_client,
            name="Svc",
            actor_type="Service",
            actor_id="http://example.org/actors/svc",
        )
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["actor_type"] == "Service"


# ---------------------------------------------------------------------------
# seed CLI command
# ---------------------------------------------------------------------------


class TestSeedCommand:
    def test_seed_creates_local_actor(self, monkeypatch):
        monkeypatch.delenv("VULTRON_SEED_CONFIG", raising=False)
        monkeypatch.delenv("VULTRON_ACTOR_ID", raising=False)
        mock_fn = _mock_seed_actor("Finder", "http://finder/actors/f")
        runner = CliRunner()
        with patch("vultron.demo.cli.seed_actor", mock_fn):
            result = runner.invoke(
                main,
                [
                    "seed",
                    "--actor-name",
                    "Finder",
                    "--actor-type",
                    "Person",
                    "--api-url",
                    "http://localhost:7999/api/v2",
                ],
            )
        assert result.exit_code == 0, result.output
        assert mock_fn.called
        kwargs = mock_fn.call_args.kwargs
        assert kwargs["name"] == "Finder"
        assert kwargs["actor_type"] == "Person"

    def test_seed_success_output_contains_emoji(self, monkeypatch):
        monkeypatch.delenv("VULTRON_SEED_CONFIG", raising=False)
        monkeypatch.delenv("VULTRON_ACTOR_ID", raising=False)
        mock_fn = _mock_seed_actor("TestActor")
        runner = CliRunner()
        with patch("vultron.demo.cli.seed_actor", mock_fn):
            result = runner.invoke(
                main,
                [
                    "seed",
                    "--actor-name",
                    "TestActor",
                    "--api-url",
                    "http://localhost:7999/api/v2",
                ],
            )
        assert "🌱" in result.output
        assert "✅" in result.output

    def test_seed_with_config_file_creates_local_and_peer(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.delenv("VULTRON_SEED_CONFIG", raising=False)
        data = {
            "local_actor": {
                "name": "FileActor",
                "actor_type": "Person",
                "id": "http://file-actor/actors/fa",
            },
            "peers": [
                {
                    "name": "FilePeer",
                    "actor_type": "Organization",
                    "id": "http://file-peer/actors/fp",
                }
            ],
        }
        config_file = tmp_path / "seed.json"
        config_file.write_text(json.dumps(data))

        calls: list = []

        def _capturing_seed(
            client, name, actor_type="Organization", actor_id=None
        ):
            calls.append(
                {"name": name, "actor_type": actor_type, "actor_id": actor_id}
            )
            return as_Organization.model_validate(
                {"id": actor_id or f"http://mock/{name}", "name": name}
            )

        mock_fn = MagicMock(side_effect=_capturing_seed)
        runner = CliRunner()
        with patch("vultron.demo.cli.seed_actor", mock_fn):
            result = runner.invoke(
                main,
                [
                    "seed",
                    "--config",
                    str(config_file),
                    "--api-url",
                    "http://localhost:7999/api/v2",
                ],
            )
        assert result.exit_code == 0, result.output
        assert mock_fn.call_count == 2
        names = {c["name"] for c in calls}
        assert "FileActor" in names
        assert "FilePeer" in names

    def test_seed_command_registered_in_main_group(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "seed" in result.output

    def test_seed_reads_actor_name_from_env(self, monkeypatch):
        monkeypatch.setenv("VULTRON_ACTOR_NAME", "EnvNamedActor")
        monkeypatch.delenv("VULTRON_ACTOR_TYPE", raising=False)
        monkeypatch.delenv("VULTRON_ACTOR_ID", raising=False)
        monkeypatch.delenv("VULTRON_SEED_CONFIG", raising=False)

        captured: list = []

        def _capturing_seed(
            client, name, actor_type="Organization", actor_id=None
        ):
            captured.append(name)
            return as_Organization.model_validate(
                {"id": actor_id or "http://mock/actors/x", "name": name}
            )

        mock_fn = MagicMock(side_effect=_capturing_seed)
        runner = CliRunner()
        with patch("vultron.demo.cli.seed_actor", mock_fn):
            result = runner.invoke(
                main,
                ["seed", "--api-url", "http://localhost:7999/api/v2"],
                env={"VULTRON_ACTOR_NAME": "EnvNamedActor"},
            )
        assert result.exit_code == 0, result.output
        assert mock_fn.called
        assert captured[0] == "EnvNamedActor"

    def test_seed_multiple_peers_all_seeded(self, tmp_path, monkeypatch):
        monkeypatch.delenv("VULTRON_SEED_CONFIG", raising=False)
        data = {
            "local_actor": {"name": "Local", "id": "http://local/actors/l"},
            "peers": [
                {"name": "PeerA", "id": "http://peer-a/actors/a"},
                {"name": "PeerB", "id": "http://peer-b/actors/b"},
                {"name": "PeerC", "id": "http://peer-c/actors/c"},
            ],
        }
        config_file = tmp_path / "multi_peer.json"
        config_file.write_text(json.dumps(data))

        mock_fn = MagicMock(
            side_effect=lambda client, name, actor_type="Organization", actor_id=None: as_Organization.model_validate(
                {"id": actor_id or f"http://mock/{name}", "name": name}
            )
        )
        runner = CliRunner()
        with patch("vultron.demo.cli.seed_actor", mock_fn):
            result = runner.invoke(
                main,
                [
                    "seed",
                    "--config",
                    str(config_file),
                    "--api-url",
                    "http://localhost:7999/api/v2",
                ],
            )
        assert result.exit_code == 0, result.output
        # 1 local + 3 peers = 4 total calls
        assert mock_fn.call_count == 4
