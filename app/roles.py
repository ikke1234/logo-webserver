def has_min_role(user_role: str, required: str) -> bool:
    order = ["viewer", "editor", "admin"]
    return order.index(user_role) >= order.index(required)
