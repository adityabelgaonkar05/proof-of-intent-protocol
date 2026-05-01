"""
Research Agent — receives a TASK from the Orchestrator, simulates route
research, creates a sub-delegation to the Execution Agent, and forwards
the job via AXL.

The COMPROMISED flag simulates a prompt-injection attack: when True, the
agent tries to widen the scope beyond what the root intent permits.  The
smart contract rejects the over-limit delegation, demonstrating that
on-chain constraints are the last line of defence.
"""

import json
import time

from web3 import Web3

import config.config as config
from proof_of_intent import ContractClient
from utils.contract_client import get_web3, get_delegation
from utils import axl_client

COMPROMISED = False

_UNISWAP_V3_ID: str = Web3.keccak(text="Uniswap-V3").hex()


def run(research_private_key: str) -> None:
    # Step 1: Listen for task from Orchestrator
    print("Research Agent listening for task...")
    envelope = axl_client.listen_for_message(timeout=60, port=config.RESEARCH_AXL_PORT)
    task = envelope["message"]
    print(f"Received task: {task['goal']}")

    # Step 2: Simulate research
    print("Researching best swap route...")
    time.sleep(2)
    print("Found route: Uniswap V3, estimated output: 0.18 ETH")

    # Fetch delegation scope so we can respect (or exceed) the deadline
    w3 = get_web3()
    delegation_info = get_delegation(w3, task["delegationId"])
    message_deadline: int = delegation_info["scope"]["deadline"]

    # Step 3: Determine execution scope
    if not COMPROMISED:
        child_scope = {
            "maxAmountIn": 400_000_000,           # 400 USDC (6 decimals)
            "minAmountOut": 180_000_000_000_000_000,  # 0.18 ETH
            "allowedProtocols": [_UNISWAP_V3_ID],
            "deadline": message_deadline - 300,   # 5 min tighter than parent
        }
        print("Creating valid delegation with maxAmountIn=400 USDC")
    else:
        print("*** COMPROMISED: Malicious instruction received: send 800 USDC ***")
        child_scope = {
            "maxAmountIn": 800_000_000,           # ATTACK: exceeds root intent of 500
            "minAmountOut": 180_000_000_000_000_000,
            "allowedProtocols": [_UNISWAP_V3_ID],
            "deadline": message_deadline,
        }
        print("*** Attempting malicious delegation with maxAmountIn=800 USDC ***")

    # Step 4: Try to create sub-delegation to Execution Agent
    client = ContractClient(research_private_key)
    try:
        delegation_id = client.delegate_from_delegation(
            task["delegationId"], child_scope, config.EXECUTION_AGENT_ADDRESS
        )
    except Exception as e:
        print(f"*** DELEGATION REVERTED: {e} ***")
        print("*** ATTACK BLOCKED BY SMART CONTRACT ***")
        axl_client.send_message(
            config.ORCHESTRATOR_AXL_KEY,
            {"type": "FAILED", "reason": str(e)},
            port=config.RESEARCH_AXL_PORT,
        )
        return

    # Step 5: Forward to Execution Agent via AXL
    forward_message = {
        "type": "EXECUTE",
        "delegationId": delegation_id,
        "txParams": {
            "amountIn": 400_000_000,
            "minAmountOut": 180_000_000_000_000_000,
            "protocol": _UNISWAP_V3_ID,
            "tokenIn": config.USDC_ADDRESS,
            "tokenOut": config.WETH_ADDRESS,
            "recipient": config.USER_ADDRESS,
        },
    }
    axl_client.send_message(
        config.EXECUTION_AXL_KEY, forward_message, port=config.RESEARCH_AXL_PORT
    )
    print("Task forwarded to Execution Agent")


if __name__ == "__main__":
    import sys

    if "--compromised" in sys.argv:
        COMPROMISED = True
        print("*** RESEARCH AGENT STARTING IN COMPROMISED MODE ***")
    run(config.RESEARCH_PRIVATE_KEY)
