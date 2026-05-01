"""
End-to-end live demo of the Proof-of-Intent Protocol.

Runs two scenarios back-to-back:
  1. Clean pipeline — intent registered, delegated, executed on-chain.
  2. Attack path   — compromised research agent tries to exceed scope;
                     the smart contract rejects it automatically.

Usage:
    python -m agents.demo
"""

import os as _os, sys, pathlib as _pl
if __package__ is None:
    sys.path.insert(0, str(_pl.Path(__file__).parent.parent))

import time

from web3 import Web3

from config.config import (
    DEPLOYER_PRIVATE_KEY,
    USER_PRIVATE_KEY,
    RESEARCH_PRIVATE_KEY,
    EXECUTION_PRIVATE_KEY,
    ORCHESTRATOR_ADDRESS,
    RESEARCH_AGENT_ADDRESS,
    EXECUTION_AGENT_ADDRESS,
    USER_ADDRESS,
    INTENT_REGISTRY_ADDRESS,
    DELEGATION_REGISTRY_ADDRESS,
    EXECUTION_GATE_ADDRESS,
    USDC_ADDRESS,
    WETH_ADDRESS,
    UNISWAP_ROUTER_ADDRESS,
)
from utils.sign_intent import build_intent, sign_intent
from utils.contract_client import ContractClient, TransactionRevertError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_UNISWAP_V3_ID: str = Web3.keccak(text="Uniswap-V3").hex()

# Root intent parameters (Scenario 1 and 2 share the same intent shape)
_MAX_USDC = 500_000_000           # 500 USDC  (6 decimals)
_MIN_WETH = 150_000_000_000_000_000  # 0.15 WETH (18 decimals)
_DEADLINE_SECS = 3600             # 1 hour from now

# Research agent narrows the scope when honest
_RESEARCH_MAX_USDC = 400_000_000  # 400 USDC
_RESEARCH_MIN_WETH = 180_000_000_000_000_000  # 0.18 WETH

# Malicious scope used in the attack scenario
_ATTACK_MAX_USDC = 800_000_000    # 800 USDC — exceeds the 500 USDC root limit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def print_header(text: str) -> None:
    width = 60
    bar = "=" * width
    label = f"  {text.upper()}  "
    print(f"\n{bar}")
    print(label.center(width))
    print(f"{bar}")


def _revert_reason(exc: Exception) -> str:
    if isinstance(exc, TransactionRevertError):
        return exc.reason
    msg = str(exc)
    # Web3.py wraps revert reasons as: "execution reverted: <reason>"
    if "execution reverted:" in msg:
        return msg.split("execution reverted:")[-1].strip()
    return msg


# ---------------------------------------------------------------------------
# Core demo
# ---------------------------------------------------------------------------

