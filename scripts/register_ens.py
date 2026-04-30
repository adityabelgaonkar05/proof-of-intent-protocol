"""
Register an ENS name on Ethereum Sepolia via direct web3.py contract calls.

Flow: check availability → makeCommitment → commit → wait 60s → register → verify

Usage:
    python scripts/register_ens.py [name]   # default: poip
"""
import os, sys, time, secrets, pathlib

_proj = pathlib.Path(__file__).parent.parent
if str(_proj) not in sys.path:
    sys.path.insert(0, str(_proj))

from dotenv import load_dotenv
load_dotenv(_proj / ".env")

from web3 import Web3
from eth_account import Account

# ── Config ─────────────────────────────────────────────────────────────────
RPC_URL     = os.getenv("RPC_URL", "https://ethereum-sepolia-rpc.publicnode.com")
CHAIN_ID    = int(os.getenv("CHAIN_ID", "11155111"))
PRIVATE_KEY = os.environ["USER_PRIVATE_KEY"]

ENS_NAME_ARG  = sys.argv[1] if len(sys.argv) > 1 else "poip"

# Sepolia contract addresses (verified on-chain)
ETH_REGISTRAR_CONTROLLER = Web3.to_checksum_address("0xfb3cE5D01e0f33f41DbB39035dB9745962F1f968")
ENS_REGISTRY             = Web3.to_checksum_address("0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e")
PUBLIC_RESOLVER          = Web3.to_checksum_address("0x8FADE66B79cC9f707aB26799354482EB93a5B7dD")

REGISTRATION_DURATION = 365 * 24 * 3600  # 1 year in seconds

# Struct: (string,address,uint256,bytes32,address,bytes[],uint8,bytes32)
REQUEST_COMPONENTS = [
    {"name": "name",               "type": "string"},
    {"name": "owner",              "type": "address"},
    {"name": "duration",           "type": "uint256"},
    {"name": "secret",             "type": "bytes32"},
    {"name": "resolver",           "type": "address"},
    {"name": "data",               "type": "bytes[]"},
    {"name": "reverseRecord",      "type": "uint8"},
    {"name": "ownerControlledFuses","type": "bytes32"},
]

CONTROLLER_ABI = [
    {
        "name": "available",
        "type": "function",
        "inputs":  [{"name": "name", "type": "string"}],
        "outputs": [{"type": "bool"}],
        "stateMutability": "view",
    },
    {
        "name": "rentPrice",
        "type": "function",
        "inputs": [
            {"name": "name", "type": "string"},
            {"name": "duration", "type": "uint256"},
        ],
        "outputs": [{"type": "tuple", "components": [
            {"name": "base",    "type": "uint256"},
            {"name": "premium", "type": "uint256"},
        ]}],
        "stateMutability": "view",
    },
    {
        "name": "makeCommitment",
        "type": "function",
        "inputs": [{"name": "request", "type": "tuple", "components": REQUEST_COMPONENTS}],
        "outputs": [{"type": "bytes32"}],
        "stateMutability": "pure",
    },
    {
        "name": "commit",
        "type": "function",
        "inputs": [{"name": "commitment", "type": "bytes32"}],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "name": "register",
        "type": "function",
        "inputs": [{"name": "request", "type": "tuple", "components": REQUEST_COMPONENTS}],
        "outputs": [],
        "stateMutability": "payable",
    },
    {
        "name": "minCommitmentAge",
        "type": "function",
        "inputs": [],
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "name": "commitments",
        "type": "function",
        "inputs": [{"name": "commitment", "type": "bytes32"}],
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
    },
]

REGISTRY_ABI = [
    {
        "name": "owner",
        "type": "function",
        "inputs": [{"name": "node", "type": "bytes32"}],
        "outputs": [{"type": "address"}],
        "stateMutability": "view",
    },
]


def namehash(name: str) -> bytes:
    node = b"\x00" * 32
    if name:
        for label in reversed(name.split(".")):
            node = Web3.keccak(node + Web3.keccak(text=label))
    return node


