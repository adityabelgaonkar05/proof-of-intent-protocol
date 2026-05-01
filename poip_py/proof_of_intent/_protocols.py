"""Protocol ID constants — keccak256 of each protocol name."""
from web3 import Web3

UNISWAP_V3  = Web3.keccak(text="Uniswap-V3")
CURVE       = Web3.keccak(text="Curve")
BALANCER_V2 = Web3.keccak(text="Balancer-V2")
AAVE_V3     = Web3.keccak(text="Aave-V3")
ONEINCH     = Web3.keccak(text="1inch")

ALL_PROTOCOLS = [UNISWAP_V3, CURVE, BALANCER_V2, AAVE_V3, ONEINCH]

PROTOCOL_NAMES: dict[bytes, str] = {
    UNISWAP_V3:  "Uniswap-V3",
    CURVE:       "Curve",
    BALANCER_V2: "Balancer-V2",
    AAVE_V3:     "Aave-V3",
    ONEINCH:     "1inch",
}


def protocol_name(hash_bytes: bytes) -> str:
    """Return the human-readable name for a protocol bytes32 hash."""
    return PROTOCOL_NAMES.get(hash_bytes, "Unknown")


def protocol_id(name: str) -> bytes:
    """Return the bytes32 keccak256 hash for a protocol name string."""
    return Web3.keccak(text=name)
