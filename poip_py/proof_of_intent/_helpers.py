"""Human-readable helpers for token amounts and deadlines."""
import time as _time


def usdc(amount: float) -> int:
    """Convert a human-readable USDC amount to raw units (6 decimals).

    usdc(500) → 500_000_000
    """
    return int(amount * 10 ** 6)


def from_usdc(units: int) -> float:
    """Convert raw USDC units to a human-readable amount."""
    return units / 10 ** 6


def weth(amount: float) -> int:
    """Convert a human-readable ETH/WETH amount to raw units (18 decimals).

    weth(0.15) → 150_000_000_000_000_000
    """
    return int(amount * 10 ** 18)


def from_weth(units: int) -> float:
    """Convert raw WETH/ETH units to a human-readable amount."""
    return units / 10 ** 18


def token(amount: float, decimals: int) -> int:
    """Convert a human-readable token amount to raw units for any ERC20."""
    return int(amount * 10 ** decimals)


def from_token(units: int, decimals: int) -> float:
    """Convert raw ERC20 units to a human-readable amount."""
    return units / 10 ** decimals


def in_minutes(n: int) -> int:
    """Return a Unix timestamp n minutes from now."""
    return int(_time.time()) + n * 60


def in_hours(n: int) -> int:
    """Return a Unix timestamp n hours from now."""
    return int(_time.time()) + n * 3600