def send_tx(w3: Web3, account, contract_fn, value_wei: int = 0) -> str:
    gas = contract_fn.estimate_gas({"from": account.address, "value": value_wei})
    tx = contract_fn.build_transaction({
        "from":    account.address,
        "nonce":   w3.eth.get_transaction_count(account.address),
        "chainId": CHAIN_ID,
        "gas":     gas,
        "value":   value_wei,
    })
    signed  = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
    if receipt.status == 0:
        raise RuntimeError(f"Transaction reverted: 0x{tx_hash.hex()}")
    return "0x" + tx_hash.hex()


def main():
    label = ENS_NAME_ARG.lower().strip()
    full_name = f"{label}.eth"

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to RPC: {RPC_URL}")

    account  = Account.from_key(PRIVATE_KEY)
    ctrl     = w3.eth.contract(address=ETH_REGISTRAR_CONTROLLER, abi=CONTROLLER_ABI)
    registry = w3.eth.contract(address=ENS_REGISTRY, abi=REGISTRY_ABI)

    balance = w3.eth.get_balance(account.address)
    print(f"Wallet:  {account.address}")
    print(f"Balance: {balance / 1e18:.6f} ETH")

    # ── Step 1: Check availability ──────────────────────────────────────────
    print(f"\n[1/5] Checking availability of '{full_name}' ...")
    if not ctrl.functions.available(label).call():
        print(f"  '{full_name}' is already registered.")
        # Verify owner
        node  = namehash(full_name)
        owner = registry.functions.owner(node).call()
        print(f"  Current owner: {owner}")
        return

    price = ctrl.functions.rentPrice(label, REGISTRATION_DURATION).call()
    total_wei = price[0] + price[1]
    print(f"  Available! Price: {total_wei / 1e18:.6f} ETH/year")

    if balance < total_wei + w3.to_wei(0.005, "ether"):
        raise RuntimeError(
            f"Insufficient balance ({balance / 1e18:.6f} ETH) "
            f"for registration ({total_wei / 1e18:.6f} ETH + gas)"
        )

    # ── Step 2: Generate secret ─────────────────────────────────────────────
    secret = secrets.token_bytes(32)
    print(f"\n[2/5] Secret: 0x{secret.hex()}")

    request = (
        label,
        account.address,
        REGISTRATION_DURATION,
        secret,
        PUBLIC_RESOLVER,
        [],          # no additional setup data
        0,           # reverseRecord = false
        b"\x00" * 32,  # ownerControlledFuses = 0
    )

    # ── Step 3: makeCommitment + commit ─────────────────────────────────────
    print("\n[3/5] Making commitment ...")
    commitment = ctrl.functions.makeCommitment(request).call()
    print(f"  Commitment: 0x{commitment.hex()}")

    tx_hash = send_tx(w3, account, ctrl.functions.commit(commitment))
    print(f"  commit() tx: {tx_hash}")

    # ── Step 4: Wait for minCommitmentAge ───────────────────────────────────
    min_age = ctrl.functions.minCommitmentAge().call()
    print(f"\n[4/5] Waiting {min_age}s for commitment to mature ...")

    deadline = time.time() + min_age + 5
    while time.time() < deadline:
        remaining = deadline - time.time()
        print(f"  {remaining:.0f}s remaining ...", end="\r", flush=True)
        time.sleep(5)

    # Confirm commitment is on-chain
    committed_at = ctrl.functions.commitments(commitment).call()
    if committed_at == 0:
        raise RuntimeError("Commitment not found on-chain — commit tx may not have mined yet")
    print(f"\n  Commitment confirmed at timestamp {committed_at}")

    # ── Step 5: Register ────────────────────────────────────────────────────
    print("\n[5/5] Registering ...")
    # Use 110% of price as value to cover any small fluctuation
    value = total_wei * 11 // 10
    tx_hash = send_tx(w3, account, ctrl.functions.register(request), value_wei=value)
    print(f"  register() tx: {tx_hash}")

    # ── Verify ──────────────────────────────────────────────────────────────
    node  = namehash(full_name)
    owner = registry.functions.owner(node).call()
    print(f"\nRegistered '{full_name}'")
    print(f"Owner:  {owner}")
    print(f"Match:  {owner.lower() == account.address.lower()}")
    print(f"\nAdd to .env:  ENS_NAME={full_name}")


if __name__ == "__main__":
    main()
