from shop.models import Product


def list_products(catalog: dict[int, Product], in_stock_only: bool = False) -> list[dict]:
    products = catalog.values()
    if in_stock_only:
        products = [p for p in products if p.stock > 0]
    return [vars(p) for p in products]


def product_detail(catalog: dict[int, Product], product_id: int) -> dict | None:
    product = catalog.get(product_id)
    return vars(product) if product else None
