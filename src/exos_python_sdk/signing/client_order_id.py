"""Source-aware client order ID generation and validation."""

import secrets

from ..exceptions import SigningError
from .models import OrderSource, Region


def generate_client_order_id(
    region: Region = Region.HK, source: OrderSource = OrderSource.API
) -> str:
    """Generate ``0x + region nibble + source nibble + 120 random bits``."""

    if not isinstance(region, Region):
        raise SigningError("region must be a Region")
    if not isinstance(source, OrderSource):
        raise SigningError("source must be an OrderSource")
    return f"0x{region.value:x}{source.value:x}{secrets.token_hex(15)}"


def validate_client_order_id(value: str) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 34
        and value[:2].lower() == "0x"
        and all(char.lower() in "0123456789abcdef" for char in value[2:])
    )
