"""
Web3 wrappers for IntentRegistry, DelegationRegistry, and ExecutionGate.
All write methods return the transaction receipt.
"""

from web3 import Web3
from web3.contract import Contract
from web3.types import TxReceipt

from config.config import (
    RPC_URL,
    CHAIN_ID,
    INTENT_REGISTRY_ADDRESS,
    DELEGATION_REGISTRY_ADDRESS,
    EXECUTION_GATE_ADDRESS,
    INTENT_REGISTRY_ABI,
    DELEGATION_REGISTRY_ABI,
    EXECUTION_GATE_ABI,
)


def get_web3() -> Web3:
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to RPC: {RPC_URL}")
    return w3


def get_intent_registry(w3: Web3) -> Contract:
    return w3.eth.contract(
        address=Web3.to_checksum_address(INTENT_REGISTRY_ADDRESS),
        abi=INTENT_REGISTRY_ABI,
    )


def get_delegation_registry(w3: Web3) -> Contract:
    return w3.eth.contract(
        address=Web3.to_checksum_address(DELEGATION_REGISTRY_ADDRESS),
        abi=DELEGATION_REGISTRY_ABI,
    )


def get_execution_gate(w3: Web3) -> Contract:
    return w3.eth.contract(
        address=Web3.to_checksum_address(EXECUTION_GATE_ADDRESS),
        abi=EXECUTION_GATE_ABI,
    )


# ---------------------------------------------------------------------------
# IntentRegistry helpers
# ---------------------------------------------------------------------------

def get_domain_separator(w3: Web3) -> str:
    """Return the 0x-prefixed hex domain separator from IntentRegistry."""
    registry = get_intent_registry(w3)
    raw: bytes = registry.functions.DOMAIN_SEPARATOR().call()
    return "0x" + raw.hex()


def get_nonce(w3: Web3, owner: str) -> int:
    registry = get_intent_registry(w3)
    return registry.functions.nonces(Web3.to_checksum_address(owner)).call()


def register_intent(
    w3: Web3,
    intent: dict,
    signature_hex: str,
    private_key: str,
) -> TxReceipt:
    """
    Broadcast registerIntent and return the receipt.
    intent dict keys: owner, tokenIn, maxAmountIn, minAmountOut,
                      allowedProtocols, deadline, nonce
    """
    registry = get_intent_registry(w3)
    account = w3.eth.account.from_key(private_key)

    intent_tuple = (
        Web3.to_checksum_address(intent["owner"]),
        Web3.to_checksum_address(intent["tokenIn"]),
        intent["maxAmountIn"],
        intent["minAmountOut"],
        [bytes.fromhex(p[2:] if p.startswith("0x") else p) for p in intent["allowedProtocols"]],
        intent["deadline"],
        intent["nonce"],
    )
    sig_bytes = bytes.fromhex(
        signature_hex[2:] if signature_hex.startswith("0x") else signature_hex
    )

    tx = registry.functions.registerIntent(intent_tuple, sig_bytes).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "chainId": CHAIN_ID,
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash)


def get_intent(w3: Web3, intent_id: str) -> dict:
    registry = get_intent_registry(w3)
    raw_id = bytes.fromhex(intent_id[2:] if intent_id.startswith("0x") else intent_id)
    result = registry.functions.getIntent(raw_id).call()
    return {
        "owner": result[0],
        "tokenIn": result[1],
        "maxAmountIn": result[2],
        "minAmountOut": result[3],
        "allowedProtocols": ["0x" + b.hex() for b in result[4]],
        "deadline": result[5],
        "nonce": result[6],
    }


# ---------------------------------------------------------------------------
# DelegationRegistry helpers
# ---------------------------------------------------------------------------

def delegate_from_root(
    w3: Web3,
    root_intent_id: str,
    scope: dict,
    delegate_to: str,
    private_key: str,
) -> TxReceipt:
    """scope keys: maxAmountIn, minAmountOut, allowedProtocols, deadline"""
    registry = get_delegation_registry(w3)
    account = w3.eth.account.from_key(private_key)

    raw_id = bytes.fromhex(root_intent_id[2:] if root_intent_id.startswith("0x") else root_intent_id)
    scope_tuple = (
        scope["maxAmountIn"],
        scope["minAmountOut"],
        [bytes.fromhex(p[2:] if p.startswith("0x") else p) for p in scope["allowedProtocols"]],
        scope["deadline"],
    )

    tx = registry.functions.delegateFromRoot(
        raw_id, scope_tuple, Web3.to_checksum_address(delegate_to)
    ).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "chainId": CHAIN_ID,
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash)


