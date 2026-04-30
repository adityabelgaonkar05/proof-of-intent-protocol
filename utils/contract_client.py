from eth_account import Account
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


def _strip(hex_str: str) -> str:
    return hex_str[2:] if hex_str.startswith("0x") else hex_str


def _b32(hex_str: str) -> bytes:
    return bytes.fromhex(_strip(hex_str))


class ContractClient:
    def __init__(self, private_key: str):
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to RPC: {RPC_URL}")
        self.account = Account.from_key(private_key)
        self.intent_registry = self.w3.eth.contract(
            address=Web3.to_checksum_address(INTENT_REGISTRY_ADDRESS),
            abi=INTENT_REGISTRY_ABI,
        )
        self.delegation_registry = self.w3.eth.contract(
            address=Web3.to_checksum_address(DELEGATION_REGISTRY_ADDRESS),
            abi=DELEGATION_REGISTRY_ABI,
        )
        self.execution_gate = self.w3.eth.contract(
            address=Web3.to_checksum_address(EXECUTION_GATE_ADDRESS),
            abi=EXECUTION_GATE_ABI,
        )

    def _send_tx_receipt(self, contract_function) -> TxReceipt:
        gas = contract_function.estimate_gas({"from": self.account.address})
        tx = contract_function.build_transaction({
            "from": self.account.address,
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "chainId": CHAIN_ID,
            "gas": gas,
        })
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status == 0:
            raise Exception("Transaction reverted")
        return receipt

    def send_tx(self, contract_function) -> str:
        receipt = self._send_tx_receipt(contract_function)
        return receipt["transactionHash"].hex()

    def register_intent(self, intent: dict, signature: str) -> str:
        sig_bytes = bytes.fromhex(_strip(signature))
        receipt = self._send_tx_receipt(
            self.intent_registry.functions.registerIntent(
                self._encode_intent(intent), sig_bytes
            )
        )
        logs = self.intent_registry.events.IntentRegistered().process_receipt(receipt)
        if not logs:
            raise ValueError("IntentRegistered event not found in receipt")
        return "0x" + logs[0]["args"]["intentId"].hex()

    def delegate_from_root(
        self, root_intent_id: str, child_scope: dict, delegate_to: str
    ) -> str:
        receipt = self._send_tx_receipt(
            self.delegation_registry.functions.delegateFromRoot(
                _b32(root_intent_id),
                self._encode_scope(child_scope),
                Web3.to_checksum_address(delegate_to),
            )
        )
        return self._extract_delegation_id(receipt)

    def delegate_from_delegation(
        self, parent_delegation_id: str, child_scope: dict, delegate_to: str
    ) -> str:
        receipt = self._send_tx_receipt(
            self.delegation_registry.functions.delegateFromDelegation(
                _b32(parent_delegation_id),
                self._encode_scope(child_scope),
                Web3.to_checksum_address(delegate_to),
            )
        )
        return self._extract_delegation_id(receipt)

    def execute_swap(self, delegation_id: str, tx_params: dict) -> str:
        return self.send_tx(
            self.execution_gate.functions.executeSwap(
                _b32(delegation_id),
                self._encode_tx_params(tx_params),
            )
        )

    def verify_chain(self, delegation_id: str, tx_params: dict) -> bool:
        return self.execution_gate.functions.verifyChain(
            _b32(delegation_id),
            self._encode_tx_params(tx_params),
        ).call()

    # ------------------------------------------------------------------
    # Struct encoders
    # ------------------------------------------------------------------

    def _encode_intent(self, intent: dict) -> tuple:
        # Field order: owner, authorizedOrchestrator, tokenIn, maxAmountIn,
        #              minAmountOut, allowedProtocols, deadline, nonce
        return (
            Web3.to_checksum_address(intent["owner"]),
            Web3.to_checksum_address(intent["authorizedOrchestrator"]),
            Web3.to_checksum_address(intent["tokenIn"]),
            intent["maxAmountIn"],
            intent["minAmountOut"],
            [_b32(p) for p in intent["allowedProtocols"]],
            intent["deadline"],
            intent["nonce"],
        )

    def _encode_scope(self, scope: dict) -> tuple:
        return (
            scope["maxAmountIn"],
            scope["minAmountOut"],
            [_b32(p) for p in scope["allowedProtocols"]],
            scope["deadline"],
        )

    def _encode_tx_params(self, params: dict) -> tuple:
        return (
            params["amountIn"],
            params["minAmountOut"],
            _b32(params["protocol"]),
            Web3.to_checksum_address(params["tokenIn"]),
            Web3.to_checksum_address(params["tokenOut"]),
            Web3.to_checksum_address(params["recipient"]),
        )

    def _extract_delegation_id(self, receipt: TxReceipt) -> str:
        logs = self.delegation_registry.events.DelegationCreated().process_receipt(receipt)
        if not logs:
            raise ValueError("DelegationCreated event not found in receipt")
        return "0x" + logs[0]["args"]["delegationId"].hex()


