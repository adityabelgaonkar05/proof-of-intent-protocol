"""
Smoke tests for ContractClient and the error/Scope types.

Tests that require a live RPC call are marked with @pytest.mark.live and
are skipped unless PRIVATE_KEY is set in the environment.

Run all tests:
    pytest                        # skips live tests if PRIVATE_KEY absent
    PRIVATE_KEY=0x... pytest      # runs everything
"""
import os

import pytest
from web3 import Web3

from proof_of_intent import ContractClient, Scope, UNISWAP_V3
from proof_of_intent.errors import (
    POIPError,
    TransactionRevertError,
    ScopeViolationError,
    DeadlineExpiredError,
)
from proof_of_intent._defaults import (
    DEFAULT_CHAIN_ID,
    DEFAULT_RPC_URL,
    DEFAULT_AGENT_REGISTRY,
    DEFAULT_INTENT_REGISTRY,
    DEFAULT_DELEGATION_REGISTRY,
    DEFAULT_EXECUTION_GATE,
)

# Hardhat/Foundry deterministic test key — safe to commit, never use on mainnet.
_TEST_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
_TEST_ADDR = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

_LIVE_KEY = os.getenv("PRIVATE_KEY")
live = pytest.mark.skipif(not _LIVE_KEY, reason="PRIVATE_KEY not set")


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------

class TestErrors:
    def test_scope_violation_is_transaction_revert(self):
        assert issubclass(ScopeViolationError, TransactionRevertError)

    def test_deadline_expired_is_transaction_revert(self):
        assert issubclass(DeadlineExpiredError, TransactionRevertError)

    def test_transaction_revert_is_poip(self):
        assert issubclass(TransactionRevertError, POIPError)

    def test_poip_is_exception(self):
        assert issubclass(POIPError, Exception)

    def test_revert_carries_reason(self):
        err = TransactionRevertError("ScopeExceeded")
        assert err.reason == "ScopeExceeded"
        assert str(err) == "ScopeExceeded"


# ---------------------------------------------------------------------------
# Scope dataclass
# ---------------------------------------------------------------------------

class TestScope:
    def test_to_dict_fields(self):
        scope = Scope(
            max_amount_in=500_000_000,
            min_amount_out=1,
            allowed_protocols=["Uniswap-V3"],
            deadline=9_999_999_999,
        )
        d = scope.to_dict()
        assert d["maxAmountIn"] == 500_000_000
        assert d["minAmountOut"] == 1
        assert d["deadline"] == 9_999_999_999
        assert len(d["allowedProtocols"]) == 1

    def test_protocol_hashed_correctly(self):
        scope = Scope(
            max_amount_in=1, min_amount_out=0,
            allowed_protocols=["Uniswap-V3"],
            deadline=1,
        )
        d = scope.to_dict()
        assert d["allowedProtocols"][0] == UNISWAP_V3.hex()

    def test_multiple_protocols(self):
        from proof_of_intent import CURVE
        scope = Scope(1, 0, ["Uniswap-V3", "Curve"], 1)
        d = scope.to_dict()
        assert len(d["allowedProtocols"]) == 2
        assert d["allowedProtocols"][0] == UNISWAP_V3.hex()
        assert d["allowedProtocols"][1] == CURVE.hex()


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_rpc_url_is_sepolia(self):
        assert "sepolia" in DEFAULT_RPC_URL.lower()

    def test_chain_id_is_sepolia(self):
        assert DEFAULT_CHAIN_ID == 11155111

    def test_contract_addresses_are_checksummed(self):
        for addr in [
            DEFAULT_AGENT_REGISTRY,
            DEFAULT_INTENT_REGISTRY,
            DEFAULT_DELEGATION_REGISTRY,
            DEFAULT_EXECUTION_GATE,
        ]:
            assert Web3.is_checksum_address(addr)


# ---------------------------------------------------------------------------
# ContractClient instantiation (no network calls)
# ---------------------------------------------------------------------------

class TestContractClientInstantiation:
    def test_derives_address_from_key(self):
        c = ContractClient(private_key=_TEST_KEY)
        assert c.account.address == _TEST_ADDR

    def test_default_chain_id(self):
        c = ContractClient(private_key=_TEST_KEY)
        assert c._chain_id == DEFAULT_CHAIN_ID

    def test_chain_id_override(self):
        c = ContractClient(private_key=_TEST_KEY, chain_id=1)
        assert c._chain_id == 1

    def test_keyword_only_private_key(self):
        c = ContractClient(private_key=_TEST_KEY)
        assert c.account.address == _TEST_ADDR

    def test_contracts_bound_to_correct_addresses(self):
        c = ContractClient(private_key=_TEST_KEY)
        assert c.agent_registry.address == DEFAULT_AGENT_REGISTRY
        assert c.intent_registry.address == DEFAULT_INTENT_REGISTRY
        assert c.delegation_registry.address == DEFAULT_DELEGATION_REGISTRY
        assert c.execution_gate.address == DEFAULT_EXECUTION_GATE


# ---------------------------------------------------------------------------
# Live tests (require PRIVATE_KEY and a live Sepolia RPC)
# ---------------------------------------------------------------------------

class TestContractClientLive:
    @live
    def test_derives_address_from_env_key(self):
        c = ContractClient(private_key=_LIVE_KEY)
        assert Web3.is_checksum_address(c.account.address)

    @live
    def test_verify_chain_no_env_var_error(self):
        """verify_chain() reaches the chain without missing-env-var errors."""
        c = ContractClient(private_key=_LIVE_KEY)
        zero_id = "0x" + "00" * 32
        tx_params = {
            "amountIn":     0,
            "minAmountOut": 0,
            "protocol":     "0x" + "00" * 32,
            "tokenIn":      "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
            "tokenOut":     "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14",
            "recipient":    c.account.address,
        }
        try:
            result = c.verify_chain(zero_id, tx_params)
            assert isinstance(result, bool)
        except Exception as exc:
            msg = str(exc).lower()
            assert "environment variable" not in msg, f"env-var leak: {exc}"
