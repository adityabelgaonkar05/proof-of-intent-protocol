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
# Deployed contract addresses
# ---------------------------------------------------------------------------

_deployed: dict = json.loads((_ROOT / "config" / "deployed.json").read_text())

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


INTENT_REGISTRY_ABI = _load_abi("IntentRegistry")
DELEGATION_REGISTRY_ABI = _load_abi("DelegationRegistry")
EXECUTION_GATE_ABI = _load_abi("ExecutionGate")

# ---------------------------------------------------------------------------
# Protocol identifiers (keccak256 of protocol name)
# ---------------------------------------------------------------------------

from web3 import Web3  # noqa: E402

KNOWN_PROTOCOLS: dict[str, str] = {
    name: Web3.keccak(text=name).hex()
    for name in ["uniswap-v3", "curve", "balancer-v2", "aave-v3", "1inch"]
}
