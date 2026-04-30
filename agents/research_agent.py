"""
Research agent — uses Claude to reason about on-chain protocol conditions and
recommend the narrowest valid execution scope for a given intent.

On Base Sepolia no live DEX price APIs exist, so the agent uses Claude's
reasoning ability together with simulated liquidity data.  In production this
would be replaced with actual on-chain reads / API calls passed as tool results.
"""

import json
from typing import Any

import anthropic

from config.config import CLAUDE_API_KEY, KNOWN_PROTOCOLS

_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

# ---------------------------------------------------------------------------
# Simulated liquidity snapshot (replace with live API calls in production)
# ---------------------------------------------------------------------------

_SIMULATED_LIQUIDITY: dict[str, dict] = {
    "Uniswap-V3": {
        "available": True,
        "estimated_slippage_bps": 15,
        "depth_eth": 500,
    },
    "Curve": {
        "available": True,
        "estimated_slippage_bps": 8,
        "depth_eth": 300,
    },
    "Balancer-V2": {
        "available": True,
        "estimated_slippage_bps": 20,
        "depth_eth": 150,
    },
    "Aave-V3": {
        "available": False,
        "reason": "not a spot-swap venue",
    },
    "1inch": {
        "available": True,
        "estimated_slippage_bps": 10,
        "depth_eth": 1000,
    },
}

_SYSTEM = """
You are a DeFi research agent.  You are given:
1. An intent (token swap specification with constraints)
2. A liquidity snapshot for each allowed protocol

Your job is to recommend a NARROWED execution scope that:
- Picks only the protocols with the best liquidity and lowest slippage
- Reduces maxAmountIn to the minimum needed to satisfy the swap
- Raises minAmountOut to reflect realistic on-chain conditions
- Keeps the deadline to the minimum sensible window (no longer than the
  original, ideally shorter)

Respond with ONLY a JSON object with these fields:
{
  "recommendedProtocols": ["<protocol name>", ...],
  "suggestedMaxAmountIn":  <int, wei — must be <= original maxAmountIn>,
  "suggestedMinAmountOut": <int, wei — must be >= original minAmountOut>,
  "suggestedDeadlineMinutes": <int>,
  "rationale": "<one sentence>"
}
""".strip()


def research_best_scope(intent: dict[str, Any]) -> dict[str, Any]:
    """
    Given a compiled intent, return a narrowed Scope recommendation.

    Returns a dict with keys:
        recommendedProtocols, suggestedMaxAmountIn,
        suggestedMinAmountOut, suggestedDeadlineMinutes, rationale
    """
    # Resolve allowed protocol names from keccak ids
    reverse_map = {v: k for k, v in KNOWN_PROTOCOLS.items()}
    allowed_names = [
        reverse_map.get(pid, pid) for pid in intent.get("allowedProtocols", [])
    ]

    # Build liquidity snapshot restricted to allowed protocols
    snapshot = {
        name: _SIMULATED_LIQUIDITY.get(name, {"available": False, "reason": "unknown"})
        for name in allowed_names
    }

    import time
    remaining_seconds = intent["deadline"] - int(time.time())

    user_message = json.dumps(
        {
            "intent": {
                "maxAmountIn_wei": intent["maxAmountIn"],
                "minAmountOut_wei": intent["minAmountOut"],
                "allowedProtocols": allowed_names,
                "deadlineRemainingSeconds": max(remaining_seconds, 0),
            },
            "liquiditySnapshot": snapshot,
        },
        indent=2,
    )

    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Research agent returned invalid JSON: {raw!r}") from exc

    # Map protocol names back to keccak hex ids
    result["recommendedProtocolIds"] = [
        KNOWN_PROTOCOLS[name]
        for name in result.get("recommendedProtocols", [])
        if name in KNOWN_PROTOCOLS
    ]

    return result
