"""End-to-end verification: Steps 2-10 of the system check."""
import os, time, sys, traceback
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv
load_dotenv()

from config.config import (
    RPC_URL, CHAIN_ID, USDC_ADDRESS, WETH_ADDRESS,
    AGENT_REGISTRY_ADDRESS, INTENT_REGISTRY_ADDRESS,
    DELEGATION_REGISTRY_ADDRESS, EXECUTION_GATE_ADDRESS,
    AGENT_REGISTRY_ABI,
)
from utils.contract_client import ContractClient
from utils.sign_intent import build_intent, sign_intent

DEPLOYER_PK = os.environ["DEPLOYER_PRIVATE_KEY"]
USER_PK     = os.environ["USER_PRIVATE_KEY"]
ORCH_PK     = os.environ["ORCHESTRATOR_PRIVATE_KEY"]
RES_PK      = os.environ["RESEARCH_PRIVATE_KEY"]
EXEC_PK     = os.environ["EXECUTION_PRIVATE_KEY"]

ORCH_ADDR = os.environ["ORCHESTRATOR_ADDRESS"]
RES_ADDR  = os.environ["RESEARCH_ADDRESS"]
EXEC_ADDR = os.environ["EXECUTION_ADDRESS"]
USER_ADDR = Account.from_key(USER_PK).address

UNI = Web3.keccak(text="Uniswap-V3").hex()
results = {}

def banner(s):
    print(f"\n{'='*60}\n{s}\n{'='*60}")

def revert_reason(e):
    msg = str(e)
    if "execution reverted:" in msg:
        return msg.split("execution reverted:")[-1].strip().strip("'\"")
    return msg

w3 = Web3(Web3.HTTPProvider(RPC_URL))
user = ContractClient(USER_PK)
orch = ContractClient(ORCH_PK)
res  = ContractClient(RES_PK)
ex   = ContractClient(EXEC_PK)
deployer = ContractClient(DEPLOYER_PK)

# ---------------- STEP 2 ----------------
banner("STEP 2 — Contract state verification")
ok = True
for name, addr in [("agentRegistry",AGENT_REGISTRY_ADDRESS),("intentRegistry",INTENT_REGISTRY_ADDRESS),
                   ("delegationRegistry",DELEGATION_REGISTRY_ADDRESS),("executionGate",EXECUTION_GATE_ADDRESS)]:
    code = w3.eth.get_code(Web3.to_checksum_address(addr))
    print(f"  {name:20s} {addr}  code={'present' if len(code)>2 else 'MISSING'}")
    if len(code)<=2: ok=False

ar = user.agent_registry
for name, addr in [("ORCH",ORCH_ADDR),("RES",RES_ADDR),("EXEC",EXEC_ADDR)]:
    active = ar.functions.isActiveAgent(Web3.to_checksum_address(addr)).call()
    print(f"  {name} active: {active}")
    if not active:
        print(f"  Registering {name}...")
        deployer.send_tx(deployer.agent_registry.functions.registerAgent(Web3.to_checksum_address(addr), name))
        active = ar.functions.isActiveAgent(Web3.to_checksum_address(addr)).call()
        print(f"  {name} active after register: {active}")
    if not active: ok=False

print("\n  Wallet balances:")
for n,a in [("USER",USER_ADDR),("ORCH",ORCH_ADDR),("RES",RES_ADDR),("EXEC",EXEC_ADDR)]:
    bal = w3.eth.get_balance(Web3.to_checksum_address(a))
    eth = Web3.from_wei(bal,"ether")
    flag = "" if bal >= w3.to_wei(0.01,"ether") else "  (LOW — please fund)"
    print(f"    {n:5s} {a}  {eth:.6f} ETH{flag}")

results["STEP 2"] = "PASS" if ok else "FAIL"
print(f"\nSTEP 2: {results['STEP 2']}")

# ---------------- STEP 3 ----------------
banner("STEP 3 — Intent compiler")
from agents.compiler import compile_intent
from config.config import USE_CLAUDE
provider = "Claude" if USE_CLAUDE else "OpenAI"
print(f"  Provider: {provider}")
prompt = "swap maximum 300 USDC to ETH, only use Uniswap-V3, get at least 0.12 ETH, valid for 45 minutes"

def validate(out):
    return (out.get("maxAmountIn")==300_000_000
            and out.get("minAmountOut")==120_000_000_000_000_000
            and out.get("allowedProtocols")==["Uniswap-V3"]
            and out.get("deadlineMinutes")==45
            and "error" not in out)

attempts = []
out = compile_intent(prompt); attempts.append(out)
if not validate(out):
    out = compile_intent(prompt); attempts.append(out)
print("  Output:", attempts[-1])
ok3 = validate(attempts[-1])
if not ok3:
    print("  Both attempts:", attempts)
results["STEP 3"] = "PASS" if ok3 else "FAIL"
print(f"STEP 3: {results['STEP 3']}")

