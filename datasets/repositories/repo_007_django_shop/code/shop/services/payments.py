def charge(order_id: int, amount_cents: int, token: str) -> dict:
    if amount_cents <= 0:
        return {"status": 400, "error": "invalid amount"}
    # Pretend to call a payment gateway.
    return {"status": 200, "charge_id": f"ch_{order_id}", "amount": amount_cents}
