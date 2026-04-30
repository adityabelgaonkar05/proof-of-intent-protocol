"""
Orchestrator — top-level Claude agent that coordinates the full intent
lifecycle using tool use.

Flow:
  1. compile_intent   — parse the user's request into an Intent struct
  2. register_intent  — sign and broadcast to IntentRegistry
  3. research_scope   — find the best narrowed execution scope
  4. execute_intent   — delegate + call ExecutionGate

The orchestrator is itself a Claude agent: it reasons about the flow and
calls tools to advance it, so it can recover from partial failures and
explain decisions in natural language.
"""

import json
import time
from typing import Any

import anthropic
from eth_account import Account

from config.config import CLAUDE_API_KEY, USER_PRIVATE_KEY
from agents.compiler import compile_intent
from agents.research_agent import research_best_scope
from agents.execution_agent import execute as execution_agent_execute
from utils.contract_client import (
    get_web3,
    get_nonce,
    get_domain_separator,
    register_intent as client_register_intent,
    extract_intent_id_from_receipt,
)
from utils.sign_intent import sign_intent

_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

# ---------------------------------------------------------------------------
# Tool definitions exposed to the orchestrator Claude agent
# ---------------------------------------------------------------------------

_TOOLS: list[dict] = [
    {
        "name": "compile_intent",
        "description": (
            "Parse a natural-language swap request into a structured Intent. "
            "Returns the intent dict including allowedProtocols as keccak hex IDs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_request": {
                    "type": "string",
                    "description": "The user's swap request in natural language.",
                }
            },
            "required": ["user_request"],
        },
    },
    {
        "name": "register_intent",
        "description": (
            "Sign the compiled intent with the user's private key and register it "
            "on IntentRegistry.  Returns the intentId and transaction hash."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "object",
                    "description": "The intent dict returned by compile_intent.",
                }
            },
            "required": ["intent"],
        },
    },
    {
        "name": "research_scope",
        "description": (
            "Run the research agent to find the best narrowed execution scope for "
            "the intent.  Returns recommendedProtocols, suggestedAmounts, and rationale."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "object",
                    "description": "The compiled intent dict.",
                }
            },
            "required": ["intent"],
        },
    },
    {
        "name": "execute_intent",
        "description": (
            "Create an on-chain delegation with the narrowed scope and call "
            "ExecutionGate.executeIntent.  Returns success status and tx hashes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "intent_id": {"type": "string", "description": "The registered intentId (0x hex)."},
                "intent": {"type": "object", "description": "The compiled intent dict."},
                "research": {"type": "object", "description": "The research result dict."},
            },
            "required": ["intent_id", "intent", "research"],
        },
    },
]

_SYSTEM = """
You are an orchestrator for the Proof-of-Intent Protocol.
Your goal is to help a user execute a DeFi swap by:
  1. Compiling their request (call compile_intent)
  2. Registering the intent on-chain (call register_intent)
  3. Researching the best execution scope (call research_scope)
  4. Executing the intent (call execute_intent)

Use the tools in order.  After each tool call, briefly explain what happened
and what you are doing next.  If a step fails, explain why and stop.
""".strip()


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

def _dispatch_tool(name: str, inputs: dict[str, Any], state: dict[str, Any]) -> Any:
    w3 = get_web3()
    user_address = Account.from_key(USER_PRIVATE_KEY).address

    if name == "compile_intent":
        import time as _time
        nonce = get_nonce(w3, user_address)
        compiled = compile_intent(inputs["user_request"])
        # Augment with on-chain fields the compiler doesn't produce
        compiled["owner"] = user_address
        compiled["authorizedOrchestrator"] = user_address
        compiled["nonce"] = nonce
        compiled["deadline"] = int(_time.time()) + compiled.pop("deadlineMinutes", 30) * 60
        # Convert protocol names to keccak hex ids
        from web3 import Web3 as _Web3
        compiled["allowedProtocols"] = [
            _Web3.keccak(text=p).hex() for p in compiled.get("allowedProtocols", [])
        ]
        state["intent"] = compiled
        return compiled

    if name == "register_intent":
        intent = inputs["intent"]
        signature = sign_intent(intent, USER_PRIVATE_KEY)
        receipt = client_register_intent(w3, intent, signature, USER_PRIVATE_KEY)
        intent_id = extract_intent_id_from_receipt(receipt)
        state["intent_id"] = intent_id
        return {
            "intentId": intent_id,
            "txHash": "0x" + receipt["transactionHash"].hex(),
            "status": "success" if receipt["status"] == 1 else "reverted",
        }

    if name == "research_scope":
        research = research_best_scope(inputs["intent"])
        state["research"] = research
        return research

    if name == "execute_intent":
        result = execution_agent_execute(
            intent_id=inputs["intent_id"],
            intent=inputs["intent"],
            research=inputs["research"],
            agent_private_key=USER_PRIVATE_KEY,
        )
        state["execution_result"] = result
        return result

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Main orchestration loop
# ---------------------------------------------------------------------------

def run(user_request: str) -> dict[str, Any]:
    """
    Run the full orchestration for the given natural-language swap request.
    Returns the final state dict (intent, intent_id, research, execution_result).
    """
    print(f"\n[Orchestrator] Starting intent execution for: {user_request!r}\n")

    messages: list[dict] = [{"role": "user", "content": user_request}]
    state: dict[str, Any] = {}

    while True:
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_SYSTEM,
            tools=_TOOLS,
            messages=messages,
        )

        # Collect any text the agent produced
        for block in response.content:
            if block.type == "text" and block.text.strip():
                print(f"[Orchestrator] {block.text.strip()}")

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason != "tool_use":
            break

        # Process tool calls and feed results back
        tool_results: list[dict] = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            print(f"[Orchestrator] Calling tool: {block.name}({json.dumps(block.input)[:120]})")
            try:
                result = _dispatch_tool(block.name, block.input, state)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                })
                print(f"[Orchestrator] Tool result: {json.dumps(result, default=str)[:200]}")
            except Exception as exc:  # noqa: BLE001
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "is_error": True,
                    "content": str(exc),
                })
                print(f"[Orchestrator] Tool error: {exc}")

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return state
