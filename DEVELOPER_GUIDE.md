# Proof-of-Intent Protocol — Developer Usage Guide

---

## Table of Contents

1. [Minimum Setup — SDK Core (Python)](#1-minimum-setup--sdk-core-python)
2. [Natural Language Compiler](#2-natural-language-compiler)
3. [Running the Full 3-Agent Pipeline (AXL)](#3-running-the-full-3-agent-pipeline-axl)
4. [TypeScript SDK](#4-typescript-sdk)
5. [What You Actually See When Things Work](#5-what-you-actually-see-when-things-work)
6. [What Breaks and Why](#6-what-breaks-and-why)
7. [Contract Addresses](#7-contract-addresses)

---

## Quick-reference: full public API

### Python (`from proof_of_intent import ...`)

| Export | Requires private keys? | Description |
|---|---|---|
| `usdc(amount)` | No | `usdc(500)` → `500_000_000` |
| `from_usdc(units)` | No | `from_usdc(500_000_000)` → `500.0` |
| `weth(amount)` | No | `weth(0.15)` → `150_000_000_000_000_000` |
| `from_weth(units)` | No | reverse conversion |
| `token(amount, decimals)` | No | generic ERC20 conversion |
| `from_token(units, decimals)` | No | reverse conversion |
| `in_minutes(n)` | No | Unix timestamp `n` minutes from now |
| `in_hours(n)` | No | Unix timestamp `n` hours from now |
| `ContractClient(private_key)` | Yes | main SDK class |
| `TransactionRevertError` | Yes | exception class with `.reason` attribute |
| `build_intent(...)` | Yes | builds intent dict, hashes protocol names |
| `sign_intent(intent, key)` | Yes | EIP-712 signature |
| `UNISWAP_V3`, `CURVE`, `BALANCER_V2` | No | pre-hashed bytes32 constants |
| `Scope` | No | dataclass for building scope dicts |

**`ContractClient` methods:**

| Method | Returns | Description |
|---|---|---|
| `.register_intent(intent, sig)` | `str` intentId | register on-chain |
| `.create_intent(token_in, max_amount_in, min_amount_out, protocols, deadline, orchestrator?, owner?)` | `str` intentId | build + sign + register in one call |
| `.delegate_from_root(intent_id, scope, delegate_to)` | `str` delegationId | first delegation from intent |
| `.delegate_from_delegation(parent_id, scope, delegate_to)` | `str` delegationId | sub-delegation |
| `.execute_swap(delegation_id, tx_params)` | `str` tx hash | execute the swap |
| `.verify_chain(delegation_id, tx_params)` | `bool` | view call, no gas |
| `.ensure_token_approval(token, spender, amount)` | `None` | approve only if allowance is low |
| `.token_balance(token, account)` | `int` raw units | ERC20 balance check |
| `.register_agent(address, name, skip_if_active?)` | `str \| None` tx hash | register in AgentRegistry |
| `ContractClient.build_scope(max_amount_in, min_amount_out, protocols, deadline)` | `dict` | static; hashes protocol names |

### TypeScript (`import { ... } from 'proof-of-intent'`)

| Export | Description |
|---|---|
| `toUsdc(amount)` / `usdc(amount)` | `toUsdc(500)` → `500_000_000n` |
| `fromUsdc(units)` | reverse |
| `toWeth(amount)` / `weth(amount)` | `toWeth(0.15)` → `150_000_000_000_000_000n` |
| `fromWeth(units)` | reverse |
| `toToken(amount, decimals)` | generic |
| `fromToken(units, decimals)` | reverse |
| `inMinutes(n)` | `bigint` Unix timestamp `n` minutes from now |
| `inHours(n)` | `bigint` Unix timestamp `n` hours from now |
| `buildIntent(params)` | builds `IntentData`, **hashes protocol names automatically** |
| `buildScope(params)` | builds `ScopeData`, **hashes protocol names automatically** |
| `signIntent(intent, key, config)` | EIP-712 signature |
| `ContractClient({ privateKey, ...overrides })` | same methods as Python, async |
| `UNISWAP_V3`, `CURVE`, `BALANCER_V2`, `AAVE_V3`, `ONEINCH` | pre-hashed bytes32 constants |
| `protocolId(name)` | hash a protocol name |
| `protocolName(bytes32)` | reverse lookup |
| `loadConfig(overrides?)` | load from env vars + Sepolia defaults |
| `loadDeployedAddresses(deployed)` | convert deployed.json to config |
| `getNonce(config, owner)` | fetch nonce from IntentRegistry |
| `getDomainSeparator(config)` | EIP-712 domain separator |
| `verifyChain(id, params, config)` | module-level view call |
| `executeSwap(id, params, key, config)` | module-level execute |

---

## 1. Minimum Setup — SDK Core (Python)

### What "SDK core" means

The Python SDK is the self-contained `proof_of_intent` package in `poip-py/`.
It bundles its own ABIs and hardcodes Sepolia defaults — no dependency on
`config/`, `contracts/out/`, or any pipeline key beyond `PRIVATE_KEY`.

Primary operations:

```python
from proof_of_intent import ContractClient, build_intent, sign_intent

# build_intent — all keyword-only
build_intent(owner, authorized_orchestrator, token_in, max_amount_in,
             min_amount_out, allowed_protocols, deadline, nonce) -> dict

sign_intent(intent: dict, private_key: str) -> str   # returns "0x..." signature

# ContractClient — private_key positional, all other params keyword-only
ContractClient(private_key: str, *, rpc_url=..., chain_id=...,
               agent_registry_address=..., intent_registry_address=...,
               delegation_registry_address=..., execution_gate_address=...)
  .register_intent(intent, signature) -> str          # returns intentId hex
  .create_intent(token_in, max_amount_in, min_amount_out,  # build+sign+register
                 allowed_protocols, deadline,              # in one call
                 orchestrator=None, owner=None) -> str
  .delegate_from_root(root_intent_id, child_scope, delegate_to) -> str
  .delegate_from_delegation(parent_delegation_id, child_scope, delegate_to) -> str
  .execute_swap(delegation_id, tx_params) -> str       # returns tx hash
  .verify_chain(delegation_id, tx_params) -> bool
  ContractClient.build_scope(max_amount_in, min_amount_out,  # static method
                             allowed_protocols, deadline) -> dict
```

### Install

```bash
# From the repository root
pip install -e ./poip-py

# With dev dependencies (pytest, python-dotenv)
pip install -e "./poip-py[dev]"

# With AI dependencies (anthropic, openai) for the compiler
pip install -e "./poip-py[ai]"
```

No other install step is needed. ABIs are bundled inside the package under
`proof_of_intent/_abis/`.

### Required environment variables

Only one environment variable is required to use the SDK on its own:

| Variable | Notes |
|---|---|
| `PRIVATE_KEY` | Your Ethereum wallet private key (`0x…`). |

```bash
cp .env.sdk.example poip-py/.env
# Fill in PRIVATE_KEY=0x...
```

Contract addresses are hardcoded to the deployed Sepolia contracts in
`poip-py/proof_of_intent/_defaults.py`. You can override them at construction time:

```python
client = ContractClient(
    private_key=os.environ["PRIVATE_KEY"],
    intent_registry_address="0x...",   # override only what you need
)
```

Optional variables:

| Variable | Default |
|---|---|
| `RPC_URL` | `https://ethereum-sepolia-rpc.publicnode.com` |
| `CHAIN_ID` | `11155111` |

### ABI requirement

None — ABIs are bundled in the package. The `forge build` step is only needed if
you are modifying contracts or running the full pipeline (`agents/`).

### Token amount helpers

```python
from proof_of_intent import usdc, weth, token, in_minutes, in_hours
from proof_of_intent import from_usdc, from_weth, from_token

usdc(500)          # → 500_000_000        (USDC has 6 decimals)
usdc(0.5)          # → 500_000
weth(0.15)         # → 150_000_000_000_000_000
weth(1)            # → 1_000_000_000_000_000_000
token(100, 6)      # → 100_000_000        generic: any token + decimal count
in_minutes(60)     # → int(time.time()) + 3600
in_hours(1)        # → int(time.time()) + 3600  (same as in_minutes(60))

from_usdc(500_000_000)               # → 500.0
from_weth(150_000_000_000_000_000)   # → 0.15
```

### Quickstart script

Run the 5-step standalone example (no pipeline, no extra config):

```bash
cd poip-py
cp .env.example .env   # fill in PRIVATE_KEY
python examples/quickstart.py
```

### Minimum working example

```python
import os
from proof_of_intent import (
    ContractClient, build_intent, sign_intent,
    usdc, weth, in_hours, UNISWAP_V3,
)

USDC = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"   # Sepolia USDC
WETH = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"   # Sepolia WETH

private_key = os.environ["PRIVATE_KEY"]
client = ContractClient(private_key=private_key)

# 1. Build and sign an intent
nonce = client.intent_registry.functions.nonces(client.account.address).call()
intent = build_intent(
    owner=client.account.address,
    authorized_orchestrator=client.account.address,   # self-orchestrate for demo
    token_in=USDC,
    max_amount_in=usdc(500),
    min_amount_out=weth(0.15),
    allowed_protocols=["Uniswap-V3"],   # hashed to bytes32 automatically
    deadline=in_hours(1),
    nonce=nonce,
)
signature = sign_intent(intent, private_key)

# 2. Register on-chain
intent_id = client.register_intent(intent, signature)
print("intentId:", intent_id)

# Alternatively — build + sign + register in one call:
# intent_id = client.create_intent(
#     token_in=USDC,
#     max_amount_in=usdc(500),
#     min_amount_out=weth(0.15),
#     allowed_protocols=["Uniswap-V3"],
#     deadline=in_hours(1),
# )

# 3. Create root delegation (scope must use pre-hashed bytes32 for protocol)
scope = {
    "maxAmountIn":      usdc(500),
    "minAmountOut":     weth(0.15),
    "allowedProtocols": [UNISWAP_V3.hex()],
    "deadline":         in_hours(1),
}
delegation_id = client.delegate_from_root(intent_id, scope, client.account.address)
print("delegationId:", delegation_id)

# 4. Verify chain (view call, no gas)
tx_params = {
    "amountIn":     usdc(500),
    "minAmountOut": weth(0.15),
    "protocol":     UNISWAP_V3.hex(),
    "tokenIn":      USDC,
    "tokenOut":     WETH,
    "recipient":    client.account.address,
}
assert client.verify_chain(delegation_id, tx_params)

# 5. Execute (requires Sepolia USDC in the wallet)
client.ensure_token_approval(USDC, client.execution_gate.address, usdc(500))
tx_hash = client.execute_swap(delegation_id, tx_params)
print("tx hash:", tx_hash)
print(f"https://sepolia.etherscan.io/tx/{tx_hash}")
```

### Error handling

`ContractClient` raises `TransactionRevertError` (not a generic exception) when a
contract call reverts. It has a `.reason` attribute with the revert string:

```python
from proof_of_intent import ContractClient
from proof_of_intent.errors import TransactionRevertError, ScopeViolationError, DeadlineExpiredError

try:
    delegation_id = orch.delegate_from_root(intent_id, bad_scope, agent)
except ScopeViolationError as exc:
    print(exc.reason)   # "Amount exceeds scope"
except DeadlineExpiredError as exc:
    print(exc.reason)   # "Deadline expired"
except TransactionRevertError as exc:
    print(exc.reason)   # any other revert
```

Error hierarchy: `POIPError → TransactionRevertError → ScopeViolationError / DeadlineExpiredError`

---

## 2. Natural Language Compiler

### What it adds

`agents/compiler.py` converts a plain English sentence into the structured dict
that `build_intent()` expects. It adds no new packages beyond what the SDK core
already requires — `anthropic` and `openai` are both in `pyproject.toml`'s `[ai]` extra.

### Additional env vars

| Variable | When required |
|---|---|
| `CLAUDE_API_KEY` | When `USE_CLAUDE=true` (default) |
| `OPENAI_API_KEY` | When `USE_CLAUDE=false` |

`USE_CLAUDE` defaults to `true`, so `CLAUDE_API_KEY` is required in the default
configuration. Set `USE_CLAUDE=false` to switch to OpenAI.

### Model used

- Claude path: `claude-haiku-4-5-20251001` via `anthropic.Anthropic`
- OpenAI path: `gpt-5-mini` via `openai.OpenAI`

### Function signatures

```python
from agents.compiler import compile_intent, display_intent, interactive_compile

# One-shot: returns a dict or raises ValueError
compiled: dict = compile_intent("swap 400 USDC for max ETH via Uniswap, deadline 30 min")

# Pretty-print the result to stdout
display_intent(compiled)

# Interactive REPL: prompts for input, shows result, asks for confirmation
compiled: dict = interactive_compile()
```

### Output schema

`compile_intent()` returns a dict matching this schema (raw from the system prompt):

```json
{
  "tokenIn": "<ERC20 token symbol>",
  "tokenInAddress": "<checksummed address or null if unknown>",
  "maxAmountIn": "<integer in token units with decimals>",
  "minAmountOut": "<integer minimum output in output token units>",
  "allowedProtocols": ["<protocol name>"],
  "deadlineMinutes": "<integer minutes from now>",
  "reasoning": "<one sentence>"
}
```

**Note:** `compile_intent()` returns a raw dict, not a fully-formed intent struct.
You must convert `deadlineMinutes` to an absolute Unix timestamp and look up or
confirm `tokenInAddress` before passing to `build_intent()`.

### Connecting compiler output to `build_intent()`

```python
import time
from agents.compiler import compile_intent
from proof_of_intent import build_intent, sign_intent, in_minutes
from config.config import USER_PRIVATE_KEY, USER_ADDRESS, ORCHESTRATOR_ADDRESS

compiled = compile_intent("swap 500 USDC for WETH using Uniswap, 1 hour deadline")

intent = build_intent(
    owner=USER_ADDRESS,
    authorized_orchestrator=ORCHESTRATOR_ADDRESS,
    token_in=compiled["tokenInAddress"],          # must be a valid address
    max_amount_in=compiled["maxAmountIn"],
    min_amount_out=compiled["minAmountOut"],
    allowed_protocols=compiled["allowedProtocols"],
    deadline=int(time.time()) + compiled["deadlineMinutes"] * 60,
    nonce=0,  # fetch from contract: client.intent_registry.functions.nonces(USER_ADDRESS).call()
)
signature = sign_intent(intent, USER_PRIVATE_KEY)
```

### Running the interactive compiler standalone

```bash
python -m agents.compiler
```

---

## 3. Running the Full 3-Agent Pipeline (AXL)

The pipeline consists of three Python agents communicating over a local AXL P2P
mesh. Each agent runs in a separate terminal.

### Prerequisites

1. **AXL binary** — `vendor/axl/node` is a pre-compiled Go binary.
   If it is absent or you need to rebuild:

   ```bash
   # Requires Go 1.25.5+
   cd vendor/axl
   make build
   # Output: vendor/axl/node
   ```

2. **Agent identity keys** — `agents/keys/orchestrator.key`,
   `agents/keys/research.key`, `agents/keys/execution.key` are ed25519 private
   key files already committed to the repository. Do not regenerate them unless
   you also update the hardcoded public keys in `config/config.py`
   (`ORCHESTRATOR_AXL_KEY`, `RESEARCH_AXL_KEY`, `EXECUTION_AXL_KEY`).

3. **Python environment** — SDK installed, `.env` populated with all pipeline keys.

4. **Sepolia wallet funding** — the user wallet (`USER_ADDRESS`) needs Sepolia USDC
   (400+ units, at `0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238`) and enough
   Sepolia ETH for gas (~0.05 ETH). The orchestrator, research, and execution
   wallets only need Sepolia ETH for gas (~0.01 ETH each).

5. **Agent registration** — all three agent wallets must be registered in
   `AgentRegistry` on Sepolia. This is done once by running the deploy script.
   If deploying fresh contracts, run `./deploy.sh` after setting env vars and
   agent addresses (see below).

6. **Foundry build artifacts** — `contracts/out/` must exist (used by `config/config.py`
   when running pipeline agents). It is already built and committed to the repository.
   To rebuild: `cd contracts && forge build`.

### Step-by-step

#### Step 1: Populate `.env`

```bash
cp .env.example .env
```

Fill in all four private keys:

```
DEPLOYER_PRIVATE_KEY=0x...   # orchestrator wallet (also used for deploy)
USER_PRIVATE_KEY=0x...
RESEARCH_PRIVATE_KEY=0x...
EXECUTION_PRIVATE_KEY=0x...
```

Set the LLM key. Default is Claude:

```
USE_CLAUDE=true
CLAUDE_API_KEY=sk-ant-...
```

Optionally set ENS and 0G keys; both are non-blocking and the pipeline works
without them:

```
ENS_NAME=yourname.eth        # leave blank to skip
ZG_API_KEY=0x...             # leave blank to skip
```

#### Step 2: (First time only) Deploy contracts and register agents

If using the already-deployed Sepolia contracts, skip this step — `config/deployed.json`
is already populated.

To deploy fresh contracts:

```bash
# Set agent addresses derived from your private keys in .env
ORCHESTRATOR_ADDRESS=<address from DEPLOYER_PRIVATE_KEY>
RESEARCH_ADDRESS=<address from RESEARCH_PRIVATE_KEY>
EXECUTION_ADDRESS=<address from EXECUTION_PRIVATE_KEY>

./deploy.sh
# This runs: forge script script/Deploy.s.sol --rpc-url $RPC_URL --private-key $DEPLOYER_PRIVATE_KEY --broadcast
# Output: updates config/deployed.json
```

#### Step 3: Start the AXL nodes

All three must run from the **project root directory** because the config files
reference key paths as relative paths (`"PrivateKeyPath": "agents/keys/orchestrator.key"`).

**Terminal 1 — Orchestrator node (bootstrap):**
```bash
./vendor/axl/node -config agents/axl_configs/orchestrator.json
```
Listens on `tls://127.0.0.1:9001`, API on `http://127.0.0.1:9002`.

**Terminal 2 — Research node:**
```bash
./vendor/axl/node -config agents/axl_configs/research.json
```
Peers to `tls://127.0.0.1:9001`, API on `http://127.0.0.1:9012`.

**Terminal 3 — Execution node:**
```bash
./vendor/axl/node -config agents/axl_configs/execution.json
```
Peers to `tls://127.0.0.1:9001`, API on `http://127.0.0.1:9022`.

Wait for the Yggdrasil mesh to converge (a few seconds). The nodes output routing
table updates to stderr as peers connect.

#### Step 4: Register the user's intent on-chain

You need to do this before starting the agents, because the orchestrator requires
an existing `intentId`. Use the SDK directly:

```python
# From project root
python - <<'EOF'
import time, os
from dotenv import load_dotenv; load_dotenv()
from proof_of_intent import ContractClient, build_intent, sign_intent, usdc, weth, in_hours
from config.config import USER_PRIVATE_KEY, USER_ADDRESS, ORCHESTRATOR_ADDRESS, USDC_ADDRESS

user = ContractClient(USER_PRIVATE_KEY)
nonce = user.intent_registry.functions.nonces(USER_ADDRESS).call()
intent = build_intent(
    owner=USER_ADDRESS,
    authorized_orchestrator=ORCHESTRATOR_ADDRESS,
    token_in=USDC_ADDRESS,
    max_amount_in=usdc(500),
    min_amount_out=weth(0.15),
    allowed_protocols=["Uniswap-V3"],
    deadline=in_hours(1),
    nonce=nonce,
)
sig = sign_intent(intent, USER_PRIVATE_KEY)
intent_id = user.register_intent(intent, sig)
print("INTENT_ID:", intent_id)
EOF
```

Note the printed `INTENT_ID` — you need it in Step 6.

#### Step 5: Start the Execution Agent

**Terminal 4:**
```bash
python -m agents.execution_agent
```
Output: `Execution Agent listening...`

The agent waits on `http://127.0.0.1:9022/recv` with a 60-second timeout.

#### Step 6: Start the Research Agent

**Terminal 5:**
```bash
python -m agents.research_agent
# For the compromised (attack) scenario:
python -m agents.research_agent --compromised
```
Output: `Research Agent listening for task...`

The agent waits on `http://127.0.0.1:9012/recv` with a 60-second timeout.

#### Step 7: Start the Orchestrator

**Terminal 6:**
```bash
python -m agents.orchestrator <INTENT_ID> "swap 400 USDC for max WETH"
```

Replace `<INTENT_ID>` with the hex value from Step 4.

The orchestrator will:
1. Load the root intent from the contract
2. Create a root delegation to the Research Agent
3. Send a `{"type": "TASK", "delegationId": "...", "goal": "...", "rootIntentId": "..."}` message via AXL
4. Block waiting for a `COMPLETE` or `FAILED` reply (300-second timeout)

#### Step 8: Pre-approve USDC spending (if not already done)

The execution agent calls `ensure_token_approval` using its own wallet as the
`ContractClient`, but the approval needs to be from the **user** wallet because
`ExecutionGate.executeSwap` calls `transferFrom(recipient, ...)`. The execution agent
approves USDC from the execution key's wallet, not the user's wallet. If the user
has not separately approved `ExecutionGate` to spend their USDC, the `executeSwap`
call will revert with `ERC20InsufficientAllowance`.

To pre-approve from the user wallet:

```python
from dotenv import load_dotenv; load_dotenv()
from proof_of_intent import ContractClient, usdc
from config.config import USER_PRIVATE_KEY, USDC_ADDRESS, EXECUTION_GATE_ADDRESS
ContractClient(USER_PRIVATE_KEY).ensure_token_approval(
    USDC_ADDRESS, EXECUTION_GATE_ADDRESS, usdc(400)
)
```

### Alternative: run the self-contained demo

The demo handles intent registration, all delegations, verification, execution, and
both the clean and attack scenarios in one script — no AXL nodes required:

```bash
python -m agents.demo
```

The demo does NOT use AXL messaging. Agents are simulated in-process. This is the
quickest way to verify the full on-chain flow.

---

## 4. TypeScript SDK

### Install

```bash
cd poip-ts
npm install
npm run build    # compiles TypeScript to dist/
```

**Dependencies:** `ethers ^6.0.0` (production), `dotenv ^16.0.0`, `tsx ^4.0.0`,
`typescript ^5.0.0` (dev).

### Import

```typescript
import {
  // Types
  IntentData, ScopeData, TxParamsData, DelegationData, Config,
  // Config loaders
  loadConfig, loadDeployedAddresses,
  // Token/deadline helpers
  toUsdc, usdc, fromUsdc, toWeth, weth, fromWeth, toToken, fromToken,
  inMinutes, inHours,
  // Protocol IDs (keccak256 hashes, ethers.id())
  UNISWAP_V3, CURVE, BALANCER_V2, AAVE_V3, ONEINCH,
  ALL_PROTOCOLS, PROTOCOL_NAMES, protocolName, protocolId,
  // Intent building and signing (both hash protocol names automatically)
  buildIntent, buildScope, signIntent,
  // ContractClient class
  ContractClient,
  // Module-level helpers
  getProvider, getNonce, getDomainSeparator,
  registerIntentRaw, extractIntentIdFromReceipt,
  delegateFromRoot, delegateFromDelegation, extractDelegationIdFromReceipt,
  getDelegation, verifyChain, executeSwap,
} from '../src/index';
```

**Helper naming — Python vs TypeScript:**

| Python | TypeScript | Notes |
|---|---|---|
| `usdc(500)` | `usdc(500)` / `toUsdc(500)` | returns `bigint` in TS |
| `weth(0.15)` | `weth(0.15)` / `toWeth(0.15)` | returns `bigint` in TS |
| `token(x, d)` | `toToken(x, d)` | |
| `from_usdc(x)` | `fromUsdc(x)` | |
| `from_weth(x)` | `fromWeth(x)` | |
| `in_minutes(n)` | `inMinutes(n)` | returns `bigint` in TS |
| `in_hours(n)` | `inHours(n)` | returns `bigint` in TS |

### Environment variables

`loadConfig()` in `src/config.ts` falls back to hardcoded Sepolia defaults when
env vars are not set. Contract address env vars are **optional**:

| Variable | Required | Default |
|---|---|---|
| `RPC_URL` | No | `https://ethereum-sepolia-rpc.publicnode.com` |
| `CHAIN_ID` | No | `11155111` |
| `AGENT_REGISTRY_ADDRESS` | No | `0xcD5954121BbE13a4867c2Df886e24E924D006883` |
| `INTENT_REGISTRY_ADDRESS` | No | `0xf2a52EAf8E2440F9aFa28aDA5426Bc2908DDc5b4` |
| `DELEGATION_REGISTRY_ADDRESS` | No | `0x51bF1E9C33ACF135E7C6ca83AD4Cf36d5B8BBa45` |
| `EXECUTION_GATE_ADDRESS` | No | `0x076e8cd66be8B927CcB9adA63505e8027b209cb6` |
| `ENS_NAME` | No | `""` |
| `ZG_API_KEY` | No | `""` |
| `ZG_RPC_URL` | No | `https://evmrpc-testnet.0g.ai` |
| `ZG_INDEXER_URL` | No | `https://indexer-storage-testnet-turbo.0g.ai` |

The `tradingBot.ts` example adds its own `requireEnv()` calls for private keys
and token addresses:

| Variable | Used in |
|---|---|
| `USER_PRIVATE_KEY` | `tradingBot.ts` |
| `ORCHESTRATOR_PRIVATE_KEY` | `tradingBot.ts` |
| `EXECUTION_PRIVATE_KEY` | `tradingBot.ts` |
| `USDC_ADDRESS` | `tradingBot.ts` |
| `WETH_ADDRESS` | `tradingBot.ts` |

Note: the TS example uses `ORCHESTRATOR_PRIVATE_KEY`, not `DEPLOYER_PRIVATE_KEY`.

### Function signatures

```typescript
// Load config from env vars; falls back to Sepolia defaults for addresses
function loadConfig(overrides?: Partial<Config>): Config

// Convert deployed.json object to config overrides
function loadDeployedAddresses(deployed: Record<string, string>): Partial<Config>

// Build an intent struct — hashes protocol names to bytes32 automatically
function buildIntent(params: {
  owner: string;
  authorizedOrchestrator: string;
  tokenIn: string;
  maxAmountIn: bigint;
  minAmountOut: bigint;
  allowedProtocols: string[];   // protocol names like "Uniswap-V3", hashed for you
  deadline: bigint;
  nonce: bigint;
}): IntentData

// Build a scope struct — hashes protocol names to bytes32 automatically
function buildScope(params: {
  maxAmountIn: bigint;
  minAmountOut: bigint;
  allowedProtocols: string[];   // protocol names, hashed automatically
  deadline: bigint;
}): ScopeData

// EIP-712 sign an intent
async function signIntent(
  intent: IntentData,
  privateKey: string,
  config: { chainId: number; intentRegistryAddress: string }
): Promise<string>

// ContractClient — options object constructor
class ContractClient {
  constructor(options: {
    privateKey: string;
    rpcUrl?: string;
    chainId?: number;
    agentRegistryAddress?: string;
    intentRegistryAddress?: string;
    delegationRegistryAddress?: string;
    executionGateAddress?: string;
  })
  async registerIntent(intent: IntentData, signature: string): Promise<string>
  async delegateFromRoot(rootIntentId: string, childScope: ScopeData, delegateTo: string): Promise<string>
  async delegateFromDelegation(parentDelegationId: string, childScope: ScopeData, delegateTo: string): Promise<string>
  async executeSwap(delegationId: string, txParams: TxParamsData): Promise<string>
  async verifyChain(delegationId: string, txParams: TxParamsData): Promise<boolean>
  async ensureTokenApproval(tokenAddress: string, spender: string, amount: bigint): Promise<void>
  async tokenBalance(tokenAddress: string, account: string): Promise<bigint>
}

// Module-level helpers
async function getNonce(config: Config, owner: string): Promise<bigint>
async function getDomainSeparator(config: Config): Promise<string>
async function getDelegation(delegationId: string, config: Config): Promise<DelegationData>
async function verifyChain(delegationId: string, txParams: TxParamsData, config: Config): Promise<boolean>
async function executeSwap(delegationId: string, txParams: TxParamsData, privateKey: string, config: Config): Promise<TransactionReceipt>
```

**Protocol name hashing — both SDKs hash automatically:**
Both `buildIntent()` and `buildScope()` in TypeScript hash protocol names to bytes32
automatically (using `ethers.id()`), the same way Python does. You can pass human-
readable strings in either language:

```typescript
// ✓ Both of these are equivalent and correct:
buildIntent(..., allowedProtocols: ["Uniswap-V3"])   // hashed automatically
buildIntent(..., allowedProtocols: [UNISWAP_V3])     // pre-hashed constant

// ✓ buildScope hashes names too:
buildScope({ ..., allowedProtocols: ["Uniswap-V3"] })
```

The exported constants (`UNISWAP_V3`, `CURVE`, etc.) are pre-hashed bytes32 values.
Use them when constructing `tx_params` or scope dicts manually — i.e., anywhere
you're building a struct directly rather than going through `buildIntent`/`buildScope`.

```typescript
import { UNISWAP_V3 } from '../src/index';
const txParams: TxParamsData = {
  ...
  protocol: UNISWAP_V3,              // ✓ correct — already hashed
  // protocol: "Uniswap-V3",         // ✗ wrong — raw string, will not match
};
```

### Run the example

```bash
cd poip-ts
cp .env.example .env  # fill in private keys
npx ts-node examples/tradingBot.ts
```

---

## 5. What You Actually See When Things Work

### SDK only (Python) — `python -m agents.demo`

The demo prints step headers to stdout. A working run looks like:

```
============================================================
              PROOF OF INTENT PROTOCOL — LIVE DEMO
============================================================
Chain: Ethereum Sepolia
Contracts deployed at:
  IntentRegistry:     0xf2a52EAf8E2440F9aFa28aDA5426Bc2908DDc5b4
  DelegationRegistry: 0x51bF1E9C33ACF135E7C6ca83AD4Cf36d5B8BBa45
  ExecutionGate:      0x076e8cd66be8B927CcB9adA63505e8027b209cb6

============================================================
           SCENARIO 1: CLEAN PIPELINE — NO ATTACK
============================================================

============================================================
             STEP 1: USER COMPILES AND SIGNS INTENT
============================================================
  owner:                  0x<user address>
  authorizedOrchestrator: 0x<orchestrator address>
  tokenIn (USDC):         0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238
  maxAmountIn:            500 USDC
  minAmountOut:           0.15 WETH
  allowedProtocols:       Uniswap-V3
  deadline:               +1 hour
  signature:              0x<first 20 chars>...

============================================================
              STEP 2: INTENT REGISTERED ON-CHAIN
============================================================
  intentId: 0x<bytes32>
  Intent is now immutable on Ethereum Sepolia.
0G storage skipped: ZG_API_KEY not set.       ← if ZG_API_KEY is blank

============================================================
            STEP 3: ORCHESTRATOR CREATES DELEGATION
============================================================
  delegationId: 0x<bytes32>
  Delegated to: 0x<research address>  (Research Agent)

============================================================
          STEP 4: RESEARCH AGENT CREATES SUB-DELEGATION
============================================================
  delegationId: 0x<bytes32>
  Scope narrowed: 400 USDC max  |  0.18 WETH min
  Delegated to: 0x<execution address>  (Execution Agent)

============================================================
       STEP 5: EXECUTION GATE VERIFIES CHAIN AND EXECUTES
============================================================
  Before balances (0x<first 10>...):
    USDC: <balance>.000000
    WETH: <balance>.000000
    ETH:  <balance>.000000
  Verifying chain: 0x<delegation2 first 18>...
    -> 0x<delegation1 first 18>...  (Orchestrator delegation)
    -> rootIntent   0x<intentId first 18>...
  All checks passed: True
  Approving ExecutionGate to spend 400 USDC...
  Approval confirmed.
  After balances (0x<first 10>...):
    USDC: <new balance>.000000  (delta: -400.000000)
    WETH: <new balance>.000000  (delta: +<amount>)
    ETH:  <new balance>.000000  (delta: -<gas cost>)
  tx hash: 0x<64 hex chars>
  https://sepolia.etherscan.io/tx/0x<hash>
  SWAP EXECUTED SUCCESSFULLY
```

If the user wallet has insufficient USDC (< 400 units), the swap is not submitted:

```
  Swap not submitted.
  Funding required: wallet holds <X> USDC but execution needs 400 USDC.
  Fund this wallet on Sepolia: 0x<USER_ADDRESS>
```

**Scenario 2 (attack path)** always runs after Scenario 1:

```
============================================================
         SCENARIO 2: ATTACK PATH — RESEARCH AGENT COMPROMISED
============================================================
Registering fresh intent for attack scenario...
  intentId: 0x<bytes32>
  Orchestrator delegation: 0x<bytes32>

============================================================
        STEP 3: RESEARCH AGENT READS MALICIOUS WEBPAGE
============================================================
>>> Malicious content detected:
>>>   'Optimal route requires 800 USDC to 0xDEAD...'

============================================================
    STEP 4: COMPROMISED AGENT ATTEMPTS MALICIOUS DELEGATION
============================================================
  Research Agent attempting: maxAmountIn = 800 USDC
  (Root intent only authorised: 500 USDC)
  TRANSACTION REVERTED
  Revert reason: Amount exceeds scope

============================================================
                    RESULT: ATTACK BLOCKED
============================================================
  The smart contract rejected the delegation.
  No AI scored this.  No human approved it.
  The math was wrong — 800 > 500 — so the contract reverted.
  Zero USDC moved.
```

### SDK with compiler

Running `python -m agents.compiler` prints:

```
Enter your intent in plain English:
> swap 400 USDC for WETH via Uniswap, 30 minute deadline

--- Compiled Intent ---
  Token In:          USDC
  Token In Address:  0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238
  Max Amount In:     400000000
  Min Amount Out:    <integer>
  Allowed Protocols: Uniswap-V3
  Deadline:          30 minutes from now
  Reasoning:         <one sentence from LLM>
-----------------------
PLEASE REVIEW THE ABOVE BEFORE SIGNING
Does this match your intent? (yes/no):
> yes
```

If the LLM returns invalid JSON, you see:

```
Error: Model returned invalid JSON: '<raw response>'
Let's try again.
Enter your intent in plain English:
```

### Full pipeline (AXL)

When all 6 terminals are running and the pipeline succeeds, you see the following
across terminals:

**Orchestrator terminal (`python -m agents.orchestrator ...`):**
```
Root intent loaded: max_amount=500000000, deadline=<unix timestamp>
Delegation created: 0x<bytes32>
Task sent to Research Agent via AXL
Result: {
  "type": "COMPLETE",
  "txHash": "0x<64 hex chars>"
}
```

**Research Agent terminal (`python -m agents.research_agent`):**
```
Research Agent listening for task...
Received task: swap 400 USDC for max WETH
Researching best swap route...
Found route: Uniswap V3, estimated output: 0.18 ETH
Creating valid delegation with maxAmountIn=400 USDC
Task forwarded to Execution Agent
```

**Execution Agent terminal (`python -m agents.execution_agent`):**
```
Execution Agent listening...
Received execution task: {
  "type": "EXECUTE",
  "delegationId": "0x<bytes32>",
  "txParams": { ... }
}
Verifying delegation chain against root intent...
Chain verification: PASSED
Token approval confirmed for 400000000 units
Executing swap via ExecutionGate...
Swap executed successfully!
Transaction hash: 0x<64 hex chars>
```

---

## 6. What Breaks and Why

Ordered from most to least likely for a new developer.

---

### 1. `SystemExit: Missing required environment variable(s): DEPLOYER_PRIVATE_KEY`

**Why:** This only happens when running the **pipeline agents** (`agents/demo.py`,
`agents/orchestrator.py`). These call `require_pipeline_keys()` at startup and
exit immediately if the pipeline keys are absent.

**The SDK itself** (`poip-py`) does NOT require `DEPLOYER_PRIVATE_KEY`. Only
`PRIVATE_KEY` is needed for SDK-only usage.

**Fix (pipeline):** Ensure `.env` has all four private keys and `load_dotenv()` runs before importing agents.

**Fix (SDK only):** Use `.env.sdk.example` as your template — it only requires `PRIVATE_KEY`.

---

### 2. `ValueError: Required environment variable 'CLAUDE_API_KEY' is missing or empty.`

**Why:** `USE_CLAUDE` defaults to `true`, so `CLAUDE_API_KEY` is required at
import time for the compiler even if you never call it.

**Fix:** Either add `CLAUDE_API_KEY=sk-ant-...` to `.env`, or set `USE_CLAUDE=false`
and add `OPENAI_API_KEY=sk-...` instead.

---

### 3. `FileNotFoundError: ... contracts/out/AgentRegistry.sol/AgentRegistry.json`

**Why:** `config/config.py` (pipeline config) loads ABIs from `contracts/out/` at
import time. This only affects pipeline code that imports `config.config` directly.

**The `proof_of_intent` SDK is not affected** — it bundles its own ABIs.

**Fix (pipeline):**
```bash
cd contracts && forge build
```

Requires [Foundry](https://getfoundry.sh/) to be installed.

---

### 4. `ConnectionError: Cannot connect to RPC: https://ethereum-sepolia-rpc.publicnode.com`

**Why:** The public Sepolia RPC is rate-limited and occasionally returns 429.
`ContractClient.__init__` calls `self.w3.is_connected()` which makes an HTTP request.

**Fix:** Set a private RPC URL:

```python
# Python — pass at construction time
client = ContractClient(private_key=key, rpc_url="https://sepolia.infura.io/v3/<key>")

# or via .env
RPC_URL=https://sepolia.infura.io/v3/<your_key>
```

---

### 5. `TransactionRevertError: Amount exceeds scope`

**Why:** You called `delegate_from_delegation()` with a `maxAmountIn` that exceeds
the parent delegation's `maxAmountIn`. The `DelegationRegistry` contract enforces:

```
childScope.maxAmountIn <= parentScope.maxAmountIn
childScope.minAmountOut >= parentScope.minAmountOut
childScope.deadline <= parentScope.deadline
childScope.allowedProtocols ⊆ parentScope.allowedProtocols
```

**Fix:** Ensure child scope values are within parent scope bounds.

---

### 6. `TransactionRevertError: Transaction reverted` (from `execute_swap`)

Most likely causes in order:

- **Insufficient USDC balance:** the user wallet does not hold enough USDC.
  Check with `client.token_balance(USDC_ADDRESS, USER_ADDRESS)`.

- **Insufficient allowance:** `ExecutionGate` is not approved to spend USDC.
  Call `user_client.ensure_token_approval(USDC_ADDRESS, EXECUTION_GATE_ADDRESS, amount)`.

- **Delegation already executed:** `delegationId` was already used. Each delegation
  can only be executed once. Register a fresh intent and re-delegate.

- **Deadline expired:** `deadline` in the intent or delegation has passed.
  Create a new intent with `deadline=in_hours(1)`.

- **Wrong recipient wallet approved:** In the pipeline, `execution_agent.py` calls
  `ensure_token_approval` from the execution wallet, but `executeSwap` pulls tokens
  from `txParams["recipient"]` (the user wallet). The user wallet must approve
  `ExecutionGate`, not the execution wallet.

---

### 7. `AXLTimeout: No AXL message received within 60s on port <N>`

**Why:** The AXL nodes are not running, not yet converged, or the message was
sent before the peer route was established.

**Fix:**
- Confirm all three `./vendor/axl/node` processes are running from the project root.
- Start agents in the correct order: Orchestrator node first (it is the bootstrap peer),
  then Research and Execution nodes, then wait ~5 seconds for mesh convergence, then
  start the Python agents.
- The first `send_message` after startup retries up to 5 times on 502 with linear
  backoff. If you still get `AXLTimeout`, the nodes have not routed to each other.

---

### 8. `urllib.error.HTTPError: HTTP Error 502: Bad Gateway` (from `send_message`)

**Why:** The AXL node's Yggdrasil spanning tree has not yet propagated a route to
the destination peer. The Python `send_message()` retries 5 times with linear backoff
starting at 1 second. If all retries fail, this exception propagates.

**Fix:** Wait longer after starting the nodes. The mesh typically converges in 2–5 seconds.

---

### 9. TypeScript: `Error: Missing env var: AGENT_REGISTRY_ADDRESS`

**Why:** `tradingBot.ts` calls `requireEnv('AGENT_REGISTRY_ADDRESS')` explicitly.
This is a guard in the example script, not in the SDK itself. `loadConfig()` already
has Sepolia defaults and does not require these env vars.

**Fix:** Either remove the `requireEnv()` guard from your own script, or add the
address vars to your `.env`. The Sepolia values are:

```
AGENT_REGISTRY_ADDRESS=0xcD5954121BbE13a4867c2Df886e24E924D006883
INTENT_REGISTRY_ADDRESS=0xf2a52EAf8E2440F9aFa28aDA5426Bc2908DDc5b4
DELEGATION_REGISTRY_ADDRESS=0x51bF1E9C33ACF135E7C6ca83AD4Cf36d5B8BBa45
EXECUTION_GATE_ADDRESS=0x076e8cd66be8B927CcB9adA63505e8027b209cb6
```

---

### 10. TypeScript: Protocol ID mismatch in `tx_params` — `verifyChain` returns `false`

**Why:** `buildIntent()` and `buildScope()` in TypeScript both hash protocol names
automatically — you can pass `"Uniswap-V3"` to them and it works correctly. However,
`TxParamsData.protocol` is a raw `bytes32` field that is NOT hashed automatically
(it maps directly to the contract struct). If you pass a string name instead of a
pre-hashed constant, the bytes32 will not match what was stored during intent/delegation
creation, and `verifyChain` will fail.

**Fix:** Always use exported constants or `protocolId()` for `tx_params.protocol`:

```typescript
import { UNISWAP_V3, protocolId } from '../src/index';

// ✓ buildIntent and buildScope hash names for you:
const intent = buildIntent({ ..., allowedProtocols: ["Uniswap-V3"] });
const scope  = buildScope({ ...,  allowedProtocols: ["Uniswap-V3"] });

// ✗ tx_params does NOT hash — use the constant:
const txParams: TxParamsData = {
  ...,
  protocol: UNISWAP_V3,     // ✓ correct — pre-hashed bytes32
  // protocol: "Uniswap-V3",   // ✗ wrong — raw string, will not match
};
```

---

### 11. `Warning [0G]: upload failed — <reason>`

**Why:** 0G storage is non-blocking. If `ZG_API_KEY` is set but the key has no
A0GI tokens on the 0G Newton testnet, the upload subprocess exits with an error.
The main flow continues normally.

**Fix:** Get A0GI tokens from `https://faucet.0g.ai`, or leave `ZG_API_KEY` blank
to skip 0G storage entirely.

---

### 12. `Warning [ENS]: <reason>`

**Why:** ENS linking is non-blocking. Common causes:
- `ENS_NAME` is set but the `DEPLOYER_PRIVATE_KEY` wallet is not the ENS controller for that name.
- The ENS registry resolver returns the zero address (name registered with no explicit resolver).

**Fix:** Leave `ENS_NAME` blank to skip ENS linking, or ensure the deployer wallet
controls the ENS name.

---

## 7. Contract Addresses

### Deployed addresses

```json
{
  "agentRegistry":      "0xcD5954121BbE13a4867c2Df886e24E924D006883",
  "intentRegistry":     "0xf2a52EAf8E2440F9aFa28aDA5426Bc2908DDc5b4",
  "delegationRegistry": "0x51bF1E9C33ACF135E7C6ca83AD4Cf36d5B8BBa45",
  "executionGate":      "0x076e8cd66be8B927CcB9adA63505e8027b209cb6"
}
```

Network: **Ethereum Sepolia** (chainId `11155111`).

### Cross-reference: where these addresses live in the codebase

| Address | Python SDK (`poip-py`) | Pipeline (`config/`) | TypeScript SDK (`poip-ts`) |
|---|---|---|---|
| `agentRegistry` | `_defaults.py` hardcoded | `deployed.json` via `_deployed["agentRegistry"]` | `SEPOLIA_DEFAULTS` in `config.ts` |
| `intentRegistry` | `_defaults.py` hardcoded | `deployed.json` via `_deployed["intentRegistry"]` | `SEPOLIA_DEFAULTS` in `config.ts` |
| `delegationRegistry` | `_defaults.py` hardcoded | `deployed.json` via `_deployed["delegationRegistry"]` | `SEPOLIA_DEFAULTS` in `config.ts` |
| `executionGate` | `_defaults.py` hardcoded | `deployed.json` via `_deployed["executionGate"]` | `SEPOLIA_DEFAULTS` in `config.ts` |

Both `poip-py` and `poip-ts` have these addresses as hardcoded defaults — no env
vars or config files needed. The pipeline (`agents/`, `config/`) reads from
`config/deployed.json`.

### Hardcoded in `config/config.py` (pipeline)

These are defaults, overridable by env var:

```python
USDC_ADDRESS            = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"  # Sepolia USDC
WETH_ADDRESS            = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"  # Sepolia WETH
UNISWAP_ROUTER_ADDRESS  = "0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E"  # SwapRouter02
ENS_REGISTRY_ADDRESS    = "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e"  # not overridable
ENS_RESOLVER_ADDRESS    = "0x8FADE66B79cC9f707aB26799354482EB93a5B7dD"  # not overridable
```

### Hardcoded in `contracts/script/Deploy.s.sol`

```solidity
address uniswapRouter = vm.envOr(
    "UNISWAP_ROUTER_ADDRESS",
    address(0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E)
);
```

This matches the Python default exactly.

### Hardcoded in `poip-ts/src/config.ts`

```typescript
const SEPOLIA_DEFAULTS = {
  agentRegistry:      '0xcD5954121BbE13a4867c2Df886e24E924D006883',
  intentRegistry:     '0xf2a52EAf8E2440F9aFa28aDA5426Bc2908DDc5b4',
  delegationRegistry: '0x51bF1E9C33ACF135E7C6ca83AD4Cf36d5B8BBa45',
  executionGate:      '0x076e8cd66be8B927CcB9adA63505e8027b209cb6',
};
const ENS_RESOLVER_ADDRESS = '0x8FADE66B79cC9f707aB26799354482EB93a5B7dD';
const ENS_REGISTRY_ADDRESS = '0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e';
```

### Hardcoded AXL public keys in `config/config.py`

These correspond to the ed25519 private keys committed in `agents/keys/`:

```python
ORCHESTRATOR_AXL_KEY = "f2395885c7d3f024bcf269e88cac9a072a977016365ae260118782c19240760b"
RESEARCH_AXL_KEY     = "7ab38976ea6550c626fc28382dd133c255054c5fe19ea4450ad0103771438a91"
EXECUTION_AXL_KEY    = "1f63933d14bf26298b076c1f69f25e323fc167b7133c233c6fb58f3410c29515"
```

These are used by the AXL `send_message()` calls as the `X-Destination-Peer-Id`
header values. They must match the actual public keys in the `.key` files. If you
regenerate the keys, update these values too.