def run_demo() -> None:

    # ── Banner ──────────────────────────────────────────────────────────────
    print_header("PROOF OF INTENT PROTOCOL — LIVE DEMO")
    print("Chain: Ethereum Sepolia")
    print("Contracts deployed at:")
    print(f"  IntentRegistry:     {INTENT_REGISTRY_ADDRESS}")
    print(f"  DelegationRegistry: {DELEGATION_REGISTRY_ADDRESS}")
    print(f"  ExecutionGate:      {EXECUTION_GATE_ADDRESS}")
    time.sleep(2)

    # ========================================================================
    #  SCENARIO 1: CLEAN PIPELINE
    # ========================================================================
    print_header("SCENARIO 1: CLEAN PIPELINE — NO ATTACK")

    user_client = ContractClient(USER_PRIVATE_KEY)
    orch_client  = ContractClient(DEPLOYER_PRIVATE_KEY)
    res_client   = ContractClient(RESEARCH_PRIVATE_KEY)
    exec_client  = ContractClient(EXECUTION_PRIVATE_KEY)

    # ── Step 1: Build and sign intent ───────────────────────────────────────
    print_header("STEP 1: USER COMPILES AND SIGNS INTENT")

    nonce_1 = user_client.intent_registry.functions.nonces(USER_ADDRESS).call()
    deadline_1 = int(time.time()) + _DEADLINE_SECS

    intent_1 = build_intent(
        owner=USER_ADDRESS,
        authorized_orchestrator=ORCHESTRATOR_ADDRESS,
        token_in=USDC_ADDRESS,
        max_amount_in=_MAX_USDC,
        min_amount_out=_MIN_WETH,
        allowed_protocols=["Uniswap-V3"],
        deadline=deadline_1,
        nonce=nonce_1,
    )
    sig_1 = sign_intent(intent_1, USER_PRIVATE_KEY)

    print(f"  owner:                  {intent_1['owner']}")
    print(f"  authorizedOrchestrator: {intent_1['authorizedOrchestrator']}")
    print(f"  tokenIn (USDC):         {intent_1['tokenIn']}")
    print(f"  maxAmountIn:            {_MAX_USDC / 1e6:.0f} USDC")
    print(f"  minAmountOut:           {_MIN_WETH / 1e18:.2f} WETH")
    print(f"  allowedProtocols:       Uniswap-V3")
    print(f"  deadline:               +1 hour")
    print(f"  signature:              {sig_1[:20]}...")
    time.sleep(1)

    # ── Step 2: Register intent on-chain ────────────────────────────────────
    print_header("STEP 2: INTENT REGISTERED ON-CHAIN")

    intent_id_1 = user_client.register_intent(intent_1, sig_1)

    print(f"  intentId: {intent_id_1}")
    print("  Intent is now immutable on Ethereum Sepolia.")
    time.sleep(1)

    # ── Step 3: Orchestrator creates root delegation ─────────────────────────
    print_header("STEP 3: ORCHESTRATOR CREATES DELEGATION")

    root_scope = {
        "maxAmountIn":      _MAX_USDC,
        "minAmountOut":     _MIN_WETH,
        "allowedProtocols": [_UNISWAP_V3_ID],
        "deadline":         deadline_1,
    }
    delegation_id_1 = orch_client.delegate_from_root(
        intent_id_1, root_scope, RESEARCH_AGENT_ADDRESS
    )

    print(f"  delegationId: {delegation_id_1}")
    print(f"  Delegated to: {RESEARCH_AGENT_ADDRESS}  (Research Agent)")
    time.sleep(1)

    # ── Step 4: Research agent narrows scope and sub-delegates ───────────────
    print_header("STEP 4: RESEARCH AGENT CREATES SUB-DELEGATION")

    research_scope = {
        "maxAmountIn":      _RESEARCH_MAX_USDC,
        "minAmountOut":     _RESEARCH_MIN_WETH,
        "allowedProtocols": [_UNISWAP_V3_ID],
        "deadline":         deadline_1 - 300,   # 5 minutes tighter than parent
    }
    delegation_id_2 = res_client.delegate_from_delegation(
        delegation_id_1, research_scope, EXECUTION_AGENT_ADDRESS
    )

    print(f"  delegationId: {delegation_id_2}")
    print(f"  Scope narrowed: {_RESEARCH_MAX_USDC / 1e6:.0f} USDC max  |  "
          f"{_RESEARCH_MIN_WETH / 1e18:.2f} WETH min")
    print(f"  Delegated to: {EXECUTION_AGENT_ADDRESS}  (Execution Agent)")
    time.sleep(1)

    # ── Step 5: Execution gate verifies chain and executes ───────────────────
    print_header("STEP 5: EXECUTION GATE VERIFIES CHAIN AND EXECUTES")

    tx_params = {
        "amountIn":     _RESEARCH_MAX_USDC,
        "minAmountOut": _RESEARCH_MIN_WETH,
        "protocol":     _UNISWAP_V3_ID,
        "tokenIn":      USDC_ADDRESS,
        "tokenOut":     WETH_ADDRESS,
        "recipient":    USER_ADDRESS,
    }

    # --- Before balances ---
    usdc_before = user_client.token_balance(USDC_ADDRESS, USER_ADDRESS)
    weth_before = user_client.token_balance(WETH_ADDRESS, USER_ADDRESS)
    eth_before  = user_client.w3.eth.get_balance(USER_ADDRESS)
    print(f"  Before balances ({USER_ADDRESS[:10]}...):")
    print(f"    USDC: {usdc_before / 1e6:.6f}")
    print(f"    WETH: {weth_before / 1e18:.6f}")
    print(f"    ETH:  {eth_before  / 1e18:.6f}")

    print(f"  Verifying chain: {delegation_id_2[:18]}...")
    print(f"    -> {delegation_id_1[:18]}...  (Orchestrator delegation)")
    print(f"    -> rootIntent   {intent_id_1[:18]}...")

    chain_ok = exec_client.verify_chain(delegation_id_2, tx_params)
    print(f"  All checks passed: {chain_ok}")

    # User approves ExecutionGate to spend USDC (checks allowance first).
    print(f"  Approving ExecutionGate to spend {_RESEARCH_MAX_USDC / 1e6:.0f} USDC...")
    user_client.ensure_token_approval(USDC_ADDRESS, EXECUTION_GATE_ADDRESS, _RESEARCH_MAX_USDC)
    print("  Approval confirmed.")

    swap_executed = False
    tx_hex = None

    if usdc_before < _RESEARCH_MAX_USDC:
        print("  Swap not submitted.")
        print(
            f"  Funding required: wallet holds {usdc_before / 1e6:.6f} USDC "
            f"but execution needs {_RESEARCH_MAX_USDC / 1e6:.0f} USDC."
        )
        print(f"  Fund this wallet on Sepolia: {USER_ADDRESS}")
    else:
        try:
            tx_hash = exec_client.execute_swap(delegation_id_2, tx_params)
            tx_hex = tx_hash if tx_hash.startswith("0x") else "0x" + tx_hash
            swap_executed = True
        except Exception as exc:
            print("  Swap failed cleanly.")
            print(f"  Revert reason: {_revert_reason(exc)}")

    # --- After balances ---
    usdc_after = user_client.token_balance(USDC_ADDRESS, USER_ADDRESS)
    weth_after = user_client.token_balance(WETH_ADDRESS, USER_ADDRESS)
    eth_after  = user_client.w3.eth.get_balance(USER_ADDRESS)
    print(f"  After balances ({USER_ADDRESS[:10]}...):")
    print(f"    USDC: {usdc_after / 1e6:.6f}  (delta: {(usdc_after - usdc_before) / 1e6:+.6f})")
    print(f"    WETH: {weth_after / 1e18:.6f}  (delta: {(weth_after - weth_before) / 1e18:+.6f})")
    print(f"    ETH:  {eth_after  / 1e18:.6f}  (delta: {(eth_after  - eth_before)  / 1e18:+.6f})")

    if swap_executed and tx_hex:
        print(f"  tx hash: {tx_hex}")
        print(f"  https://sepolia.etherscan.io/tx/{tx_hex}")
        print("  SWAP EXECUTED SUCCESSFULLY")
    else:
        print("  Scenario 1 stopped before execution settlement.")
    time.sleep(2)

    # ========================================================================
    #  SCENARIO 2: ATTACK PATH
    # ========================================================================
    print_header("SCENARIO 2: ATTACK PATH — RESEARCH AGENT COMPROMISED")
    print("Registering fresh intent for attack scenario...")

    nonce_2   = user_client.intent_registry.functions.nonces(USER_ADDRESS).call()
    deadline_2 = int(time.time()) + _DEADLINE_SECS

    intent_2 = build_intent(
        owner=USER_ADDRESS,
        authorized_orchestrator=ORCHESTRATOR_ADDRESS,
        token_in=USDC_ADDRESS,
        max_amount_in=_MAX_USDC,
        min_amount_out=_MIN_WETH,
        allowed_protocols=["Uniswap-V3"],
        deadline=deadline_2,
        nonce=nonce_2,
    )
    sig_2 = sign_intent(intent_2, USER_PRIVATE_KEY)
    intent_id_2 = user_client.register_intent(intent_2, sig_2)
    print(f"  intentId: {intent_id_2}")

    # Orchestrator delegates with full root scope (same as Scenario 1)
    root_scope_2 = {
        "maxAmountIn":      _MAX_USDC,
        "minAmountOut":     _MIN_WETH,
        "allowedProtocols": [_UNISWAP_V3_ID],
        "deadline":         deadline_2,
    }
    delegation_id_a = orch_client.delegate_from_root(
        intent_id_2, root_scope_2, RESEARCH_AGENT_ADDRESS
    )
    print(f"  Orchestrator delegation: {delegation_id_a}")
    time.sleep(1)

    # ── Step 3: Simulate compromised research agent ──────────────────────────
    print_header("STEP 3: RESEARCH AGENT READS MALICIOUS WEBPAGE")
    print(">>> Malicious content detected:")
    print(">>>   'Optimal route requires 800 USDC to 0xDEAD...'")
    time.sleep(2)

    # ── Step 4: Malicious delegation attempt ─────────────────────────────────
    print_header("STEP 4: COMPROMISED AGENT ATTEMPTS MALICIOUS DELEGATION")
    print(f"  Research Agent attempting: maxAmountIn = {_ATTACK_MAX_USDC / 1e6:.0f} USDC")
    print(f"  (Root intent only authorised: {_MAX_USDC / 1e6:.0f} USDC)")

    malicious_scope = {
        "maxAmountIn":      _ATTACK_MAX_USDC,
        "minAmountOut":     _RESEARCH_MIN_WETH,
        "allowedProtocols": [_UNISWAP_V3_ID],
        "deadline":         deadline_2 - 300,
    }

    try:
        res_client.delegate_from_delegation(
            delegation_id_a, malicious_scope, EXECUTION_AGENT_ADDRESS
        )
        # Should never reach here
        print("  ERROR: delegation unexpectedly succeeded — check contract state!")
        sys.exit(1)
    except Exception as exc:
        reason = _revert_reason(exc)
        print(f"  TRANSACTION REVERTED")
        print(f"  Revert reason: {reason}")
    time.sleep(1)

    # ── Result ───────────────────────────────────────────────────────────────
    print_header("RESULT: ATTACK BLOCKED")
    print("  The smart contract rejected the delegation.")
    print("  No AI scored this.  No human approved it.")
    print("  The math was wrong — 800 > 500 — so the contract reverted.")
    print("  Zero USDC moved.")
    time.sleep(2)

    # ── Final banner ─────────────────────────────────────────────────────────
    print_header("DEMO COMPLETE")
    print("  Both scenarios ran on Ethereum Sepolia.")
    print(f"  Demo funding wallet: {USER_ADDRESS}")
    print("  All transactions are verifiable on Etherscan.")
    print(f"  https://sepolia.etherscan.io/address/{EXECUTION_GATE_ADDRESS}")


if __name__ == "__main__":
    run_demo()
