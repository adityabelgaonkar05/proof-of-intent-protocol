import json
import os
import pathlib

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
# Addresses and ABIs loaded from Forge build artifacts / deployed.json
# ---------------------------------------------------------------------------

_ROOT = pathlib.Path(__file__).parent.parent
_DEPLOYED_JSON = _ROOT / "config" / "deployed.json"
_FORGE_OUT = _ROOT / "contracts" / "out"


def _load_deployed() -> dict:
    if _DEPLOYED_JSON.exists():
        return json.loads(_DEPLOYED_JSON.read_text())
    return {}


def _load_abi(contract_name: str) -> list:
    artifact = _FORGE_OUT / f"{contract_name}.sol" / f"{contract_name}.json"
    if artifact.exists():
        return json.loads(artifact.read_text())["abi"]
    return []


_deployed = _load_deployed()

AGENT_REGISTRY_ADDRESS: str = _deployed.get("agentRegistry", "")
AGENT_REGISTRY_ABI: list = _load_abi("AgentRegistry")

# ---------------------------------------------------------------------------
# Contract ABIs (minimal — only the functions the Python layer needs)
# ---------------------------------------------------------------------------

_INTENT_COMPONENTS = [
    {"name": "owner",                   "type": "address"},
    {"name": "authorizedOrchestrator",  "type": "address"},
    {"name": "tokenIn",                 "type": "address"},
    {"name": "maxAmountIn",             "type": "uint256"},
    {"name": "minAmountOut",            "type": "uint256"},
    {"name": "allowedProtocols",        "type": "bytes32[]"},
    {"name": "deadline",                "type": "uint256"},
    {"name": "nonce",                   "type": "uint256"},
]

INTENT_REGISTRY_ABI = [
    {
        "name": "registerIntent",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "intent", "type": "tuple", "components": _INTENT_COMPONENTS},
            {"name": "signature", "type": "bytes"},
        ],
        "outputs": [{"name": "intentId", "type": "bytes32"}],
    },
    {
        "name": "revokeIntent",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "intentId", "type": "bytes32"}],
        "outputs": [],
    },
    {
        "name": "getIntent",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "intentId", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "tuple", "components": _INTENT_COMPONENTS}],
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
            {"name": "intentId",               "type": "bytes32", "indexed": True},
            {"name": "owner",                  "type": "address", "indexed": True},
            {"name": "authorizedOrchestrator", "type": "address", "indexed": False},
            {"name": "maxAmountIn",            "type": "uint256", "indexed": False},
            {"name": "deadline",               "type": "uint256", "indexed": False},
        ],
    },
    {
        "name": "IntentRevoked",
        "type": "event",
        "inputs": [
            {"name": "intentId", "type": "bytes32", "indexed": True},
            {"name": "owner",    "type": "address", "indexed": True},
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
                    {"name": "maxAmountIn",      "type": "uint256"},
                    {"name": "minAmountOut",     "type": "uint256"},
                    {"name": "allowedProtocols", "type": "bytes32[]"},
                    {"name": "deadline",         "type": "uint256"},
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
                    {"name": "maxAmountIn",      "type": "uint256"},
                    {"name": "minAmountOut",     "type": "uint256"},
                    {"name": "allowedProtocols", "type": "bytes32[]"},
                    {"name": "deadline",         "type": "uint256"},
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
                    {"name": "parentId",    "type": "bytes32"},
                    {"name": "isRootIntent", "type": "bool"},
                    {
                        "name": "scope",
                        "type": "tuple",
                        "components": [
                            {"name": "maxAmountIn",      "type": "uint256"},
                            {"name": "minAmountOut",     "type": "uint256"},
                            {"name": "allowedProtocols", "type": "bytes32[]"},
                            {"name": "deadline",         "type": "uint256"},
                        ],
                    },
                    {"name": "delegatedTo", "type": "address"},
                    {"name": "executed",    "type": "bool"},
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
            {"name": "parentId",     "type": "bytes32", "indexed": True},
            {"name": "delegatedTo",  "type": "address", "indexed": True},
        ],
    },
]

_TX_PARAMS_COMPONENTS = [
    {"name": "amountIn",     "type": "uint256"},
    {"name": "minAmountOut", "type": "uint256"},
    {"name": "protocol",     "type": "bytes32"},
    {"name": "tokenIn",      "type": "address"},
    {"name": "tokenOut",     "type": "address"},
    {"name": "recipient",    "type": "address"},
]

EXECUTION_GATE_ABI = [
    {
        "name": "verifyChain",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "delegationId", "type": "bytes32"},
            {"name": "params", "type": "tuple", "components": _TX_PARAMS_COMPONENTS},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "executeSwap",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "delegationId", "type": "bytes32"},
            {"name": "params", "type": "tuple", "components": _TX_PARAMS_COMPONENTS},
        ],
        "outputs": [],
    },
    {
        "name": "SwapExecuted",
        "type": "event",
        "inputs": [
            {"name": "delegationId", "type": "bytes32", "indexed": True},
            {"name": "amountIn",     "type": "uint256", "indexed": False},
            {"name": "recipient",    "type": "address", "indexed": False},
        ],
    },
    {
        "name": "ChainVerificationFailed",
        "type": "event",
        "inputs": [
            {"name": "delegationId", "type": "bytes32", "indexed": True},
            {"name": "reason",       "type": "string",  "indexed": False},
        ],
    },
]

# Known protocol identifiers (keccak256 of protocol name)
from web3 import Web3

KNOWN_PROTOCOLS: dict[str, str] = {
    name: Web3.keccak(text=name).hex()
    for name in ["uniswap-v3", "curve", "balancer-v2", "aave-v3", "1inch"]
}
