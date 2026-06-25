from shop.models import Order, Product


class OutOfStock(Exception):
    pass


def reserve_stock(order: Order, catalog: dict[int, Product]) -> None:
    for product_id, qty in order.items.items():
        product = catalog[product_id]
        if product.stock < qty:
            raise OutOfStock(product.name)
        product.stock -= qty


def restock(product: Product, qty: int) -> None:
    product.stock += qty
