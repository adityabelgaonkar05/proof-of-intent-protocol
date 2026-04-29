"""
Compiler agent — converts a natural-language swap request into a validated
Intent struct dict ready to be signed and registered on-chain.

Claude is used to parse the user's request and fill in any gaps with safe
defaults.  The output is deterministic enough that downstream agents can rely
on it without re-parsing.
"""

import json
import time
from typing import Any

import anthropic

from config.config import CLAUDE_API_KEY, KNOWN_PROTOCOLS

_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

_SYSTEM = """
You are an intent compiler for a DeFi protocol running on Base Sepolia testnet.
Your job is to parse a user's natural-language swap request and return a JSON
object with the following fields:

{
  "tokenIn":        "<ERC-20 address or well-known symbol>",
  "maxAmountIn":    <integer, amount in wei>,
  "minAmountOut":   <integer, minimum acceptable out amount in wei>,
  "allowedProtocols": ["<protocol name 1>", ...],   // subset of the known list
  "deadlineMinutes": <integer, minutes from now>
}

Rules:
- If the user specifies a token by symbol (USDC, ETH, WETH, etc.) return
  the symbol as-is; the caller will resolve the address.
- If minAmountOut is not specified, default to 97% of maxAmountIn (i.e.
  maxAmountIn * 0.97, expressed in the same units).
- If no protocols are mentioned, include all known protocols.
- If no deadline is mentioned, default to 30 minutes.
- Known protocols: uniswap-v3, curve, balancer-v2, aave-v3, 1inch
- Respond ONLY with the JSON object — no explanation, no markdown.
""".strip()

# Testnet token addresses (Base Sepolia)
_TOKEN_ADDRESSES: dict[str, str] = {
    "ETH":  "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
    "WETH": "0x4200000000000000000000000000000000000006",
    "USDC": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    "DAI":  "0x7683022d84f726a96c4a6611cd31dbf5409c0ac9",
}


def compile_intent(user_request: str, owner_address: str, current_nonce: int) -> dict[str, Any]:
    """
    Parse user_request and return a fully-populated intent dict.
    owner_address and current_nonce are injected by the caller.
    Raises ValueError if Claude cannot parse the request.
    """
    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_request}],
    )

    raw = response.content[0].text.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Compiler agent returned invalid JSON: {raw!r}") from exc

    # Resolve token symbol → address
    token_in = parsed["tokenIn"]
    if not token_in.startswith("0x"):
        token_in = _TOKEN_ADDRESSES.get(token_in.upper(), token_in)

    # Map protocol names → keccak256 hex identifiers
    protocol_names: list[str] = parsed.get("allowedProtocols", list(KNOWN_PROTOCOLS.keys()))
    allowed_protocols = [
        KNOWN_PROTOCOLS[name]
        for name in protocol_names
        if name in KNOWN_PROTOCOLS
    ]
    if not allowed_protocols:
        allowed_protocols = list(KNOWN_PROTOCOLS.values())

    max_amount_in: int = int(parsed["maxAmountIn"])
    min_amount_out: int = int(parsed.get("minAmountOut", max_amount_in * 97 // 100))
    deadline_minutes: int = int(parsed.get("deadlineMinutes", 30))
    deadline: int = int(time.time()) + deadline_minutes * 60

    return {
        "owner": owner_address,
        "tokenIn": token_in,
        "maxAmountIn": max_amount_in,
        "minAmountOut": min_amount_out,
        "allowedProtocols": allowed_protocols,
        "deadline": deadline,
        "nonce": current_nonce,
    }
