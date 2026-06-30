from shop.models import Order
from shop.services.inventory import reserve_stock


def add_to_cart(order: Order, product_id: int, qty: int) -> Order:
    order.items[product_id] = order.items.get(product_id, 0) + qty
    return order


def checkout(order: Order, catalog: dict) -> dict:
    # BUG: stock is not re-checked at checkout, so oversells are possible.
    reserve_stock(order, catalog)
    order.status = "paid"
    return {"status": 200, "order_id": order.id}
