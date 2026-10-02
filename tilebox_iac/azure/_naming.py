import hashlib


def resource_name(name: str, max_length: int) -> str:
    """Shorten long logical names while leaving room for the provider's random suffix."""
    if len(name) <= max_length:
        return name
    return name[: max_length - 12] + hashlib.sha256(name.encode()).hexdigest()[:12]
