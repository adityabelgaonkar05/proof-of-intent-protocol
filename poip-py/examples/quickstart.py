"""
Proof-of-Intent Protocol — Python SDK quickstart.

This example uses ONLY the proof_of_intent package.
No pipeline config (config/config.py) is needed.

Minimum requirements:
    PRIVATE_KEY=0x...   (in poip-py/.env or the environment)

Run from the poip-py directory:
    python examples/quickstart.py
"""
import os
import sys
import pathlib

# Load .env from the package root (poip-py/.env)
try:
    from dotenv import load_dotenv
    load_dotenv(pathlib.Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # python-dotenv optional; set PRIVATE_KEY in shell instead

from proof_of_intent import ContractClient, usdc, in_hours, UNISWAP_V3

USDC_ADDR = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"  # Sepolia USDC
WETH_ADDR = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"  # Sepolia WETH


def main() -> None:
    private_key = os.environ.get("PRIVATE_KEY")
    if not private_key:
        sys.exit(
            "PRIVATE_KEY is required.\n"
            "  cp .env.example .env   # then fill in your key\n"
            "  python examples/quickstart.py"
        )

    print("=" * 55)
    print("  Proof-of-Intent Protocol — Python SDK Quickstart")
    print("=" * 55)

    client = ContractClient(private_key=private_key)
    print(f"  Wallet : {client.account.address}")
    print(f"  Chain  : Ethereum Sepolia (11155111)")
    print()

    # ── Step 1: Register agent (idempotent) ──────────────────────────────────
    print("Step 1/5  Register agent")
    tx = client.register_agent(client.account.address, "QuickstartAgent")
    print(f"          {'tx: ' + tx if tx else 'Already registered — skipping.'}")
    print()

    # ── Step 2: Create intent ─────────────────────────────────────────────────
    print("Step 2/5  Create intent")
    intent_id = client.create_intent(
        token_in=USDC_ADDR,
        max_amount_in=usdc(100),
        min_amount_out=1,
        allowed_protocols=["Uniswap-V3"],
        deadline=in_hours(1),
    )
    print(f"          intentId: {intent_id}")
    print()

    # ── Step 3: Delegate ──────────────────────────────────────────────────────
    print("Step 3/5  Create delegation")
    scope = {
        "maxAmountIn":      usdc(100),
        "minAmountOut":     1,
        "allowedProtocols": [UNISWAP_V3.hex()],
        "deadline":         in_hours(1),
    }
    delegation_id = client.delegate_from_root(intent_id, scope, client.account.address)
    print(f"          delegationId: {delegation_id}")
    print()

    # ── Step 4: Verify chain (view call — no gas) ─────────────────────────────
    print("Step 4/5  Verify chain")
    tx_params = {
        "amountIn":     usdc(100),
        "minAmountOut": 1,
        "protocol":     UNISWAP_V3.hex(),
        "tokenIn":      USDC_ADDR,
        "tokenOut":     WETH_ADDR,
        "recipient":    client.account.address,
    }
    if not client.verify_chain(delegation_id, tx_params):
        sys.exit("FAIL — verifyChain returned false")
    print("          Chain verified ✓")
    print()

    # ── Step 5: Execute swap (requires Sepolia USDC) ──────────────────────────
    print("Step 5/5  Execute swap")
    balance = client.token_balance(USDC_ADDR, client.account.address)
    print(f"          USDC balance: {balance / 1e6:.2f} USDC")

    if balance < usdc(100):
        print()
        print(f"  Wallet {client.account.address} needs ≥ 100 Sepolia USDC.")
        print("  Get some at: https://faucet.circle.com")
        print()
        print("  Steps 1–4 completed on-chain. Re-run after funding to execute.")
        return

    client.ensure_token_approval(USDC_ADDR, client.execution_gate.address, usdc(100))
    tx_hash = client.execute_swap(delegation_id, tx_params)
    print(f"  Swap executed!")
    print(f"  tx: https://sepolia.etherscan.io/tx/{tx_hash}")
    weth_after = client.token_balance(WETH_ADDR, client.account.address)
    print(f"  WETH received: {weth_after / 1e18:.6f} WETH")


if __name__ == "__main__":
    main()
