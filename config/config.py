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


CLAUDE_API_KEY = _require("CLAUDE_API_KEY")
RPC_URL = os.getenv("RPC_URL", "https://sepolia.base.org")
DEPLOYER_PRIVATE_KEY = _require("DEPLOYER_PRIVATE_KEY")
USER_PRIVATE_KEY = _require("USER_PRIVATE_KEY")
CHAIN_ID = 84532  # Base Sepolia

# ---------------------------------------------------------------------------
# Agent Ethereum wallet addresses
# ---------------------------------------------------------------------------

RESEARCH_PRIVATE_KEY: str   = _require("RESEARCH_PRIVATE_KEY")
EXECUTION_PRIVATE_KEY: str  = _require("EXECUTION_PRIVATE_KEY")

from eth_account import Account as _Account  # noqa: E402

ORCHESTRATOR_ADDRESS: str    = _Account.from_key(DEPLOYER_PRIVATE_KEY).address
RESEARCH_AGENT_ADDRESS: str  = _Account.from_key(RESEARCH_PRIVATE_KEY).address
EXECUTION_AGENT_ADDRESS: str = _Account.from_key(EXECUTION_PRIVATE_KEY).address
USER_ADDRESS: str            = _Account.from_key(USER_PRIVATE_KEY).address

# Token addresses on Base Sepolia (override via env vars for other networks)
USDC_ADDRESS: str = os.getenv("USDC_ADDRESS", "0x036CbD53842c5426634e7929541eC2318f3dCF7e")
WETH_ADDRESS: str = os.getenv("WETH_ADDRESS", "0x4200000000000000000000000000000000000006")

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
# Protocol identifiers (keccak256 of protocol name)
# ---------------------------------------------------------------------------

from web3 import Web3  # noqa: E402

KNOWN_PROTOCOLS: dict[str, str] = {
    name: Web3.keccak(text=name).hex()
    for name in ["Uniswap-V3", "Curve", "Balancer-V2", "Aave-V3", "1inch"]
}

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
