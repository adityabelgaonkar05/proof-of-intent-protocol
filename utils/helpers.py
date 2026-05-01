"""
Human-readable helpers for token amounts and deadlines.

Import from utils:
    from utils import usdc, weth, in_minutes
or directly:
    from utils.helpers import usdc, weth, in_minutes
"""
import time as _time


def usdc(amount: float) -> int:
    """Convert a human-readable USDC amount to raw units (6 decimals).

    usdc(500)   → 500_000_000
    usdc(0.5)   → 500_000
    """
    return int(amount * 10 ** 6)


def from_usdc(units: int) -> float:
    """Convert raw USDC units to a human-readable amount.

    from_usdc(500_000_000) → 500.0
    """
    return units / 10 ** 6


def weth(amount: float) -> int:
    """Convert a human-readable ETH/WETH amount to raw units (18 decimals).

    weth(0.15)  → 150_000_000_000_000_000
    weth(1)     → 1_000_000_000_000_000_000
    """
    return int(amount * 10 ** 18)


def from_weth(units: int) -> float:
    """Convert raw WETH/ETH units to a human-readable amount.

    from_weth(150_000_000_000_000_000) → 0.15
    """
    return units / 10 ** 18


def token(amount: float, decimals: int) -> int:
    """Convert a human-readable token amount to raw units for any ERC20.

    token(100, 6)  → 100_000_000   (e.g. USDC)
    token(1, 18)   → 1_000_000_000_000_000_000  (e.g. WETH)
    """
    return int(amount * 10 ** decimals)


def from_token(units: int, decimals: int) -> float:
    """Convert raw ERC20 units to a human-readable amount."""
    return units / 10 ** decimals


def in_minutes(n: int) -> int:
    """Return a Unix timestamp n minutes from now.

    Use as the deadline parameter:
        deadline=in_minutes(60)   # valid for 1 hour
    """
    return int(_time.time()) + n * 60
