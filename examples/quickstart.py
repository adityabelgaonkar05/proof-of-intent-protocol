"""
Proof-of-Intent Protocol — Python quickstart.

Minimum .env requirements:
    DEPLOYER_PRIVATE_KEY=0x...

USER_PRIVATE_KEY is optional. When not set it defaults to DEPLOYER_PRIVATE_KEY,
meaning one wallet acts as user, orchestrator, and executor — no multi-agent
setup required.

RESEARCH_PRIVATE_KEY and EXECUTION_PRIVATE_KEY are not used here.

The script stops gracefully before executeSwap if the wallet does not hold
enough Sepolia USDC, prints the funding URL, and exits cleanly.

Run from the project root:
    python -m examples.quickstart
or:
    python examples/quickstart.py
"""
import sys
import os

# Support running as a script from the project root without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from utils import ContractClient, usdc, weth, in_minutes
from config.config import (
    require_pipeline_keys,
    DEPLOYER_PRIVATE_KEY,
    USER_PRIVATE_KEY,
    USER_ADDRESS,
    ORCHESTRATOR_ADDRESS,
    USDC_ADDRESS,
    WETH_ADDRESS,
    EXECUTION_GATE_ADDRESS,
    KNOWN_PROTOCOLS,
)


def main() -> None:
    require_pipeline_keys("DEPLOYER_PRIVATE_KEY")

    print("=" * 55)
    print("  Proof-of-Intent Protocol — Python Quickstart")
    print("=" * 55)
    print(f"  Wallet : {ORCHESTRATOR_ADDRESS}")
    print(f"  Chain  : Ethereum Sepolia (11155111)")
    print()

    # One ContractClient per signing key. In single-key mode both are the same.
    client      = ContractClient(DEPLOYER_PRIVATE_KEY)
    user_client = ContractClient(USER_PRIVATE_KEY)

    # ── Step 1: Register the agent (idempotent) ──────────────────────────────
    print("Step 1/5  Register agent")
    tx = client.register_agent(ORCHESTRATOR_ADDRESS, "QuickstartAgent")
    if tx is None:
        print("          Already registered — skipping.")
    else:
        print(f"          tx: {tx}")
    print()

    # ── Step 2: Create intent (build → sign → register in one call) ───────────
    print("Step 2/5  Create intent")
    # minAmountOut=1 is intentional for this demo — always set a real floor in production.
    intent_id = user_client.create_intent(
        token_in          = USDC_ADDRESS,
        max_amount_in     = usdc(100),        # 100 USDC
        min_amount_out    = 1,                # demo: accept any output
        allowed_protocols = ["Uniswap-V3"],
        deadline          = in_minutes(60),   # valid for 1 hour
        orchestrator      = ORCHESTRATOR_ADDRESS,
    )
    print(f"          intentId: {intent_id}")
    print()

    # ── Step 3: Create root delegation (orchestrator → itself) ────────────────
    print("Step 3/5  Create delegation")
    scope = ContractClient.build_scope(
        max_amount_in     = usdc(100),
        min_amount_out    = 1,
        allowed_protocols = ["Uniswap-V3"],
        deadline          = in_minutes(55),   # 5 min tighter than intent deadline
    )
    delegation_id = client.delegate_from_root(intent_id, scope, ORCHESTRATOR_ADDRESS)
    print(f"          delegationId: {delegation_id}")
    print()

    # ── Step 4: Verify the delegation chain (view call — no gas) ─────────────
    print("Step 4/5  Verify chain")
    tx_params = {
        "amountIn"    : usdc(100),
        "minAmountOut": 1,
        "protocol"    : KNOWN_PROTOCOLS["Uniswap-V3"],
        "tokenIn"     : USDC_ADDRESS,
        "tokenOut"    : WETH_ADDRESS,
        "recipient"   : USER_ADDRESS,
    }
    ok = client.verify_chain(delegation_id, tx_params)
    if not ok:
        print("          FAIL — verify_chain returned False")
        sys.exit(1)
    print(f"          Chain verified ✓")
    print()

    # ── Step 5: Execute swap (requires Sepolia USDC in USER_ADDRESS) ──────────
    print("Step 5/5  Execute swap")
    balance = user_client.token_balance(USDC_ADDRESS, USER_ADDRESS)
    print(f"          USDC balance: {balance / 1e6:.2f}")

    if balance < usdc(100):
        print()
        print(f"  Wallet {USER_ADDRESS} needs ≥ 100 Sepolia USDC.")
        print("  Get some at: https://faucet.circle.com")
        print()
        print("  Steps 1–4 already completed on-chain.")
        print("  Re-run after funding to execute the swap.")
        return

    user_client.ensure_token_approval(USDC_ADDRESS, EXECUTION_GATE_ADDRESS, usdc(100))
    print("          Approval confirmed.")

    tx_hash = client.execute_swap(delegation_id, tx_params)
    print()
    print("  ✓ Swap executed!")
    print(f"  tx: https://sepolia.etherscan.io/tx/{tx_hash}")

    weth_after = user_client.token_balance(WETH_ADDRESS, USER_ADDRESS)
    print(f"  WETH balance: {weth_after / 1e18:.6f}")


if __name__ == "__main__":
    main()
