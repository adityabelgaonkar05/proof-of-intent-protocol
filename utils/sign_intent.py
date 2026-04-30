import os as _os, sys as _sys
if __package__ is None:  # running as script, not as part of the package
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import Web3

from config.config import CHAIN_ID, INTENT_REGISTRY_ADDRESS

DOMAIN = {
    "name": "IntentRegistry",
    "version": "1",
    "chainId": CHAIN_ID,
    "verifyingContract": INTENT_REGISTRY_ADDRESS,
}

INTENT_TYPE = {
    "Intent": [
        {"name": "owner",                   "type": "address"},
        {"name": "authorizedOrchestrator",  "type": "address"},
        {"name": "tokenIn",                 "type": "address"},
        {"name": "maxAmountIn",             "type": "uint256"},
        {"name": "minAmountOut",            "type": "uint256"},
        {"name": "allowedProtocols",        "type": "bytes32[]"},
        {"name": "deadline",                "type": "uint256"},
        {"name": "nonce",                   "type": "uint256"},
    ]
}


def sign_intent(intent: dict, private_key: str) -> str:
    signed = Account.sign_typed_data(
        private_key,
        domain_data=DOMAIN,
        message_types=INTENT_TYPE,
        message_data=intent,
    )
    return "0x" + signed.signature.hex()


def build_intent(
    owner: str,
    authorized_orchestrator: str,
    token_in: str,
    max_amount_in: int,
    min_amount_out: int,
    allowed_protocols: list[str],
    deadline: int,
    nonce: int,
) -> dict:
    protocol_hashes = [Web3.keccak(text=name) for name in allowed_protocols]
    return {
        "owner": Web3.to_checksum_address(owner),
        "authorizedOrchestrator": Web3.to_checksum_address(authorized_orchestrator),
        "tokenIn": Web3.to_checksum_address(token_in),
        "maxAmountIn": max_amount_in,
        "minAmountOut": min_amount_out,
        "allowedProtocols": protocol_hashes,
        "deadline": deadline,
        "nonce": nonce,
    }


if __name__ == "__main__":
    import os
    import sys
    import time
    # Ensure project root is on sys.path when run as a script.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dotenv import load_dotenv

    load_dotenv()
    from config.config import USDC_ADDRESS

    private_key = os.environ["USER_PRIVATE_KEY"]
    owner = Account.from_key(private_key).address

    intent = build_intent(
        owner=owner,
        authorized_orchestrator=owner,  # use self as orchestrator for standalone test
        token_in=USDC_ADDRESS,
        max_amount_in=100 * 10**6,   # 100 USDC
        min_amount_out=99 * 10**18,  # 99 output tokens
        allowed_protocols=["Uniswap-V3"],
        deadline=int(time.time()) + 3600,
        nonce=0,
    )

    signature = sign_intent(intent, private_key)

    print("Intent:")
    for k, v in intent.items():
        print(f"  {k}: {v}")
    print(f"\nSignature: {signature}")
