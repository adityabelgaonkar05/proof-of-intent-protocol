"""
Orchestrator — entry point of the pipeline.

Receives the user's goal and rootIntentId, creates the first delegation
to the Research Agent, hands the task off via AXL, and waits for the
final COMPLETE or FAILED confirmation.
"""

import json
import sys

import config.config as config
from proof_of_intent import ContractClient
from utils import axl_client


def _b32(hex_str: str) -> bytes:
    s = hex_str[2:] if hex_str.startswith("0x") else hex_str
    return bytes.fromhex(s)


def run(root_intent_id: str, user_goal: str, orchestrator_private_key: str) -> dict:
    config.require_pipeline_keys("DEPLOYER_PRIVATE_KEY")

    # Step 1: Connect to contracts
    client = ContractClient(orchestrator_private_key)

    # Step 2: Load root intent
    intent = client.intent_registry.functions.getIntent(_b32(root_intent_id)).call()
    # intent tuple: (owner, authorizedOrchestrator, tokenIn, maxAmountIn,
    #                minAmountOut, allowedProtocols, deadline, nonce)
    max_amount = intent[3]
    deadline = intent[6]
    print(f"Root intent loaded: max_amount={max_amount}, deadline={deadline}")

    # Step 3: Create delegation to Research Agent (full scope — no narrowing yet)
    child_scope = {
        "maxAmountIn": intent[3],
        "minAmountOut": intent[4],
        "allowedProtocols": ["0x" + b.hex() for b in intent[5]],
        "deadline": intent[6],
    }
    delegation_id = client.delegate_from_root(
        root_intent_id, child_scope, config.RESEARCH_AGENT_ADDRESS
    )
    print(f"Delegation created: {delegation_id}")

    # Step 4: Send task to Research Agent via AXL
    message = {
        "type": "TASK",
        "delegationId": delegation_id,
        "goal": user_goal,
        "rootIntentId": root_intent_id,
    }
    axl_client.send_message(
        config.RESEARCH_AXL_KEY, message, port=config.ORCHESTRATOR_AXL_PORT
    )
    print("Task sent to Research Agent via AXL")

    # Step 5: Wait for completion confirmation
    while True:
        try:
            envelope = axl_client.listen_for_message(
                timeout=300, port=config.ORCHESTRATOR_AXL_PORT
            )
        except axl_client.AXLTimeout:
            raise TimeoutError("Timed out waiting for Research Agent response")

        msg = envelope["message"]
        if msg.get("type") in ("COMPLETE", "FAILED"):
            print(f"Result: {json.dumps(msg, indent=2)}")
            return msg


if __name__ == "__main__":
    root_intent_id = sys.argv[1]
    user_goal = sys.argv[2]
    run(root_intent_id, user_goal, config.DEPLOYER_PRIVATE_KEY)
