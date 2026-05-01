import json
import time

from eth_account import Account
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ContractLogicError
from web3.types import TxReceipt

from config.config import (
    RPC_URL,
    CHAIN_ID,
    AGENT_REGISTRY_ADDRESS,
    INTENT_REGISTRY_ADDRESS,
    DELEGATION_REGISTRY_ADDRESS,
    EXECUTION_GATE_ADDRESS,
    AGENT_REGISTRY_ABI,
    INTENT_REGISTRY_ABI,
    DELEGATION_REGISTRY_ABI,
    EXECUTION_GATE_ABI,
    ZG_API_KEY,
    ZG_RPC_URL,
    ZG_INDEXER_URL,
    ENS_NAME,
    ENS_RESOLVER_ADDRESS,
    ENS_REGISTRY_ADDRESS,
    ENS_PUBLIC_RESOLVER_ABI,
)

# Minimal ERC20 ABI — only the functions needed for approve/allowance checks.
_ERC20_ABI = [
    {
        "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
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


class TransactionRevertError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class ContractClient:
    def __init__(self, private_key: str):
        self._private_key = private_key
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to RPC: {RPC_URL}")
        self.account = Account.from_key(private_key)
        self.agent_registry = self.w3.eth.contract(
            address=Web3.to_checksum_address(AGENT_REGISTRY_ADDRESS),
            abi=AGENT_REGISTRY_ABI,
        )
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
        try:
            gas = contract_function.estimate_gas({"from": self.account.address})
        except ContractLogicError as exc:
            raise TransactionRevertError(_extract_revert_reason(exc)) from exc
        tx = contract_function.build_transaction({
            "from": self.account.address,
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "chainId": CHAIN_ID,
            "gas": gas,
        })
        signed = self.account.sign_transaction(tx)
        try:
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        except ContractLogicError as exc:
            raise TransactionRevertError(_extract_revert_reason(exc)) from exc
        if receipt.status == 0:
            raise TransactionRevertError("Transaction reverted")
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
        intent_id = "0x" + logs[0]["args"]["intentId"].hex()

        # Non-blocking: store on 0G and ENS; failures are warnings only.
        self.store_intent_on_0g(intent, intent_id)
        self.store_intent_on_ens(intent_id, ENS_NAME)

        return intent_id

    def store_intent_on_0g(self, intent: dict, intent_id: str) -> str | None:
        """
        Store the intent as a JSON blob on 0G decentralised storage.

        Returns the rootHash reference on success, None on any failure.
        Failure is always non-blocking: errors are printed as warnings.
        """
        if not ZG_API_KEY:
            print("0G storage skipped: ZG_API_KEY not set.")
            return None

        # The 0g-sdk's top-level packages (`core`, `utils`, `config`) conflict
        # with our project's own packages of the same names. Importing from
        # `core` in-process fails because our `utils` and `config` shadow the
        # SDK's own copies. Run the upload in a subprocess with the project root
        # stripped from PYTHONPATH so the 0g-sdk resolves its own namespaces.
        import subprocess as _sp, sys as _sys, pathlib as _pl
        _helper = _pl.Path(__file__).parent.parent / "scripts" / "zg_upload.py"
        if not _helper.exists():
            print("Warning [0G]: upload helper script not found.")
            return None

        try:
            metadata = {
                "intentId": intent_id,
                "owner": intent.get("owner", ""),
                "maxAmountIn": intent.get("maxAmountIn", 0),
                "minAmountOut": intent.get("minAmountOut", 0),
                "allowedProtocols": [
                    p.hex() if isinstance(p, (bytes, bytearray)) else p
                    for p in intent.get("allowedProtocols", [])
                ],
                "deadline": intent.get("deadline", 0),
                "timestamp": int(time.time()),
            }
            payload = json.dumps(metadata, separators=(",", ":")).encode()

            # Build a clean env: venv Python but without the project root on PYTHONPATH.
            _env = {k: v for k, v in __import__("os").environ.items()}
            _env.pop("PYTHONPATH", None)

            _proc = _sp.run(
                [_sys.executable, str(_helper), ZG_API_KEY, ZG_RPC_URL, ZG_INDEXER_URL],
                input=payload,
                capture_output=True,
                env=_env,
                timeout=120,
            )
            _out = _proc.stdout.decode().strip()
            if _out.startswith("ERROR:") or _proc.returncode != 0:
                _err = _out[6:] if _out.startswith("ERROR:") else (_proc.stderr.decode().strip() or _out)
                print(f"Warning [0G]: upload failed — {_err}")
                return None

            ref = _out
            print(f"Intent stored on 0G: {ref}")
            return ref

        except Exception as exc:
            print(f"Warning [0G]: {exc}")
            return None

    def store_intent_on_ens(self, intent_id: str, ens_name: str) -> None:
        """
        Write intent_id as the "active-intent" text record on the ENS name.

        Non-blocking: prints a warning on any failure.
        Skipped silently when ENS_NAME is not configured.
        """
        if not ens_name:
            return

        try:
            node = self._ens_namehash(ens_name)

            # Look up the resolver the ENS registry has on file for this name.
            # Fall back to the hardcoded default if the registry returns zero.
            _registry = self.w3.eth.contract(
                address=Web3.to_checksum_address(ENS_REGISTRY_ADDRESS),
                abi=[{
                    "inputs": [{"type": "bytes32", "name": "node"}],
                    "name": "resolver",
                    "outputs": [{"type": "address"}],
                    "stateMutability": "view",
                    "type": "function",
                }],
            )
            _zero = "0x0000000000000000000000000000000000000000"
            _resolver_addr = _registry.functions.resolver(node).call()
            if _resolver_addr == _zero:
                _resolver_addr = ENS_RESOLVER_ADDRESS

            resolver = self.w3.eth.contract(
                address=Web3.to_checksum_address(_resolver_addr),
                abi=ENS_PUBLIC_RESOLVER_ABI,
            )
            self._send_tx_receipt(
                resolver.functions.setText(node, "active-intent", intent_id)
            )
            print(f"Intent linked to {ens_name} on ENS")
        except Exception as exc:
            print(f"Warning [ENS]: {exc}")

    @staticmethod
    def _ens_namehash(name: str) -> bytes:
        """Compute the ENS namehash (EIP-137) for a domain name."""
        node = b"\x00" * 32
        if name:
            for label in reversed(name.split(".")):
                label_hash = Web3.keccak(text=label)
                node = Web3.keccak(node + label_hash)
        return node

    def ensure_token_approval(self, token_address: str, spender: str, amount: int) -> None:
        """Approve `spender` to spend `amount` of `token_address` on behalf of this account.

        Checks the current allowance first and only sends an approval tx if it is
        insufficient, avoiding unnecessary gas spend.
        """
        token = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=_ERC20_ABI,
        )
        current = token.functions.allowance(
            self.account.address,
            Web3.to_checksum_address(spender),
        ).call()
        if current < amount:
            self._send_tx_receipt(
                token.functions.approve(
                    Web3.to_checksum_address(spender),
                    amount,
                )
            )

    def token_balance(self, token_address: str, account: str) -> int:
        """Return the ERC20 balance of `account` for the given token."""
        token = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=_ERC20_ABI,
        )
        return token.functions.balanceOf(Web3.to_checksum_address(account)).call()

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
    # High-level convenience methods
    # ------------------------------------------------------------------

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
        """Build, sign, and register an intent in one call. Returns intentId.

        :param token_in:          ERC20 address to swap from (e.g. USDC_ADDRESS).
        :param max_amount_in:     Max spend in raw units — use usdc(500) or weth(0.15).
        :param min_amount_out:    Minimum acceptable output in raw units.
        :param allowed_protocols: Protocol names e.g. ["Uniswap-V3"]. Hashed automatically.
        :param deadline:          Unix timestamp. Use in_minutes(60) for 1 hour from now.
        :param orchestrator:      Address authorised to create the first delegation.
                                  Defaults to this wallet.
        :param owner:             Intent owner. Defaults to this wallet.
        """
        from utils.sign_intent import build_intent as _build, sign_intent as _sign  # noqa: PLC0415
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
        signature = _sign(intent, self._private_key)
        return self.register_intent(intent, signature)

    @staticmethod
    def build_scope(
        max_amount_in: int,
        min_amount_out: int,
        allowed_protocols: list[str],
        deadline: int,
    ) -> dict:
        """Build a scope dict with protocol names hashed to bytes32 automatically.

        Pass the result directly to delegate_from_root() or delegate_from_delegation().

        :param max_amount_in:     Max spend in raw units — use usdc(500) etc.
        :param min_amount_out:    Minimum output in raw units.
        :param allowed_protocols: Protocol names e.g. ["Uniswap-V3"]. Hashed automatically.
        :param deadline:          Unix timestamp.
        """
        return {
            "maxAmountIn":      max_amount_in,
            "minAmountOut":     min_amount_out,
            "allowedProtocols": [Web3.keccak(text=p).hex() for p in allowed_protocols],
            "deadline":         deadline,
        }

    def register_agent(
        self,
        agent_address: str,
        name: str,
        skip_if_active: bool = True,
    ) -> str | None:
        """Register an address in AgentRegistry so it can receive delegations.

        :param agent_address: Ethereum address to register.
        :param name:          Human-readable label stored on-chain.
        :param skip_if_active: When True (default), returns None without a tx if
                               the address is already registered and active.
        """
        addr = Web3.to_checksum_address(agent_address)
        if skip_if_active and self.agent_registry.functions.isActiveAgent(addr).call():
            return None
        return self.send_tx(
            self.agent_registry.functions.registerAgent(addr, name)
        )

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
