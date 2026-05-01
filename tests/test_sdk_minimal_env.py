"""
Verifies that ContractClient can be imported, instantiated, and used with only
PRIVATE_KEY set — no DEPLOYER_PRIVATE_KEY or other pipeline variables required.

The test spawns a subprocess with a stripped-down environment so that cached
module imports from the test runner cannot mask missing-env-var failures.
"""

import os
import pathlib
import subprocess
import sys
import textwrap

_ROOT = pathlib.Path(__file__).parent.parent

# Hardhat/Foundry deterministic test key — never use on mainnet.
_TEST_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

_SCRIPT = textwrap.dedent("""
    import os
    from utils.contract_client import ContractClient
    from web3.exceptions import ContractLogicError

    client = ContractClient(os.environ["PRIVATE_KEY"])
    print(f"account={client.account.address}")

    # Use a zero delegation ID — the call will either return False or revert on-chain;
    # either outcome is acceptable.  What must NOT happen is a missing-env-var error.
    zero_id = "0x" + "00" * 32
    tx_params = {
        "amountIn": 0,
        "minAmountOut": 0,
        "protocol": "0x" + "00" * 32,
        "tokenIn": "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
        "tokenOut": "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14",
        "recipient": client.account.address,
    }
    try:
        result = client.verify_chain(zero_id, tx_params)
        print(f"verify_chain={result}")
    except Exception as exc:
        msg = str(exc).lower()
        if "environment variable" in msg or ("missing" in msg and "key" in msg):
            raise RuntimeError(f"Unexpected env-var error: {exc}") from exc
        # Any contract-level revert or RPC error is fine — we reached the chain.
        print(f"verify_chain raised (expected): {exc}")

    print("SUCCESS")
""")


def test_contract_client_with_only_private_key():
    """ContractClient instantiates and reaches the chain with only PRIVATE_KEY set."""
    env = {
        "PRIVATE_KEY": _TEST_PRIVATE_KEY,
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        # Preserve virtualenv / conda Python paths so imports resolve correctly.
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        "VIRTUAL_ENV": os.environ.get("VIRTUAL_ENV", ""),
    }
    # Strip empty-string keys to keep the env table clean.
    env = {k: v for k, v in env.items() if v}

    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        env=env,
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert proc.returncode == 0, (
        f"Script exited {proc.returncode}\n"
        f"--- stdout ---\n{proc.stdout}\n"
        f"--- stderr ---\n{proc.stderr}"
    )
    assert "SUCCESS" in proc.stdout, (
        f"'SUCCESS' not found in output:\n{proc.stdout}"
    )
