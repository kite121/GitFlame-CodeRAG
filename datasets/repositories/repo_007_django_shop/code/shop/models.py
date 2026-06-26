from dataclasses import dataclass, field


@dataclass
class Product:
    id: int
    name: str
    price_cents: int
    stock: int = 0


@dataclass
class Order:
    id: int
    items: dict[int, int] = field(default_factory=dict)  # product_id -> qty
    status: str = "pending"


def order_total(order: Order, catalog: dict[int, Product]) -> int:
    total = 0
    for product_id, qty in order.items.items():
        total += catalog[product_id].price_cents * qty
    return total