# ---------------- STEP 4 ----------------
banner("STEP 4 — EIP-712 signing & registerIntent")
nonce = user.intent_registry.functions.nonces(USER_ADDR).call()
deadline = int(time.time())+3600
intent = build_intent(USER_ADDR, ORCH_ADDR, USDC_ADDRESS,
                      300_000_000, 120_000_000_000_000_000,
                      ["Uniswap-V3"], deadline, nonce)
sig = sign_intent(intent, USER_PK)
try:
    intent_id = user.register_intent(intent, sig)
    print(f"  intentId: {intent_id}")
    results["STEP 4"] = "PASS"
except Exception as e:
    print("  FAIL:", revert_reason(e))
    results["STEP 4"] = "FAIL"
    raise SystemExit(1)
print(f"STEP 4: {results['STEP 4']}")

# ---------------- STEP 5 ----------------
banner("STEP 5 — Delegation chain")
try:
    d1 = orch.delegate_from_root(intent_id, {
        "maxAmountIn":250_000_000, "minAmountOut":125_000_000_000_000_000,
        "allowedProtocols":[UNI], "deadline": deadline-300}, RES_ADDR)
    print(f"  delegationId1: {d1}")
    d2 = res.delegate_from_delegation(d1, {
        "maxAmountIn":200_000_000, "minAmountOut":130_000_000_000_000_000,
        "allowedProtocols":[UNI], "deadline": deadline-600}, EXEC_ADDR)
    print(f"  delegationId2: {d2}")
    txp = {"amountIn":200_000_000, "minAmountOut":130_000_000_000_000_000,
           "protocol":UNI, "tokenIn":USDC_ADDRESS, "tokenOut":WETH_ADDRESS, "recipient":USER_ADDR}
    chain_ok = ex.verify_chain(d2, txp)
    print(f"  verify_chain: {chain_ok}")
    user.ensure_token_approval(USDC_ADDRESS, EXECUTION_GATE_ADDRESS, txp["amountIn"])
    print(f"  USDC approval confirmed for {txp['amountIn']} units")
    tx = ex.execute_swap(d2, txp)
    print(f"  swap tx: 0x{tx}")
    print(f"  https://sepolia.etherscan.io/tx/0x{tx}")
    results["STEP 5"] = "PASS" if chain_ok else "FAIL"
except Exception as e:
    print("  FAIL:", revert_reason(e))
    results["STEP 5"] = "FAIL"
print(f"STEP 5: {results['STEP 5']}")

# ---------------- STEP 6 ----------------
banner("STEP 6 — Attack scenario (amount exceeds scope)")
nonce6 = user.intent_registry.functions.nonces(USER_ADDR).call()
i6 = build_intent(USER_ADDR, ORCH_ADDR, USDC_ADDRESS, 300_000_000, 120_000_000_000_000_000,
                  ["Uniswap-V3"], int(time.time())+3600, nonce6)
sig6 = sign_intent(i6, USER_PK)
intent_id6 = user.register_intent(i6, sig6)
d6_1 = orch.delegate_from_root(intent_id6, {
    "maxAmountIn":250_000_000, "minAmountOut":125_000_000_000_000_000,
    "allowedProtocols":[UNI], "deadline": i6["deadline"]-300}, RES_ADDR)
try:
    res.delegate_from_delegation(d6_1, {
        "maxAmountIn":800_000_000, "minAmountOut":125_000_000_000_000_000,
        "allowedProtocols":[UNI], "deadline": i6["deadline"]-600}, EXEC_ADDR)
    print("  CRITICAL FAILURE — malicious delegation was not blocked")
    results["STEP 6"] = "FAIL"
    raise SystemExit(1)
except SystemExit: raise
except Exception as e:
    rr = revert_reason(e)
    if "Amount exceeds scope" in rr:
        print(f"  ATTACK BLOCKED — {rr}")
        results["STEP 6"] = "PASS"
    else:
        print(f"  Unexpected revert: {rr}")
        results["STEP 6"] = "FAIL"
print(f"STEP 6: {results['STEP 6']}")

# ---------------- STEP 7 ----------------
banner("STEP 7 — Protocol attack (subset violation)")
nonce7 = user.intent_registry.functions.nonces(USER_ADDR).call()
i7 = build_intent(USER_ADDR, ORCH_ADDR, USDC_ADDRESS, 300_000_000, 120_000_000_000_000_000,
                  ["Uniswap-V3"], int(time.time())+3600, nonce7)
sig7 = sign_intent(i7, USER_PK)
id7 = user.register_intent(i7, sig7)
d7_1 = orch.delegate_from_root(id7, {
    "maxAmountIn":250_000_000, "minAmountOut":125_000_000_000_000_000,
    "allowedProtocols":[UNI], "deadline": i7["deadline"]-300}, RES_ADDR)
CURVE = Web3.keccak(text="Curve").hex()
try:
    res.delegate_from_delegation(d7_1, {
        "maxAmountIn":200_000_000, "minAmountOut":125_000_000_000_000_000,
        "allowedProtocols":[UNI, CURVE], "deadline": i7["deadline"]-600}, EXEC_ADDR)
    print("  CRITICAL FAILURE — protocol injection not blocked")
    results["STEP 7"] = "FAIL"
    raise SystemExit(1)
