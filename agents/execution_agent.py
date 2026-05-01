"""
Execution Agent — final agent in the pipeline.

Receives an EXECUTE task from the Research Agent, runs a dry-run
verifyChain view call to confirm the full delegation chain is valid
against the root intent, then calls ExecutionGate.executeSwap on-chain.
Reports COMPLETE or FAILED back to the Orchestrator via AXL.
"""

import json

import config.config as config
from proof_of_intent import ContractClient
from utils import axl_client
from config.config import USDC_ADDRESS, EXECUTION_GATE_ADDRESS


def run(execution_private_key: str) -> None:
    # Step 1: Listen for task from Research Agent
    print("Execution Agent listening...")
    envelope = axl_client.listen_for_message(timeout=60, port=config.EXECUTION_AXL_PORT)
    message = envelope["message"]
    print(f"Received execution task: {json.dumps(message, indent=2)}")

    client = ContractClient(execution_private_key)

    # Step 2: Dry-run — verify the delegation chain as a view call before spending gas
    print("Verifying delegation chain against root intent...")
    try:
        valid = client.verify_chain(message["delegationId"], message["txParams"])
        print("Chain verification: PASSED")
    except Exception as e:
        print(f"Chain verification: FAILED — {e}")
        axl_client.send_message(
            config.ORCHESTRATOR_AXL_KEY,
            {"type": "FAILED", "reason": str(e)},
            port=config.EXECUTION_AXL_PORT,
        )
        return

    # Step 3: Ensure the recipient has approved ExecutionGate to pull tokenIn.
    # The recipient address comes from txParams; for USDC swaps this is the user wallet.
    amount_in = message["txParams"]["amountIn"]
    try:
        client.ensure_token_approval(USDC_ADDRESS, EXECUTION_GATE_ADDRESS, amount_in)
        print(f"Token approval confirmed for {amount_in} units")
    except Exception as e:
        print(f"Token approval failed — {e}")
        axl_client.send_message(
            config.ORCHESTRATOR_AXL_KEY,
            {"type": "FAILED", "reason": f"approval failed: {e}"},
            port=config.EXECUTION_AXL_PORT,
        )
        return

    # Step 4: Execute
    print("Executing swap via ExecutionGate...")
    try:
        tx_hash = client.execute_swap(message["delegationId"], message["txParams"])
        print("Swap executed successfully!")
        print(f"Transaction hash: {tx_hash}")
        axl_client.send_message(
            config.ORCHESTRATOR_AXL_KEY,
            {"type": "COMPLETE", "txHash": tx_hash},
            port=config.EXECUTION_AXL_PORT,
        )
    except Exception as e:
        print(f"Execution REVERTED: {e}")
        axl_client.send_message(
            config.ORCHESTRATOR_AXL_KEY,
            {"type": "FAILED", "reason": str(e)},
            port=config.EXECUTION_AXL_PORT,
        )


if __name__ == "__main__":
    run(config.EXECUTION_PRIVATE_KEY)
