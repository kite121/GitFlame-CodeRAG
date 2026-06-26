import pytest

from shop.models import Order, Product
from shop.services.inventory import OutOfStock, reserve_stock


def test_reserve_stock_raises_when_insufficient():
    catalog = {1: Product(id=1, name="Widget", price_cents=100, stock=1)}
    order = Order(id=1, items={1: 5})
    with pytest.raises(OutOfStock):
        reserve_stock(order, catalog)