except SystemExit: raise
except Exception as e:
    rr = revert_reason(e)
    if "Protocols not subset" in rr:
        print(f"  PROTOCOL ATTACK BLOCKED — {rr}")
        results["STEP 7"] = "PASS"
    else:
        print(f"  Unexpected: {rr}")
        results["STEP 7"] = "FAIL"
print(f"STEP 7: {results['STEP 7']}")

# ---------------- STEP 8 ----------------
banner("STEP 8 — Revocation")
nonce8 = user.intent_registry.functions.nonces(USER_ADDR).call()
i8 = build_intent(USER_ADDR, ORCH_ADDR, USDC_ADDRESS, 300_000_000, 120_000_000_000_000_000,
                  ["Uniswap-V3"], int(time.time())+3600, nonce8)
sig8 = sign_intent(i8, USER_PK)
id8 = user.register_intent(i8, sig8)
print(f"  registered: {id8}")
user.send_tx(user.intent_registry.functions.revokeIntent(bytes.fromhex(id8[2:])))
print("  revoked")
try:
    orch.delegate_from_root(id8, {
        "maxAmountIn":250_000_000, "minAmountOut":125_000_000_000_000_000,
        "allowedProtocols":[UNI], "deadline": i8["deadline"]-300}, RES_ADDR)
    print("  FAIL — delegation succeeded after revocation")
    results["STEP 8"] = "FAIL"
except Exception as e:
    rr = revert_reason(e)
    if "Intent not found" in rr:
        print(f"  REVOCATION WORKS — {rr}")
        results["STEP 8"] = "PASS"
    else:
        print(f"  Unexpected: {rr}")
        results["STEP 8"] = "FAIL"
print(f"STEP 8: {results['STEP 8']}")

# ---------------- STEP 9 ----------------
banner("STEP 9 — Replay protection (root already delegated)")
nonce9 = user.intent_registry.functions.nonces(USER_ADDR).call()
i9 = build_intent(USER_ADDR, ORCH_ADDR, USDC_ADDRESS, 300_000_000, 120_000_000_000_000_000,
                  ["Uniswap-V3"], int(time.time())+3600, nonce9)
sig9 = sign_intent(i9, USER_PK)
id9 = user.register_intent(i9, sig9)
orch.delegate_from_root(id9, {
    "maxAmountIn":250_000_000, "minAmountOut":125_000_000_000_000_000,
    "allowedProtocols":[UNI], "deadline": i9["deadline"]-300}, RES_ADDR)
try:
    orch.delegate_from_root(id9, {
        "maxAmountIn":250_000_000, "minAmountOut":125_000_000_000_000_000,
        "allowedProtocols":[UNI], "deadline": i9["deadline"]-300}, RES_ADDR)
    print("  FAIL — second delegation succeeded")
    results["STEP 9"] = "FAIL"
except Exception as e:
    rr = revert_reason(e)
    if "Root already delegated" in rr:
        print(f"  REPLAY PROTECTION WORKS — {rr}")
        results["STEP 9"] = "PASS"
    else:
        print(f"  Unexpected: {rr}")
        results["STEP 9"] = "FAIL"
print(f"STEP 9: {results['STEP 9']}")

# ---------------- STEP 10 ----------------
banner("STEP 10 — Frozen agent")
nonce10 = user.intent_registry.functions.nonces(USER_ADDR).call()
i10 = build_intent(USER_ADDR, ORCH_ADDR, USDC_ADDRESS, 300_000_000, 120_000_000_000_000_000,
                   ["Uniswap-V3"], int(time.time())+3600, nonce10)
sig10 = sign_intent(i10, USER_PK)
id10 = user.register_intent(i10, sig10)
deployer.send_tx(deployer.agent_registry.functions.freezeAgent(Web3.to_checksum_address(RES_ADDR)))
print("  RESEARCH frozen")
step10_pass = False
try:
    orch.delegate_from_root(id10, {
        "maxAmountIn":250_000_000, "minAmountOut":125_000_000_000_000_000,
        "allowedProtocols":[UNI], "deadline": i10["deadline"]-300}, RES_ADDR)
    print("  FAIL — delegation succeeded to frozen agent")
except Exception as e:
    rr = revert_reason(e)
    if "Target not registered agent" in rr:
        print(f"  FREEZE WORKS — {rr}")
        step10_pass = True
    else:
        print(f"  Unexpected: {rr}")
finally:
    deployer.send_tx(deployer.agent_registry.functions.unfreezeAgent(Web3.to_checksum_address(RES_ADDR)))
    print("  RESEARCH unfrozen")
results["STEP 10"] = "PASS" if step10_pass else "FAIL"
print(f"STEP 10: {results['STEP 10']}")

print("\n\n=== RESULTS ===")
for k,v in results.items(): print(f"  {k}: {v}")
