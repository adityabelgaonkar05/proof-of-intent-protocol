"""
Hardcoded Sepolia defaults for the proof-of-intent SDK.
All values can be overridden via ContractClient constructor kwargs.
"""
import json
import pathlib

_ABI_DIR = pathlib.Path(__file__).parent / "_abis"

DEFAULT_RPC_URL = "https://ethereum-sepolia-rpc.publicnode.com"
DEFAULT_CHAIN_ID = 11155111

# Deployed contract addresses on Ethereum Sepolia
DEFAULT_AGENT_REGISTRY      = "0xcD5954121BbE13a4867c2Df886e24E924D006883"
DEFAULT_INTENT_REGISTRY     = "0xf2a52EAf8E2440F9aFa28aDA5426Bc2908DDc5b4"
DEFAULT_DELEGATION_REGISTRY = "0x51bF1E9C33ACF135E7C6ca83AD4Cf36d5B8BBa45"
DEFAULT_EXECUTION_GATE      = "0x076e8cd66be8B927CcB9adA63505e8027b209cb6"

# Well-known Sepolia token addresses
USDC_ADDRESS            = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
WETH_ADDRESS            = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"
UNISWAP_ROUTER_ADDRESS  = "0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E"

# ENS Sepolia addresses
ENS_RESOLVER_ADDRESS = "0x8FADE66B79cC9f707aB26799354482EB93a5B7dD"
ENS_REGISTRY_ADDRESS = "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e"


def _load_abi(name: str) -> list:
    return json.loads((_ABI_DIR / f"{name}.json").read_text())


AGENT_REGISTRY_ABI      = _load_abi("AgentRegistry")
INTENT_REGISTRY_ABI     = _load_abi("IntentRegistry")
DELEGATION_REGISTRY_ABI = _load_abi("DelegationRegistry")
EXECUTION_GATE_ABI      = _load_abi("ExecutionGate")
