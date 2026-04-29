"""
Execution agent — takes a registered intent and a research recommendation,
creates the on-chain delegation with the narrowed scope, then calls
ExecutionGate.executeIntent.

This agent holds the agent's private key and is the only component that
broadcasts on-chain transactions on behalf of the delegated agent address.
"""

import time
from typing import Any

from web3.types import TxReceipt

from utils.contract_client import (
    get_web3,
    delegate_from_root,
    execute_swap,
    verify_chain,
    get_delegation,
    extract_delegation_id_from_receipt,
)


def build_narrow_scope(intent: dict[str, Any], research: dict[str, Any]) -> dict[str, Any]:
    """
    Merge intent constraints with research recommendations into a Scope dict
    that is provably narrower than the root intent on every axis.
    """
    deadline_minutes = research.get("suggestedDeadlineMinutes", 15)
    deadline = min(intent["deadline"], int(time.time()) + deadline_minutes * 60)

    return {
        "maxAmountIn": min(
            intent["maxAmountIn"],
            research.get("suggestedMaxAmountIn", intent["maxAmountIn"]),
        ),
        "minAmountOut": max(
            intent["minAmountOut"],
            research.get("suggestedMinAmountOut", intent["minAmountOut"]),
        ),
        "allowedProtocols": research.get(
            "recommendedProtocolIds", intent["allowedProtocols"]
        ),
        "deadline": deadline,
    }


def build_tx_params(
    intent: dict[str, Any],
    scope: dict[str, Any],
    research: dict[str, Any],
    agent_address: str,
    token_out: str = "0x0000000000000000000000000000000000000000",
) -> dict[str, Any]:
    """
    Construct TxParams for ExecutionGate.executeSwap from the intent and research output.
    token_out defaults to the zero address for demo — production resolves the real address.
    """
    protocol_ids: list[str] = scope["allowedProtocols"]
    # Pick the first recommended protocol (research already narrowed the list)
    protocol = research.get("recommendedProtocolIds", protocol_ids)[0]

    return {
        "amountIn":     scope["maxAmountIn"],
        "minAmountOut": scope["minAmountOut"],
        "protocol":     protocol,
        "tokenIn":      intent["tokenIn"],
        "tokenOut":     token_out,
        "recipient":    agent_address,
    }


def execute(
    intent_id: str,
    intent: dict[str, Any],
    research: dict[str, Any],
    agent_private_key: str,
    token_out: str = "0x0000000000000000000000000000000000000000",
) -> dict[str, Any]:
    """
    Full execution flow:
      1. Delegate from root intent with narrowed scope
      2. Verify the chain (view call — fails fast before broadcasting)
      3. Execute via ExecutionGate.executeSwap

    Returns a result dict with delegationId, receipts, and status.
    """
    w3 = get_web3()
    agent_address = w3.eth.account.from_key(agent_private_key).address

    scope = build_narrow_scope(intent, research)

    print(f"[ExecutionAgent] Creating delegation from root intent {intent_id}")
    print(f"  scope.maxAmountIn  = {scope['maxAmountIn']}")
    print(f"  scope.minAmountOut = {scope['minAmountOut']}")
    print(f"  scope.protocols    = {scope['allowedProtocols']}")
    print(f"  scope.deadline     = {scope['deadline']}")

    delegation_receipt: TxReceipt = delegate_from_root(
        w3=w3,
        root_intent_id=intent_id,
        scope=scope,
        delegate_to=agent_address,
        private_key=agent_private_key,
    )

    if delegation_receipt["status"] != 1:
        return {
            "success": False,
            "error": "delegateFromRoot transaction reverted",
            "receipt": dict(delegation_receipt),
        }

    delegation_id = extract_delegation_id_from_receipt(delegation_receipt)
    print(f"[ExecutionAgent] Delegation created: {delegation_id}")

    tx_params = build_tx_params(intent, scope, research, agent_address, token_out)

    # Dry-run verifyChain before paying gas on executeSwap
    try:
        verify_chain(w3, delegation_id, tx_params)
    except Exception as exc:
        return {
            "success": False,
            "error": f"Chain verification failed (dry-run): {exc}",
            "delegationId": delegation_id,
        }

    print(f"[ExecutionAgent] Calling ExecutionGate.executeSwap({delegation_id})")
    exec_receipt: TxReceipt = execute_swap(
        w3=w3,
        delegation_id=delegation_id,
        tx_params=tx_params,
        private_key=agent_private_key,
    )

    if exec_receipt["status"] != 1:
        return {
            "success": False,
            "error": "executeSwap transaction reverted",
            "delegationId": delegation_id,
            "receipt": dict(exec_receipt),
        }

    delegation = get_delegation(w3, delegation_id)
    print(f"[ExecutionAgent] Swap executed successfully. executed={delegation['executed']}")

    return {
        "success": True,
        "intentId": intent_id,
        "delegationId": delegation_id,
        "agentAddress": agent_address,
        "delegationTxHash": "0x" + delegation_receipt["transactionHash"].hex(),
        "executionTxHash": "0x" + exec_receipt["transactionHash"].hex(),
        "executed": delegation["executed"],
    }
