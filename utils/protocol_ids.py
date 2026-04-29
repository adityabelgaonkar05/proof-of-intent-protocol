from web3 import Web3

UNISWAP_V3 = Web3.keccak(text="Uniswap-V3")
CURVE = Web3.keccak(text="Curve")

PROTOCOL_NAMES = {
    UNISWAP_V3: "Uniswap-V3",
    CURVE: "Curve",
}

ALL_PROTOCOLS = [UNISWAP_V3, CURVE]


def name(protocol_bytes: bytes) -> str:
    return PROTOCOL_NAMES.get(protocol_bytes, "Unknown")
