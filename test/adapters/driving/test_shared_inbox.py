import pytest

from vultron.adapters.driving.shared_inbox import SharedInboxAdapter


def test_shared_inbox_adapter_init_raises_not_implemented() -> None:
    with pytest.raises(
        NotImplementedError,
        match="SharedInboxAdapter is not implemented yet",
    ):
        SharedInboxAdapter()
