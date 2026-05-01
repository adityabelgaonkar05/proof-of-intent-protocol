"""
Exception hierarchy for the proof-of-intent SDK.

from proof_of_intent.errors import POIPError, ScopeViolationError, DeadlineExpiredError
"""


class POIPError(Exception):
    """Base exception for all proof-of-intent SDK errors."""


class TransactionRevertError(POIPError):
    """A contract call reverted. `reason` contains the revert message."""
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class ScopeViolationError(TransactionRevertError):
    """Delegation would exceed the scope authorised by the root intent."""


class DeadlineExpiredError(TransactionRevertError):
    """The intent or delegation deadline has already passed."""


class ConnectionError(POIPError):  # noqa: A001 (shadows builtin intentionally)
    """Cannot connect to the configured RPC endpoint."""


# Mapping of on-chain revert strings to specific exception classes.
# Keys are substrings of the revert reason returned by the contract.
_REVERT_MAP: dict[str, type[TransactionRevertError]] = {
    "ScopeExceeded":     ScopeViolationError,
    "scope exceeded":    ScopeViolationError,
    "scope violation":   ScopeViolationError,
    "DeadlineExpired":   DeadlineExpiredError,
    "deadline expired":  DeadlineExpiredError,
    "Deadline":          DeadlineExpiredError,
}


def classify_revert(reason: str) -> TransactionRevertError:
    """Return the most specific TransactionRevertError subclass for *reason*."""
    lower = reason.lower()
    for fragment, cls in _REVERT_MAP.items():
        if fragment.lower() in lower:
            return cls(reason)
    return TransactionRevertError(reason)
