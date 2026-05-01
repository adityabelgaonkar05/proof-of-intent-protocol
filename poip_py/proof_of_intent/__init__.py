"""
proof-of-intent — Python SDK for the Proof-of-Intent Protocol.

Quick start:

    from proof_of_intent import ContractClient, usdc, in_hours, UNISWAP_V3
    import os

    client = ContractClient(private_key=os.environ["PRIVATE_KEY"])
    intent_id = client.create_intent(
        token_in="0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",  # Sepolia USDC
        max_amount_in=usdc(100),
        min_amount_out=1,
        allowed_protocols=["Uniswap-V3"],
        deadline=in_hours(1),
    )
"""

from ._client import ContractClient, Scope
from ._helpers import (
    usdc, from_usdc,
    weth, from_weth,
    token, from_token,
    in_minutes, in_hours,
)
from ._protocols import (
    UNISWAP_V3, CURVE, BALANCER_V2, AAVE_V3, ONEINCH,
    ALL_PROTOCOLS, PROTOCOL_NAMES,
    protocol_name, protocol_id,
)
from ._sign import sign_intent, build_intent
from ._compiler import compile_intent
from .errors import POIPError, TransactionRevertError, ScopeViolationError, DeadlineExpiredError

__all__ = [
    # Core client
    "ContractClient",
    "Scope",
    # Helpers
    "usdc", "from_usdc",
    "weth", "from_weth",
    "token", "from_token",
    "in_minutes", "in_hours",
    # Protocols
    "UNISWAP_V3", "CURVE", "BALANCER_V2", "AAVE_V3", "ONEINCH",
    "ALL_PROTOCOLS", "PROTOCOL_NAMES",
    "protocol_name", "protocol_id",
    # Signing
    "sign_intent", "build_intent",
    # AI compiler
    "compile_intent",
    # Errors
    "POIPError", "TransactionRevertError", "ScopeViolationError", "DeadlineExpiredError",
]

__version__ = "0.1.0"