# ---------------------------------------------------------------------------
# Module-level helpers (used by orchestrator.py and execution_agent.py)
# ---------------------------------------------------------------------------

def get_web3() -> Web3:
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to RPC: {RPC_URL}")
    return w3


def get_nonce(w3: Web3, owner: str) -> int:
    registry: Contract = w3.eth.contract(
        address=Web3.to_checksum_address(INTENT_REGISTRY_ADDRESS),
        abi=INTENT_REGISTRY_ABI,
    )
    return registry.functions.nonces(Web3.to_checksum_address(owner)).call()


def get_domain_separator(w3: Web3) -> str:
    registry: Contract = w3.eth.contract(
        address=Web3.to_checksum_address(INTENT_REGISTRY_ADDRESS),
        abi=INTENT_REGISTRY_ABI,
    )
    raw: bytes = registry.functions.DOMAIN_SEPARATOR().call()
    return "0x" + raw.hex()


def register_intent(
    w3: Web3, intent: dict, signature_hex: str, private_key: str
) -> TxReceipt:
    client = ContractClient(private_key)
    return client._send_tx_receipt(
        client.intent_registry.functions.registerIntent(
            client._encode_intent(intent),
            bytes.fromhex(_strip(signature_hex)),
        )
    )


def extract_intent_id_from_receipt(receipt: TxReceipt) -> str:
    w3 = get_web3()
    registry: Contract = w3.eth.contract(
        address=Web3.to_checksum_address(INTENT_REGISTRY_ADDRESS),
        abi=INTENT_REGISTRY_ABI,
    )
    logs = registry.events.IntentRegistered().process_receipt(receipt)
    if not logs:
        raise ValueError("IntentRegistered event not found in receipt")
    return "0x" + logs[0]["args"]["intentId"].hex()


def delegate_from_root(
    w3: Web3, root_intent_id: str, scope: dict, delegate_to: str, private_key: str
) -> TxReceipt:
    client = ContractClient(private_key)
    return client._send_tx_receipt(
        client.delegation_registry.functions.delegateFromRoot(
            _b32(root_intent_id),
            client._encode_scope(scope),
            Web3.to_checksum_address(delegate_to),
        )
    )


def delegate_from_delegation(
    w3: Web3,
    parent_delegation_id: str,
    scope: dict,
    delegate_to: str,
    private_key: str,
) -> TxReceipt:
    client = ContractClient(private_key)
    return client._send_tx_receipt(
        client.delegation_registry.functions.delegateFromDelegation(
            _b32(parent_delegation_id),
            client._encode_scope(scope),
            Web3.to_checksum_address(delegate_to),
        )
    )


def get_delegation(w3: Web3, delegation_id: str) -> dict:
    registry: Contract = w3.eth.contract(
        address=Web3.to_checksum_address(DELEGATION_REGISTRY_ADDRESS),
        abi=DELEGATION_REGISTRY_ABI,
    )
    r = registry.functions.getDelegation(_b32(delegation_id)).call()
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
    w3 = get_web3()
    registry: Contract = w3.eth.contract(
        address=Web3.to_checksum_address(DELEGATION_REGISTRY_ADDRESS),
        abi=DELEGATION_REGISTRY_ABI,
    )
    logs = registry.events.DelegationCreated().process_receipt(receipt)
    if not logs:
        raise ValueError("DelegationCreated event not found in receipt")
    return "0x" + logs[0]["args"]["delegationId"].hex()


def verify_chain(w3: Web3, delegation_id: str, tx_params: dict) -> bool:
    gate: Contract = w3.eth.contract(
        address=Web3.to_checksum_address(EXECUTION_GATE_ADDRESS),
        abi=EXECUTION_GATE_ABI,
    )
    params_tuple = (
        tx_params["amountIn"],
        tx_params["minAmountOut"],
        _b32(tx_params["protocol"]),
        Web3.to_checksum_address(tx_params["tokenIn"]),
        Web3.to_checksum_address(tx_params["tokenOut"]),
        Web3.to_checksum_address(tx_params["recipient"]),
    )
    return gate.functions.verifyChain(_b32(delegation_id), params_tuple).call()


def execute_swap(w3: Web3, delegation_id: str, tx_params: dict, private_key: str) -> TxReceipt:
    client = ContractClient(private_key)
    return client._send_tx_receipt(
        client.execution_gate.functions.executeSwap(
            _b32(delegation_id),
            client._encode_tx_params(tx_params),
        )
    )
