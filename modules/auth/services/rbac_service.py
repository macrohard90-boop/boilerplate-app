"""Role hierarchy and permission checking helpers."""

# Role hierarchy: admin > merchant > customer
ROLE_HIERARCHY: dict[str, int] = {
    "admin": 100,
    "merchant": 50,
    "customer": 10,
}


def has_role_or_higher(user_role: str, required_role: str) -> bool:
    """Check if ``user_role`` meets or exceeds ``required_role`` in the hierarchy."""
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    required_level = ROLE_HIERARCHY.get(required_role, 0)
    return user_level >= required_level


def has_permission(user_permissions: list[str], required: str) -> bool:
    """Check if the required ``resource:action`` permission is in the user's list."""
    return required in user_permissions
