"""
End-to-end demo of the Proof-of-Intent Protocol.

Usage:
    python -m agents.demo
    python -m agents.demo "Swap 0.1 ETH for at least 95% in USDC using Uniswap v3, deadline 20 minutes"

The demo runs the full orchestration pipeline:
  1. Compiler agent  — parse request → Intent struct
  2. Register intent — sign + broadcast to IntentRegistry
  3. Research agent  — find best narrowed scope
  4. Execution agent — delegate + call ExecutionGate
"""

import sys
import json
import textwrap

from agents.orchestrator import run


_DEFAULT_REQUEST = (
    "Swap 0.5 ETH worth of USDC for at least 0.47 ETH, "
    "using Uniswap v3 or Curve, deadline 30 minutes"
)

_BANNER = """
╔══════════════════════════════════════════════════════╗
║        Proof-of-Intent Protocol  —  Demo             ║
╚══════════════════════════════════════════════════════╝
"""


def _print_section(title: str, data: dict | str) -> None:
    print(f"\n{'─' * 54}")
    print(f"  {title}")
    print(f"{'─' * 54}")
    if isinstance(data, dict):
        print(textwrap.indent(json.dumps(data, indent=2, default=str), "  "))
    else:
        print(f"  {data}")


def main() -> None:
    print(_BANNER)

    request = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_REQUEST
    print(f"User request: {request!r}\n")

    state = run(request)

    _print_section("Compiled intent", state.get("intent", {}))
    _print_section("Registered intentId", state.get("intent_id", "—"))
    _print_section("Research recommendation", state.get("research", {}))
    _print_section("Execution result", state.get("execution_result", {}))

    result = state.get("execution_result", {})
    if result.get("success"):
        print("\n✓  Intent executed successfully on Base Sepolia")
        print(f"   delegation tx : {result.get('delegationTxHash')}")
        print(f"   execution tx  : {result.get('executionTxHash')}")
    else:
        print("\n✗  Execution did not complete")
        print(f"   error: {result.get('error', 'see above')}")


if __name__ == "__main__":
    main()
