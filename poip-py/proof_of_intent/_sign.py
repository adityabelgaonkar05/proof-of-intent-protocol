"""EIP-712 intent signing — no dependency on the main pipeline config."""
from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import Web3

from ._defaults import DEFAULT_CHAIN_ID, DEFAULT_INTENT_REGISTRY

_INTENT_TYPES = {
    "Intent": [
        {"name": "owner",                  "type": "address"},
        {"name": "authorizedOrchestrator", "type": "address"},
        {"name": "tokenIn",                "type": "address"},
        {"name": "maxAmountIn",            "type": "uint256"},
        {"name": "minAmountOut",           "type": "uint256"},
        {"name": "allowedProtocols",       "type": "bytes32[]"},
        {"name": "deadline",               "type": "uint256"},
        {"name": "nonce",                  "type": "uint256"},
    ]
}


def sign_intent(
    intent: dict,
    private_key: str,
    *,
    chain_id: int = DEFAULT_CHAIN_ID,
    intent_registry: str = DEFAULT_INTENT_REGISTRY,
) -> str:
    """EIP-712 sign *intent* with *private_key*. Returns a 0x-prefixed hex signature."""
    domain = {
        "name": "IntentRegistry",
        "version": "1",
        "chainId": chain_id,
        "verifyingContract": intent_registry,
    }
    signed = Account.sign_typed_data(
        private_key,
        domain_data=domain,
        message_types=_INTENT_TYPES,
        message_data=intent,
    )
    return "0x" + signed.signature.hex()


def build_intent(
    *,
    owner: str,
    authorized_orchestrator: str,
    token_in: str,
    max_amount_in: int,
    min_amount_out: int,
    allowed_protocols: list[str],
    deadline: int,
    nonce: int,
) -> dict:
    """Build an intent dict with protocol names hashed to bytes32 automatically."""
    return {
        "owner":                  Web3.to_checksum_address(owner),
        "authorizedOrchestrator": Web3.to_checksum_address(authorized_orchestrator),
        "tokenIn":                Web3.to_checksum_address(token_in),
        "maxAmountIn":            max_amount_in,
        "minAmountOut":           min_amount_out,
        "allowedProtocols":       [Web3.keccak(text=p) for p in allowed_protocols],
        "deadline":               deadline,
        "nonce":                  nonce,
    }
