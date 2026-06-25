from shop.views import cart, catalog


def urlpatterns() -> dict:
    return {
        "GET /products": catalog.list_products,
        "GET /products/{id}": catalog.product_detail,
        "POST /cart/add": cart.add_to_cart,
        "POST /cart/checkout": cart.checkout,
    }
