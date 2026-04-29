import os
from dotenv import load_dotenv

load_dotenv()

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
RPC_URL = os.getenv("RPC_URL", "https://sepolia.base.org")
CHAIN_ID = int(os.getenv("CHAIN_ID", "84532"))  # Base Sepolia

DEPLOYER_PRIVATE_KEY = os.getenv("DEPLOYER_PRIVATE_KEY", "")
USER_PRIVATE_KEY = os.getenv("USER_PRIVATE_KEY", "")

INTENT_REGISTRY_ADDRESS = os.getenv("INTENT_REGISTRY_ADDRESS", "")
DELEGATION_REGISTRY_ADDRESS = os.getenv("DELEGATION_REGISTRY_ADDRESS", "")
EXECUTION_GATE_ADDRESS = os.getenv("EXECUTION_GATE_ADDRESS", "")

# ---------------------------------------------------------------------------
# Contract ABIs (minimal — only the functions the Python layer needs)
# ---------------------------------------------------------------------------

INTENT_REGISTRY_ABI = [
    {
        "name": "registerIntent",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {
                "name": "intent",
                "type": "tuple",
                "components": [
                    {"name": "owner", "type": "address"},
                    {"name": "tokenIn", "type": "address"},
                    {"name": "maxAmountIn", "type": "uint256"},
                    {"name": "minAmountOut", "type": "uint256"},
                    {"name": "allowedProtocols", "type": "bytes32[]"},
                    {"name": "deadline", "type": "uint256"},
                    {"name": "nonce", "type": "uint256"},
                ],
            },
            {"name": "signature", "type": "bytes"},
        ],
        "outputs": [{"name": "intentId", "type": "bytes32"}],
    },
    {
        "name": "getIntent",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "intentId", "type": "bytes32"}],
        "outputs": [
            {
                "name": "",
                "type": "tuple",
                "components": [
                    {"name": "owner", "type": "address"},
                    {"name": "tokenIn", "type": "address"},
                    {"name": "maxAmountIn", "type": "uint256"},
                    {"name": "minAmountOut", "type": "uint256"},
                    {"name": "allowedProtocols", "type": "bytes32[]"},
                    {"name": "deadline", "type": "uint256"},
                    {"name": "nonce", "type": "uint256"},
                ],
            }
        ],
    },
    {
        "name": "nonces",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "DOMAIN_SEPARATOR",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "bytes32"}],
    },
    {
        "name": "IntentRegistered",
        "type": "event",
        "inputs": [
            {"name": "intentId", "type": "bytes32", "indexed": True},
            {"name": "owner", "type": "address", "indexed": True},
            {"name": "maxAmountIn", "type": "uint256", "indexed": False},
            {"name": "deadline", "type": "uint256", "indexed": False},
        ],
    },
]

DELEGATION_REGISTRY_ABI = [
    {
        "name": "delegateFromRoot",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "rootIntentId", "type": "bytes32"},
            {
                "name": "childScope",
                "type": "tuple",
                "components": [
                    {"name": "maxAmountIn", "type": "uint256"},
                    {"name": "minAmountOut", "type": "uint256"},
                    {"name": "allowedProtocols", "type": "bytes32[]"},
                    {"name": "deadline", "type": "uint256"},
                ],
            },
            {"name": "delegateTo", "type": "address"},
        ],
        "outputs": [{"name": "delegationId", "type": "bytes32"}],
    },
    {
        "name": "delegateFromDelegation",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "parentDelegationId", "type": "bytes32"},
            {
                "name": "childScope",
                "type": "tuple",
                "components": [
                    {"name": "maxAmountIn", "type": "uint256"},
                    {"name": "minAmountOut", "type": "uint256"},
                    {"name": "allowedProtocols", "type": "bytes32[]"},
                    {"name": "deadline", "type": "uint256"},
                ],
            },
            {"name": "delegateTo", "type": "address"},
        ],
        "outputs": [{"name": "delegationId", "type": "bytes32"}],
    },
    {
        "name": "getDelegation",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "delegationId", "type": "bytes32"}],
        "outputs": [
            {
                "name": "",
                "type": "tuple",
                "components": [
                    {"name": "parentId", "type": "bytes32"},
                    {"name": "isRootIntent", "type": "bool"},
                    {
                        "name": "scope",
                        "type": "tuple",
                        "components": [
                            {"name": "maxAmountIn", "type": "uint256"},
                            {"name": "minAmountOut", "type": "uint256"},
                            {"name": "allowedProtocols", "type": "bytes32[]"},
                            {"name": "deadline", "type": "uint256"},
                        ],
                    },
                    {"name": "delegatedTo", "type": "address"},
                    {"name": "executed", "type": "bool"},
                ],
            }
        ],
    },
    {
        "name": "delegationExists",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "DelegationCreated",
        "type": "event",
        "inputs": [
            {"name": "delegationId", "type": "bytes32", "indexed": True},
            {"name": "parentId", "type": "bytes32", "indexed": True},
            {"name": "delegatedTo", "type": "address", "indexed": True},
        ],
    },
]

EXECUTION_GATE_ABI = [
    {
        "name": "executeIntent",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "delegationId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "IntentExecuted",
        "type": "event",
        "inputs": [
            {"name": "delegationId", "type": "bytes32", "indexed": True},
            {"name": "executor", "type": "address", "indexed": True},
            {"name": "timestamp", "type": "uint256", "indexed": False},
        ],
    },
]

# Known protocol identifiers (keccak256 of protocol name)
KNOWN_PROTOCOLS: dict[str, str] = {
    "uniswap-v3": "0x" + bytes.fromhex(
        "1b3e4f5c6d7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c"
    ).hex(),  # placeholder — real value computed at import time below
}

# Compute proper keccak256 identifiers at import time
from web3 import Web3

KNOWN_PROTOCOLS = {
    name: Web3.keccak(text=name).hex()
    for name in ["uniswap-v3", "curve", "balancer-v2", "aave-v3", "1inch"]
}
