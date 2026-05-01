"""
ContractClient — the main SDK entry point.

    from proof_of_intent import ContractClient
    client = ContractClient(private_key=os.environ["PRIVATE_KEY"])
"""
from __future__ import annotations

import dataclasses
import time

from eth_account import Account
from web3 import Web3
from web3.exceptions import ContractLogicError
from web3.types import TxReceipt

from ._defaults import (
    DEFAULT_RPC_URL,
    DEFAULT_CHAIN_ID,
    DEFAULT_AGENT_REGISTRY,
    DEFAULT_INTENT_REGISTRY,
    DEFAULT_DELEGATION_REGISTRY,
    DEFAULT_EXECUTION_GATE,
    AGENT_REGISTRY_ABI,
    INTENT_REGISTRY_ABI,
    DELEGATION_REGISTRY_ABI,
    EXECUTION_GATE_ABI,
    ENS_RESOLVER_ADDRESS,
    ENS_REGISTRY_ADDRESS,
)
from .errors import classify_revert, TransactionRevertError

_ERC20_ABI = [
    {"inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
     "name": "allowance", "outputs": [{"name": "", "type": "uint256"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
     "name": "approve", "outputs": [{"name": "", "type": "bool"}],
     "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "account", "type": "address"}],
     "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}],
     "stateMutability": "view", "type": "function"},
]

_ENS_REGISTRY_ABI = [
    {"inputs": [{"type": "bytes32", "name": "node"}], "name": "resolver",
     "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
]

_ENS_RESOLVER_ABI = [
    {"inputs": [{"type": "bytes32", "name": "node"}, {"type": "string", "name": "key"},
                {"type": "string", "name": "value"}],
     "name": "setText", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
]


def _strip(hex_str: str) -> str:
    return hex_str[2:] if hex_str.startswith("0x") else hex_str


def _b32(value) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return bytes.fromhex(_strip(value))


def _extract_revert_reason(exc: Exception) -> str:
    message = str(exc)
    if "execution reverted:" in message:
        reason = message.split("execution reverted:", 1)[1].strip()
        for suffix in ("', '", '", "', "')", '")', "',)", '",)'):
            if suffix in reason:
                reason = reason.split(suffix, 1)[0]
                break
        return reason.strip(" '\"")
    return message


@dataclasses.dataclass
class Scope:
    """Parameters for a delegation scope.

    Pass directly to ContractClient.delegate_from_root() or
    ContractClient.delegate_from_delegation().

    Protocol names (e.g. "Uniswap-V3") are hashed to bytes32 automatically
    when the scope is serialised for the contract call.
    """
    max_amount_in: int
    min_amount_out: int
    allowed_protocols: list[str]
    deadline: int

    def to_dict(self) -> dict:
        return {
            "maxAmountIn":      self.max_amount_in,
            "minAmountOut":     self.min_amount_out,
            "allowedProtocols": [Web3.keccak(text=p).hex() for p in self.allowed_protocols],
            "deadline":         self.deadline,
        }


class ContractClient:
    """Client for the Proof-of-Intent protocol contracts on Ethereum Sepolia.

    All constructor parameters except *private_key* have sensible Sepolia
    defaults so a minimal instantiation only requires the wallet key:

        client = ContractClient(private_key=os.environ["PRIVATE_KEY"])
    """

    def __init__(
        self,
        private_key: str,
        *,
        rpc_url: str = DEFAULT_RPC_URL,
        chain_id: int = DEFAULT_CHAIN_ID,
        agent_registry_address: str = DEFAULT_AGENT_REGISTRY,
        intent_registry_address: str = DEFAULT_INTENT_REGISTRY,
        delegation_registry_address: str = DEFAULT_DELEGATION_REGISTRY,
        execution_gate_address: str = DEFAULT_EXECUTION_GATE,
        ens_name: str = "",
        zg_api_key: str = "",
    ) -> None:
        self._private_key = private_key
        self._chain_id = chain_id
        self._ens_name = ens_name
        self._zg_api_key = zg_api_key

        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            from .errors import ConnectionError as _CE
            raise _CE(f"Cannot connect to RPC: {rpc_url}")
        self.account = Account.from_key(private_key)

        self.agent_registry = self.w3.eth.contract(
            address=Web3.to_checksum_address(agent_registry_address),
            abi=AGENT_REGISTRY_ABI,
        )
        self.intent_registry = self.w3.eth.contract(
            address=Web3.to_checksum_address(intent_registry_address),
            abi=INTENT_REGISTRY_ABI,
        )
        self.delegation_registry = self.w3.eth.contract(
            address=Web3.to_checksum_address(delegation_registry_address),
            abi=DELEGATION_REGISTRY_ABI,
        )
        self.execution_gate = self.w3.eth.contract(
            address=Web3.to_checksum_address(execution_gate_address),
            abi=EXECUTION_GATE_ABI,
        )

    # ------------------------------------------------------------------
    # Transaction primitives
    # ------------------------------------------------------------------

    def _send_tx_receipt(self, contract_function) -> TxReceipt:
        try:
            gas = contract_function.estimate_gas({"from": self.account.address})
        except ContractLogicError as exc:
            raise classify_revert(_extract_revert_reason(exc)) from exc
        tx = contract_function.build_transaction({
            "from":    self.account.address,
            "nonce":   self.w3.eth.get_transaction_count(self.account.address),
            "chainId": self._chain_id,
            "gas":     gas,
        })
        signed = self.account.sign_transaction(tx)
        try:
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        except ContractLogicError as exc:
            raise classify_revert(_extract_revert_reason(exc)) from exc
        if receipt.status == 0:
            raise TransactionRevertError("Transaction reverted")
        return receipt

    def send_tx(self, contract_function) -> str:
        return self._send_tx_receipt(contract_function)["transactionHash"].hex()

    # ------------------------------------------------------------------
    # Intent registration
    # ------------------------------------------------------------------

    def register_intent(self, intent: dict, signature: str) -> str:
        """Register a pre-built and pre-signed intent. Returns intentId."""
        sig_bytes = bytes.fromhex(_strip(signature))
        receipt = self._send_tx_receipt(
            self.intent_registry.functions.registerIntent(
                self._encode_intent(intent), sig_bytes
            )
        )
        logs = self.intent_registry.events.IntentRegistered().process_receipt(receipt)
        if not logs:
            raise ValueError("IntentRegistered event not found in receipt")
        intent_id = "0x" + logs[0]["args"]["intentId"].hex()
        self._store_intent_on_ens(intent_id, self._ens_name)
        return intent_id

    def create_intent(
        self,
        token_in: str,
        max_amount_in: int,
        min_amount_out: int,
        allowed_protocols: list[str],
        deadline: int,
        orchestrator: str | None = None,
        owner: str | None = None,
    ) -> str:
        """Build, sign, and register an intent in one call. Returns intentId."""
        from ._sign import build_intent as _build, sign_intent as _sign  # noqa: PLC0415
        _owner = owner or self.account.address
        _orch  = orchestrator or self.account.address
        nonce  = self.intent_registry.functions.nonces(
            Web3.to_checksum_address(_owner)
        ).call()
        intent = _build(
            owner=_owner,
            authorized_orchestrator=_orch,
            token_in=token_in,
            max_amount_in=max_amount_in,
            min_amount_out=min_amount_out,
            allowed_protocols=allowed_protocols,
            deadline=deadline,
            nonce=nonce,
        )
        signature = _sign(
            intent,
            self._private_key,
            chain_id=self._chain_id,
            intent_registry=self.intent_registry.address,
        )
        return self.register_intent(intent, signature)

    # ------------------------------------------------------------------
    # Delegation
    # ------------------------------------------------------------------

    def delegate_from_root(
        self,
        root_intent_id: str,
        child_scope: "dict | Scope",
        delegate_to: str,
    ) -> str:
        """Create the first delegation from a root intent. Returns delegationId."""
        scope_dict = child_scope.to_dict() if isinstance(child_scope, Scope) else child_scope
        receipt = self._send_tx_receipt(
            self.delegation_registry.functions.delegateFromRoot(
                _b32(root_intent_id),
                self._encode_scope(scope_dict),
                Web3.to_checksum_address(delegate_to),
            )
        )
        return self._extract_delegation_id(receipt)

    def delegate_from_delegation(
        self,
        parent_delegation_id: str,
        child_scope: "dict | Scope",
        delegate_to: str,
    ) -> str:
        """Create a sub-delegation from an existing delegation. Returns delegationId."""
        scope_dict = child_scope.to_dict() if isinstance(child_scope, Scope) else child_scope
        receipt = self._send_tx_receipt(
            self.delegation_registry.functions.delegateFromDelegation(
                _b32(parent_delegation_id),
                self._encode_scope(scope_dict),
                Web3.to_checksum_address(delegate_to),
            )
        )
        return self._extract_delegation_id(receipt)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute_swap(self, delegation_id: str, tx_params: dict) -> str:
        """Execute a swap via the ExecutionGate. Returns tx hash."""
        return self.send_tx(
            self.execution_gate.functions.executeSwap(
                _b32(delegation_id),
                self._encode_tx_params(tx_params),
            )
        )

    def verify_chain(self, delegation_id: str, tx_params: dict) -> bool:
        """View-call to check whether the delegation chain is valid."""
        return self.execution_gate.functions.verifyChain(
            _b32(delegation_id),
            self._encode_tx_params(tx_params),
        ).call()

    # ------------------------------------------------------------------
    # Agent registry
    # ------------------------------------------------------------------

    def register_agent(
        self,
        agent_address: str,
        name: str,
        skip_if_active: bool = True,
    ) -> str | None:
        addr = Web3.to_checksum_address(agent_address)
        if skip_if_active and self.agent_registry.functions.isActiveAgent(addr).call():
            return None
        return self.send_tx(self.agent_registry.functions.registerAgent(addr, name))

    # ------------------------------------------------------------------
    # ERC-20 helpers
    # ------------------------------------------------------------------

    def ensure_token_approval(self, token_address: str, spender: str, amount: int) -> None:
        tok = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address), abi=_ERC20_ABI
        )
        current = tok.functions.allowance(
            self.account.address, Web3.to_checksum_address(spender)
        ).call()
        if current < amount:
            self._send_tx_receipt(
                tok.functions.approve(Web3.to_checksum_address(spender), amount)
            )

    def token_balance(self, token_address: str, account: str) -> int:
        tok = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address), abi=_ERC20_ABI
        )
        return tok.functions.balanceOf(Web3.to_checksum_address(account)).call()

    # ------------------------------------------------------------------
    # Scope builder (static convenience)
    # ------------------------------------------------------------------

    @staticmethod
    def build_scope(
        max_amount_in: int,
        min_amount_out: int,
        allowed_protocols: list[str],
        deadline: int,
    ) -> dict:
        return {
            "maxAmountIn":      max_amount_in,
            "minAmountOut":     min_amount_out,
            "allowedProtocols": [Web3.keccak(text=p).hex() for p in allowed_protocols],
            "deadline":         deadline,
        }

    # ------------------------------------------------------------------
    # ENS (non-blocking, optional)
    # ------------------------------------------------------------------

    def _store_intent_on_ens(self, intent_id: str, ens_name: str) -> None:
        if not ens_name:
            return
        try:
            node = self._ens_namehash(ens_name)
            _reg = self.w3.eth.contract(
                address=Web3.to_checksum_address(ENS_REGISTRY_ADDRESS),
                abi=_ENS_REGISTRY_ABI,
            )
            _zero = "0x0000000000000000000000000000000000000000"
            _resolver_addr = _reg.functions.resolver(node).call()
            if _resolver_addr == _zero:
                _resolver_addr = ENS_RESOLVER_ADDRESS
            resolver = self.w3.eth.contract(
                address=Web3.to_checksum_address(_resolver_addr),
                abi=_ENS_RESOLVER_ABI,
            )
            self._send_tx_receipt(
                resolver.functions.setText(node, "active-intent", intent_id)
            )
            print(f"Intent linked to {ens_name} on ENS")
        except Exception as exc:
            print(f"Warning [ENS]: {exc}")

    @staticmethod
    def _ens_namehash(name: str) -> bytes:
        node = b"\x00" * 32
        if name:
            for label in reversed(name.split(".")):
                node = Web3.keccak(node + Web3.keccak(text=label))
        return node

    # ------------------------------------------------------------------
    # Internal struct encoders
    # ------------------------------------------------------------------

    def _encode_intent(self, intent: dict) -> tuple:
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
