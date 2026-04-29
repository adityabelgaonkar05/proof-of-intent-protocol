"""
EIP-712 signing for IntentRegistry.

The contract encodes the allowedProtocols array as:
    keccak256(abi.encodePacked(bytes32[]))
which equals keccak256(concat of raw 32-byte values) — matched here manually
so the Python digest is byte-for-byte identical to what the contract verifies.
"""

from eth_abi import encode
from eth_account import Account
from web3 import Web3

INTENT_TYPEHASH: bytes = Web3.keccak(
    text=(
        "Intent(address owner,address tokenIn,uint256 maxAmountIn,"
        "uint256 minAmountOut,bytes32[] allowedProtocols,uint256 deadline,uint256 nonce)"
    )
)


def _protocols_hash(protocols: list[str]) -> bytes:
    """keccak256(abi.encodePacked(bytes32[])) — matches the contract encoding."""
    raw = b"".join(
        bytes.fromhex(p[2:] if p.startswith("0x") else p) for p in protocols
    )
    return bytes(Web3.keccak(raw))


def build_intent_digest(intent: dict, domain_separator: bytes) -> bytes:
    """
    Compute the EIP-712 digest for an Intent struct.

    intent keys: owner, tokenIn, maxAmountIn, minAmountOut,
                 allowedProtocols (list of hex strings), deadline, nonce
    domain_separator: raw 32 bytes from IntentRegistry.DOMAIN_SEPARATOR()
    """
    protocols_hash = _protocols_hash(intent["allowedProtocols"])

    struct_hash: bytes = Web3.keccak(
        encode(
            ["bytes32", "address", "address", "uint256", "uint256", "bytes32", "uint256", "uint256"],
            [
                INTENT_TYPEHASH,
                intent["owner"],
                intent["tokenIn"],
                intent["maxAmountIn"],
                intent["minAmountOut"],
                protocols_hash,
                intent["deadline"],
                intent["nonce"],
            ],
        )
    )

    return bytes(Web3.keccak(b"\x19\x01" + domain_separator + struct_hash))


def sign_intent(intent: dict, private_key: str, domain_separator_hex: str) -> str:
    """
    Sign an intent and return the 65-byte signature as a 0x-prefixed hex string.

    domain_separator_hex: hex string returned by IntentRegistry.DOMAIN_SEPARATOR()
    """
    domain_separator = bytes.fromhex(
        domain_separator_hex[2:] if domain_separator_hex.startswith("0x") else domain_separator_hex
    )
    digest = build_intent_digest(intent, domain_separator)
    signed = Account.sign_hash(digest, private_key=private_key)
    return "0x" + signed.signature.hex()


def recover_signer(intent: dict, signature_hex: str, domain_separator_hex: str) -> str:
    """Return the address that produced signature_hex for the given intent."""
    domain_separator = bytes.fromhex(
        domain_separator_hex[2:] if domain_separator_hex.startswith("0x") else domain_separator_hex
    )
    digest = build_intent_digest(intent, domain_separator)
    return Account._recover_hash(digest, signature=signature_hex)
