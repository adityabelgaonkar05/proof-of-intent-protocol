"""
End-to-end integration test for the Proof-of-Intent Protocol.

Requires a local Anvil node:
    anvil --port 8545

Run with:
    python -m utils.integration_test

The test deploys all four contracts plus a MockERC20 and MockSwapRouter from the
Foundry build artifacts, registers agents, runs the full delegation-and-execution
flow (including real tokenIn transferFrom + router call), then confirms that a
scope-exceeding delegation is correctly rejected.
"""

import json
import pathlib
import time

from eth_account import Account
from web3 import Web3
from web3.exceptions import ContractLogicError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ROOT = pathlib.Path(__file__).parent.parent
_OUT  = _ROOT / "contracts" / "out"

TOKEN_OUT = "0x0000000000000000000000000000000000000001"
CHAIN_ID  = 31337  # Anvil default


def _load(contract_name: str) -> dict:
    path = _OUT / f"{contract_name}.sol" / f"{contract_name}.json"
    return json.loads(path.read_text())


def _deploy(w3, artifact, deployer, *constructor_args):
    abi      = artifact["abi"]
    bytecode = artifact["bytecode"]["object"]
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash  = contract.constructor(*constructor_args).transact({"from": deployer})
    receipt  = w3.eth.wait_for_transaction_receipt(tx_hash)
    assert receipt.status == 1, "Deploy failed"
    return w3.eth.contract(address=receipt.contractAddress, abi=abi)


def _b32(hex_str: str) -> bytes:
    s = hex_str[2:] if hex_str.startswith("0x") else hex_str
    return bytes.fromhex(s)


def _sign_intent(w3, intent: dict, private_key: str, registry_address: str) -> bytes:
    """Produce an EIP-712 signature for an Intent struct."""
    from eth_account.messages import encode_typed_data

    domain = {
        "name": "IntentRegistry",
        "version": "1",
        "chainId": CHAIN_ID,
        "verifyingContract": registry_address,
    }
    intent_type = {
        "Intent": [
            {"name": "owner",                  "type": "address"},
            {"name": "authorizedOrchestrator", "type": "address"},
            {"name": "tokenIn",                "type": "address"},
            {"name": "maxAmountIn",            "type": "uint256"},
            {"name": "minAmountOut",           "type": "uint256"},
            {"name": "allowedProtocols",       "type": "bytes32[]"},
            {"name": "deadline",               "type": "uint256"},
            {"name": "nonce",                  "type": "uint256"},
        ]
    }
    signed = Account.sign_typed_data(private_key, domain, intent_type, intent)
    return signed.signature


def _protocol_id(name: str) -> bytes:
    return Web3.keccak(text=name)


# ---------------------------------------------------------------------------
# Main integration test
# ---------------------------------------------------------------------------

