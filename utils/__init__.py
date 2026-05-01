# ---------------------------------------------------------------------------
# utils — public API
#
# Helpers are importable without DEPLOYER_PRIVATE_KEY in env:
#     from utils import usdc, weth, in_minutes
#
# SDK objects trigger config loading (requires DEPLOYER_PRIVATE_KEY):
#     from utils import ContractClient, build_intent, sign_intent
# ---------------------------------------------------------------------------

from .helpers import (
    usdc, from_usdc,
    weth, from_weth,
    token, from_token,
    in_minutes,
)

__all__ = [
    # Helpers (no config dependency)
    "usdc", "from_usdc",
    "weth", "from_weth",
    "token", "from_token",
    "in_minutes",
    # SDK (loaded lazily — require DEPLOYER_PRIVATE_KEY)
    "ContractClient",
    "TransactionRevertError",
    "build_intent",
    "sign_intent",
]


def __getattr__(name: str):
    if name in ("ContractClient", "TransactionRevertError"):
        from .contract_client import ContractClient, TransactionRevertError  # noqa: PLC0415
        globals()["ContractClient"] = ContractClient
        globals()["TransactionRevertError"] = TransactionRevertError
        return globals()[name]
    if name in ("build_intent", "sign_intent"):
        from .sign_intent import build_intent, sign_intent  # noqa: PLC0415
        globals()["build_intent"] = build_intent
        globals()["sign_intent"] = sign_intent
        return globals()[name]
    raise AttributeError(f"module 'utils' has no attribute {name!r}")
