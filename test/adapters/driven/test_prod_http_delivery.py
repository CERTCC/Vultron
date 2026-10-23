import pytest

from vultron.adapters.driven.prod_http_delivery import ProdHttpDeliveryAdapter


def test_prod_http_delivery_adapter_init_raises_not_implemented() -> None:
    with pytest.raises(
        NotImplementedError,
        match=r"ProdHttpDeliveryAdapter is not implemented yet.*OX-10-004",
    ):
        ProdHttpDeliveryAdapter()
