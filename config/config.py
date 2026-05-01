import json
import os
import pathlib

from dotenv import load_dotenv

load_dotenv()

_ROOT = pathlib.Path(__file__).parent.parent


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Required environment variable '{name}' is missing or empty.")
    return value


USE_CLAUDE: bool = os.getenv("USE_CLAUDE", "true").strip().lower() != "false"

CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

RPC_URL = os.getenv("RPC_URL", "https://ethereum-sepolia-rpc.publicnode.com")
# DEPLOYER_PRIVATE_KEY is optional at import time so that SDK users who pass
# their key directly to ContractClient(key) can import this module without
# setting pipeline-specific variables.  The full pipeline (examples/quickstart,
# orchestrator) still requires it and will surface a clear error at runtime
# when it tries to derive ORCHESTRATOR_ADDRESS or USER_ADDRESS from an empty key.
DEPLOYER_PRIVATE_KEY: str = os.getenv("DEPLOYER_PRIVATE_KEY", "")
# USER_PRIVATE_KEY defaults to DEPLOYER_PRIVATE_KEY so a single-key setup works out of the box.
USER_PRIVATE_KEY: str = os.getenv("USER_PRIVATE_KEY") or DEPLOYER_PRIVATE_KEY
CHAIN_ID = int(os.getenv("CHAIN_ID", "11155111"))

# ---------------------------------------------------------------------------
# Agent Ethereum wallet addresses
# ---------------------------------------------------------------------------

# Multi-agent keys are optional. Leave unset when running single-key quickstart.
RESEARCH_PRIVATE_KEY: str  = os.getenv("RESEARCH_PRIVATE_KEY", "")
EXECUTION_PRIVATE_KEY: str = os.getenv("EXECUTION_PRIVATE_KEY", "")

from eth_account import Account as _Account  # noqa: E402

ORCHESTRATOR_ADDRESS: str    = _Account.from_key(DEPLOYER_PRIVATE_KEY).address if DEPLOYER_PRIVATE_KEY else ""
RESEARCH_AGENT_ADDRESS: str  = _Account.from_key(RESEARCH_PRIVATE_KEY).address if RESEARCH_PRIVATE_KEY else ""
EXECUTION_AGENT_ADDRESS: str = _Account.from_key(EXECUTION_PRIVATE_KEY).address if EXECUTION_PRIVATE_KEY else ""
USER_ADDRESS: str            = _Account.from_key(USER_PRIVATE_KEY).address if USER_PRIVATE_KEY else ""

# Token addresses on Ethereum Sepolia
USDC_ADDRESS: str = os.getenv("USDC_ADDRESS", "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238")
WETH_ADDRESS: str = os.getenv("WETH_ADDRESS", "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14")
UNISWAP_ROUTER_ADDRESS: str = os.getenv("UNISWAP_ROUTER_ADDRESS", "0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E")

# ---------------------------------------------------------------------------
# Deployed contract addresses
# ---------------------------------------------------------------------------

_deployed: dict = json.loads((_ROOT / "config" / "deployed.json").read_text())

AGENT_REGISTRY_ADDRESS: str = _deployed["agentRegistry"]
INTENT_REGISTRY_ADDRESS: str = _deployed["intentRegistry"]
DELEGATION_REGISTRY_ADDRESS: str = _deployed["delegationRegistry"]
EXECUTION_GATE_ADDRESS: str = _deployed["executionGate"]

# ---------------------------------------------------------------------------
# Contract ABIs (loaded from Foundry build artifacts)
# ---------------------------------------------------------------------------

_OUT = _ROOT / "contracts" / "out"


def _load_abi(contract_name: str) -> list:
    path = _OUT / f"{contract_name}.sol" / f"{contract_name}.json"
    return json.loads(path.read_text())["abi"]


AGENT_REGISTRY_ABI = _load_abi("AgentRegistry")
INTENT_REGISTRY_ABI = _load_abi("IntentRegistry")
DELEGATION_REGISTRY_ABI = _load_abi("DelegationRegistry")
EXECUTION_GATE_ABI = _load_abi("ExecutionGate")

# ---------------------------------------------------------------------------
# 0G Network — decentralised storage for intent NFTs
# ---------------------------------------------------------------------------

ZG_API_KEY: str = os.getenv("ZG_API_KEY", "").strip()
ZG_RPC_URL: str = os.getenv("ZG_RPC_URL", "https://evmrpc-testnet.0g.ai")
ZG_INDEXER_URL: str = os.getenv("ZG_INDEXER_URL", "https://indexer-storage-testnet-turbo.0g.ai")

# ---------------------------------------------------------------------------
# Protocol identifiers (keccak256 of protocol name)
# ---------------------------------------------------------------------------

from web3 import Web3  # noqa: E402

# KNOWN_PROTOCOLS is the single source of truth for protocol ID constants.
# utils/protocol_ids.py was removed — use KNOWN_PROTOCOLS or compute inline via
# Web3.keccak(text="<ProtocolName>") for one-off use.
KNOWN_PROTOCOLS: dict[str, str] = {
    name: Web3.keccak(text=name).hex()
    for name in ["Uniswap-V3", "Curve", "Balancer-V2", "Aave-V3", "1inch"]
}

# ---------------------------------------------------------------------------
# ENS text-record storage
# ---------------------------------------------------------------------------

ENS_NAME: str = os.getenv("ENS_NAME", "")
# Fallback resolver — used only if the ENS registry returns the zero address
# for the configured name (i.e. name registered with no explicit resolver).
# store_intent_on_ens() looks up the live resolver from the registry first.
ENS_RESOLVER_ADDRESS: str = "0x8FADE66B79cC9f707aB26799354482EB93a5B7dD"
ENS_REGISTRY_ADDRESS: str = "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e"

ENS_PUBLIC_RESOLVER_ABI: list = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "node", "type": "bytes32"},
            {"internalType": "string",  "name": "key",  "type": "string"},
            {"internalType": "string",  "name": "value","type": "string"},
        ],
        "name": "setText",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "node", "type": "bytes32"},
            {"internalType": "string",  "name": "key",  "type": "string"},
        ],
        "name": "text",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# ---------------------------------------------------------------------------
# AXL agent public keys (ed25519, hex). Captured from each node's
# /topology endpoint; the matching private keys live in agents/keys/.
# ---------------------------------------------------------------------------

ORCHESTRATOR_AXL_KEY = "f2395885c7d3f024bcf269e88cac9a072a977016365ae260118782c19240760b"
RESEARCH_AXL_KEY     = "7ab38976ea6550c626fc28382dd133c255054c5fe19ea4450ad0103771438a91"
EXECUTION_AXL_KEY    = "1f63933d14bf26298b076c1f69f25e323fc167b7133c233c6fb58f3410c29515"

# Local HTTP API ports for each node (see agents/axl_configs/*.json)
ORCHESTRATOR_AXL_PORT = 9002
RESEARCH_AXL_PORT     = 9012
EXECUTION_AXL_PORT    = 9022