def delegate_from_delegation(
    w3: Web3,
    parent_delegation_id: str,
    scope: dict,
    delegate_to: str,
    private_key: str,
) -> TxReceipt:
    registry = get_delegation_registry(w3)
    account = w3.eth.account.from_key(private_key)

    raw_id = bytes.fromhex(
        parent_delegation_id[2:] if parent_delegation_id.startswith("0x") else parent_delegation_id
    )
    scope_tuple = (
        scope["maxAmountIn"],
        scope["minAmountOut"],
        [bytes.fromhex(p[2:] if p.startswith("0x") else p) for p in scope["allowedProtocols"]],
        scope["deadline"],
    )

    tx = registry.functions.delegateFromDelegation(
        raw_id, scope_tuple, Web3.to_checksum_address(delegate_to)
    ).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "chainId": CHAIN_ID,
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash)


def get_delegation(w3: Web3, delegation_id: str) -> dict:
    registry = get_delegation_registry(w3)
    raw_id = bytes.fromhex(
        delegation_id[2:] if delegation_id.startswith("0x") else delegation_id
    )
    r = registry.functions.getDelegation(raw_id).call()
    return {
        "parentId": "0x" + r[0].hex(),
        "isRootIntent": r[1],
        "scope": {
            "maxAmountIn": r[2][0],
            "minAmountOut": r[2][1],
            "allowedProtocols": ["0x" + b.hex() for b in r[2][2]],
            "deadline": r[2][3],
        },
        "delegatedTo": r[3],
        "executed": r[4],
    }


def extract_delegation_id_from_receipt(receipt: TxReceipt) -> str:
    """Parse the DelegationCreated event from a tx receipt to get the delegationId."""
    w3 = get_web3()
    registry = get_delegation_registry(w3)
    logs = registry.events.DelegationCreated().process_receipt(receipt)
    if not logs:
        raise ValueError("DelegationCreated event not found in receipt")
    return "0x" + logs[0]["args"]["delegationId"].hex()


def extract_intent_id_from_receipt(receipt: TxReceipt) -> str:
    """Parse the IntentRegistered event from a tx receipt to get the intentId."""
    w3 = get_web3()
    registry = get_intent_registry(w3)
    logs = registry.events.IntentRegistered().process_receipt(receipt)
    if not logs:
        raise ValueError("IntentRegistered event not found in receipt")
    return "0x" + logs[0]["args"]["intentId"].hex()


# ---------------------------------------------------------------------------
# ExecutionGate helpers
# ---------------------------------------------------------------------------

def verify_chain(w3: Web3, delegation_id: str, tx_params: dict) -> bool:
    """
    Call verifyChain as a view function (no gas).
    tx_params keys: amountIn, minAmountOut, protocol (hex), tokenIn, tokenOut, recipient
    """
    gate = get_execution_gate(w3)
    raw_id = bytes.fromhex(delegation_id[2:] if delegation_id.startswith("0x") else delegation_id)
    params_tuple = _build_tx_params_tuple(tx_params)
    return gate.functions.verifyChain(raw_id, params_tuple).call()


def execute_swap(w3: Web3, delegation_id: str, tx_params: dict, private_key: str) -> TxReceipt:
    """
    Broadcast executeSwap and return the receipt.
    tx_params keys: amountIn, minAmountOut, protocol (hex), tokenIn, tokenOut, recipient
    """
    gate = get_execution_gate(w3)
    account = w3.eth.account.from_key(private_key)

    raw_id = bytes.fromhex(delegation_id[2:] if delegation_id.startswith("0x") else delegation_id)
    params_tuple = _build_tx_params_tuple(tx_params)

    tx = gate.functions.executeSwap(raw_id, params_tuple).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "chainId": CHAIN_ID,
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash)


def _build_tx_params_tuple(tx_params: dict) -> tuple:
    protocol = tx_params["protocol"]
    protocol_bytes = bytes.fromhex(protocol[2:] if protocol.startswith("0x") else protocol)
    return (
        tx_params["amountIn"],
        tx_params["minAmountOut"],
        protocol_bytes,
        Web3.to_checksum_address(tx_params["tokenIn"]),
        Web3.to_checksum_address(tx_params["tokenOut"]),
        Web3.to_checksum_address(tx_params["recipient"]),
    )
