# ---------------------------------------------------------------------------
# utils — public API
#
# Forwards to proof_of_intent (the installable package) for SDK objects.
# Helpers are importable with no env vars set:
#     from utils import usdc, weth, in_minutes
# SDK objects are also available here for backwards compatibility:
#     from utils import ContractClient, build_intent, sign_intent
# ---------------------------------------------------------------------------

from .helpers import (
    usdc, from_usdc,
    weth, from_weth,
    token, from_token,
    in_minutes,
)

__all__ = [
    "usdc", "from_usdc",
    "weth", "from_weth",
    "token", "from_token",
    "in_minutes",
    "ContractClient",
    "TransactionRevertError",
    "build_intent",
    "sign_intent",
    "axl_client",
]


def __getattr__(name: str):
    if name in ("ContractClient", "TransactionRevertError"):
        from proof_of_intent import ContractClient  # noqa: PLC0415
        from proof_of_intent.errors import TransactionRevertError  # noqa: PLC0415
        globals()["ContractClient"] = ContractClient
        globals()["TransactionRevertError"] = TransactionRevertError
        return globals()[name]
    if name in ("build_intent", "sign_intent"):
        from proof_of_intent import build_intent, sign_intent  # noqa: PLC0415
        globals()["build_intent"] = build_intent
        globals()["sign_intent"] = sign_intent
        return globals()[name]
    if name == "axl_client":
        from . import axl_client as _axl  # noqa: PLC0415
        globals()["axl_client"] = _axl
        return _axl
    raise AttributeError(f"module 'utils' has no attribute {name!r}")