def run():
    w3 = Web3(Web3.HTTPProvider("http://localhost:8545"))
    assert w3.is_connected(), "Anvil node not reachable at http://localhost:8545"

    accounts = w3.eth.accounts
    deployer           = accounts[0]
    user_key           = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"  # Anvil key #0
    orchestrator_key   = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"  # Anvil key #1
    research_key       = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"  # Anvil key #2
    execution_key      = "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6"  # Anvil key #3

    user_addr          = Account.from_key(user_key).address
    orchestrator_addr  = Account.from_key(orchestrator_key).address
    research_addr      = Account.from_key(research_key).address
    execution_addr     = Account.from_key(execution_key).address

    print(f"User:         {user_addr}")
    print(f"Orchestrator: {orchestrator_addr}")
    print(f"Research:     {research_addr}")
    print(f"Execution:    {execution_addr}")

    # -------------------------------------------------------------------------
    # Deploy contracts
    # -------------------------------------------------------------------------
    print("\n[1] Deploying contracts...")

    agent_art      = _load("AgentRegistry")
    intent_art     = _load("IntentRegistry")
    deleg_art      = _load("DelegationRegistry")
    gate_art       = _load("ExecutionGate")
    mock_erc20_art = _load("MockERC20")
    mock_router_art = _load("MockSwapRouter")

    agent_reg   = _deploy(w3, agent_art, deployer)
    intent_reg  = _deploy(w3, intent_art, deployer)
    deleg_reg   = _deploy(w3, deleg_art, deployer, intent_reg.address, agent_reg.address)
    mock_token  = _deploy(w3, mock_erc20_art, deployer)
    mock_router = _deploy(w3, mock_router_art, deployer)
    exec_gate   = _deploy(w3, gate_art, deployer, intent_reg.address, deleg_reg.address, mock_router.address)

    TOKEN_IN = mock_token.address

    # Wire up execution gate
    tx = deleg_reg.functions.setExecutionGate(exec_gate.address).transact({"from": deployer})
    w3.eth.wait_for_transaction_receipt(tx)

    print(f"  AgentRegistry:      {agent_reg.address}")
    print(f"  IntentRegistry:     {intent_reg.address}")
    print(f"  DelegationRegistry: {deleg_reg.address}")
    print(f"  MockERC20 (tokenIn):{mock_token.address}")
    print(f"  MockSwapRouter:     {mock_router.address}")
    print(f"  ExecutionGate:      {exec_gate.address}")

    # -------------------------------------------------------------------------
    # Register agents
    # -------------------------------------------------------------------------
    print("\n[2] Registering agents...")

    for addr, name in [
        (orchestrator_addr, "Orchestrator"),
        (research_addr,     "ResearchAgent"),
        (execution_addr,    "ExecutionAgent"),
    ]:
        tx = agent_reg.functions.registerAgent(addr, name).transact({"from": deployer})
        w3.eth.wait_for_transaction_receipt(tx)
        print(f"  Registered {name}: {addr}")

    # -------------------------------------------------------------------------
    # Build and sign intent  (500 USDC-equivalent, Uniswap-V3, 60 min)
    # -------------------------------------------------------------------------
    print("\n[3] Building and signing intent...")

    protocol_id    = _protocol_id("Uniswap-V3")
    deadline       = int(time.time()) + 3600
    nonce          = intent_reg.functions.nonces(user_addr).call()
    max_amount_in  = 500 * 10**6          # 500 USDC (6 decimals)
    min_amount_out = 490 * 10**6

    intent_data = {
        "owner":                  user_addr,
        "authorizedOrchestrator": orchestrator_addr,
        "tokenIn":                Web3.to_checksum_address(TOKEN_IN),
        "maxAmountIn":            max_amount_in,
        "minAmountOut":           min_amount_out,
        "allowedProtocols":       [protocol_id],
        "deadline":               deadline,
        "nonce":                  nonce,
    }

    signature = _sign_intent(w3, intent_data, user_key, intent_reg.address)

    # -------------------------------------------------------------------------
    # Register intent
    # -------------------------------------------------------------------------
    print("\n[4] Registering intent on-chain...")

    intent_tuple = (
        user_addr,
        orchestrator_addr,
        Web3.to_checksum_address(TOKEN_IN),
        max_amount_in,
        min_amount_out,
        [protocol_id],
        deadline,
        nonce,
    )

    tx_hash = w3.eth.send_raw_transaction(
        Account.from_key(user_key).sign_transaction(
            intent_reg.functions.registerIntent(intent_tuple, signature).build_transaction({
                "from":    user_addr,
                "nonce":   w3.eth.get_transaction_count(user_addr),
                "chainId": CHAIN_ID,
                "gas":     500_000,
            })
        ).raw_transaction
    )
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    assert receipt.status == 1, "registerIntent reverted"

    logs = intent_reg.events.IntentRegistered().process_receipt(receipt)
    intent_id = "0x" + logs[0]["args"]["intentId"].hex()
    print(f"  intentId: {intent_id}")

    # -------------------------------------------------------------------------
    # Delegate from root  (orchestrator → research agent, 400 USDC)
    # -------------------------------------------------------------------------
    print("\n[5] Delegating from root to research agent...")

    scope1 = (
        400 * 10**6,          # maxAmountIn: 400 USDC
        492 * 10**6,          # minAmountOut (tighter than root)
        [protocol_id],
        int(time.time()) + 1800,
    )

    tx_hash = w3.eth.send_raw_transaction(
        Account.from_key(orchestrator_key).sign_transaction(
            deleg_reg.functions.delegateFromRoot(
                _b32(intent_id), scope1, research_addr
            ).build_transaction({
                "from":    orchestrator_addr,
                "nonce":   w3.eth.get_transaction_count(orchestrator_addr),
                "chainId": CHAIN_ID,
                "gas":     500_000,
            })
        ).raw_transaction
    )
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    assert receipt.status == 1, "delegateFromRoot reverted"

    logs = deleg_reg.events.DelegationCreated().process_receipt(receipt)
    delegation_id_1 = "0x" + logs[0]["args"]["delegationId"].hex()
    print(f"  delegation1 (root→research): {delegation_id_1}")

    # -------------------------------------------------------------------------
    # Delegate from delegation  (research → execution agent, 300 USDC)
    # -------------------------------------------------------------------------
    print("\n[6] Delegating from delegation to execution agent...")

    scope2 = (
        300 * 10**6,          # maxAmountIn: 300 USDC (narrower)
        494 * 10**6,          # minAmountOut (even tighter)
        [protocol_id],
        int(time.time()) + 900,
    )

    tx_hash = w3.eth.send_raw_transaction(
        Account.from_key(research_key).sign_transaction(
            deleg_reg.functions.delegateFromDelegation(
                _b32(delegation_id_1), scope2, execution_addr
            ).build_transaction({
                "from":    research_addr,
                "nonce":   w3.eth.get_transaction_count(research_addr),
                "chainId": CHAIN_ID,
                "gas":     500_000,
            })
        ).raw_transaction
    )
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    assert receipt.status == 1, "delegateFromDelegation reverted"

    logs = deleg_reg.events.DelegationCreated().process_receipt(receipt)
    delegation_id_2 = "0x" + logs[0]["args"]["delegationId"].hex()
    print(f"  delegation2 (research→execution): {delegation_id_2}")

    # -------------------------------------------------------------------------
    # Verify chain (view call, must return True)
    # -------------------------------------------------------------------------
    print("\n[7] Verifying chain...")

    amount_in = 250 * 10**6   # 250 USDC (<= all scopes)
    tx_params = (
        amount_in,
        495 * 10**6,          # minAmountOut (>= all scopes)
        protocol_id,
        Web3.to_checksum_address(TOKEN_IN),
        Web3.to_checksum_address(TOKEN_OUT),
        execution_addr,       # recipient — also the tx sender
    )

    ok = exec_gate.functions.verifyChain(_b32(delegation_id_2), tx_params).call()
    assert ok, "verifyChain returned False"
    print("  verifyChain → True  ✓")

    # -------------------------------------------------------------------------
    # Mint tokenIn to execution_addr (recipient) and approve ExecutionGate
    # -------------------------------------------------------------------------
    print("\n[7b] Setting up token approval for executeSwap...")

    # Mint enough tokenIn to the recipient (execution_addr acts as both caller
    # and recipient in this integration test).
    tx = mock_token.functions.mint(execution_addr, amount_in * 2).transact({"from": deployer})
    w3.eth.wait_for_transaction_receipt(tx)

    # execution_addr approves ExecutionGate to pull its tokenIn.
    tx_hash = w3.eth.send_raw_transaction(
        Account.from_key(execution_key).sign_transaction(
            mock_token.functions.approve(exec_gate.address, amount_in * 2).build_transaction({
                "from":    execution_addr,
                "nonce":   w3.eth.get_transaction_count(execution_addr),
                "chainId": CHAIN_ID,
                "gas":     100_000,
            })
        ).raw_transaction
    )
    w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"  Minted {amount_in} tokenIn to {execution_addr}")
    print(f"  Approved ExecutionGate ({exec_gate.address}) to spend tokenIn  ✓")

    # -------------------------------------------------------------------------
    # Execute swap
    # -------------------------------------------------------------------------
    print("\n[8] Calling executeSwap...")

    tx_hash = w3.eth.send_raw_transaction(
        Account.from_key(execution_key).sign_transaction(
            exec_gate.functions.executeSwap(
                _b32(delegation_id_2), tx_params
            ).build_transaction({
                "from":    execution_addr,
                "nonce":   w3.eth.get_transaction_count(execution_addr),
                "chainId": CHAIN_ID,
                "gas":     500_000,
            })
        ).raw_transaction
    )
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    assert receipt.status == 1, "executeSwap reverted"

    delegation_state = deleg_reg.functions.getDelegation(_b32(delegation_id_2)).call()
    assert delegation_state[4], "executed flag not set after executeSwap"
    print(f"  executeSwap tx: 0x{receipt['transactionHash'].hex()}")
    print("  delegation.executed → True  ✓")

    # -------------------------------------------------------------------------
    # Malicious delegation: 800 USDC when only 400 was authorized (scope1)
    # This must be rejected with "Amount exceeds scope"
    # -------------------------------------------------------------------------
    print("\n[9] Attempting malicious delegation (800 USDC > 400 authorized)...")

    # Need a fresh root delegation on a new intent (replay protection consumed scope1).
    # Register a second intent (nonce = 1) and delegate from it.
    nonce2 = intent_reg.functions.nonces(user_addr).call()
    intent_data2 = {**intent_data, "nonce": nonce2}
    sig2 = _sign_intent(w3, intent_data2, user_key, intent_reg.address)
    intent_tuple2 = (
        user_addr, orchestrator_addr, Web3.to_checksum_address(TOKEN_IN),
        max_amount_in, min_amount_out, [protocol_id], deadline, nonce2,
    )
    tx_hash = w3.eth.send_raw_transaction(
        Account.from_key(user_key).sign_transaction(
            intent_reg.functions.registerIntent(intent_tuple2, sig2).build_transaction({
                "from":    user_addr,
                "nonce":   w3.eth.get_transaction_count(user_addr),
                "chainId": CHAIN_ID,
                "gas":     500_000,
            })
        ).raw_transaction
    )
    receipt2 = w3.eth.wait_for_transaction_receipt(tx_hash)
    logs2 = intent_reg.events.IntentRegistered().process_receipt(receipt2)
    intent_id2 = "0x" + logs2[0]["args"]["intentId"].hex()

    # Delegate from root: authorize research with 400 USDC
    scope_limited = (400 * 10**6, 492 * 10**6, [protocol_id], int(time.time()) + 1800)
    tx_hash = w3.eth.send_raw_transaction(
        Account.from_key(orchestrator_key).sign_transaction(
            deleg_reg.functions.delegateFromRoot(
                _b32(intent_id2), scope_limited, research_addr
            ).build_transaction({
                "from":    orchestrator_addr,
                "nonce":   w3.eth.get_transaction_count(orchestrator_addr),
                "chainId": CHAIN_ID,
                "gas":     500_000,
            })
        ).raw_transaction
    )
    receipt3 = w3.eth.wait_for_transaction_receipt(tx_hash)
    logs3 = deleg_reg.events.DelegationCreated().process_receipt(receipt3)
    delegation_limited = "0x" + logs3[0]["args"]["delegationId"].hex()

    # Now research tries to sub-delegate 800 USDC — must revert.
    # Use eth_call to get the revert reason before broadcasting.
    scope_malicious = (800 * 10**6, 492 * 10**6, [protocol_id], int(time.time()) + 900)
    revert_reason = ""
    reverted = False
    try:
        deleg_reg.functions.delegateFromDelegation(
            _b32(delegation_limited), scope_malicious, execution_addr
        ).call({"from": research_addr})
    except ContractLogicError as exc:
        reverted = True
        revert_reason = str(exc)
    except Exception as exc:
        reverted = True
        revert_reason = str(exc)

    assert reverted, "Expected revert for malicious delegation but got none"
    assert "Amount exceeds scope" in revert_reason, (
        f"Expected 'Amount exceeds scope' in revert reason, got: {revert_reason!r}"
    )
    print(f"  Malicious delegation correctly reverted with: {revert_reason[:80]}")
    print("  'Amount exceeds scope'  ✓")

    print("\n========================================")
    print("All integration tests passed.")
    print("========================================")


if __name__ == "__main__":
    run()
