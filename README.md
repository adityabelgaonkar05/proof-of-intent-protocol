# Proof of Intent Protocol

**Cryptographic intent custody for AI agent pipelines — sign once, delegate safely, enforce on-chain.**

---

## The Problem

When a user delegates a financial operation to an AI pipeline — "swap my 500 USDC for ETH" — the instruction gets passed between multiple agents: an orchestrator, a research agent that finds the best route, and an execution agent that calls the DEX. Any one of those agents can be compromised, hallucinate, or receive a maliciously crafted webpage that tells it to "actually, send 800 USDC to this address." There is no standard way to prove that what the execution agent does matches what the user originally authorized. The user's intent lives only in the model's context window; there is nothing on-chain to enforce it.

This protocol fixes that. The user signs a typed intent once — maximum spend, minimum output, allowed protocols, deadline — and it is committed to the blockchain before any agent runs. Every delegation in the pipeline is also on-chain and must be a strict subset of the one above it. The execution gate walks the entire chain back to the root intent before releasing a single token. A compromised research agent that tries to widen the scope gets an immediate contract revert. No AI scored it. No human approved it. The math was wrong — 800 > 500 — so the chain rejected it.

---

## How It Works

### Sign

The user builds an `Intent` struct — `tokenIn`, `maxAmountIn`, `minAmountOut`, `allowedProtocols[]`, `deadline`, `nonce` — and signs it with EIP-712. The signature binds the intent to a specific chain, contract address, and nonce, making it both tamper-evident and replay-safe. `IntentRegistry.registerIntent()` stores the hash on-chain; the intent is now immutable.

### Delegate

The orchestrator calls `DelegationRegistry.delegateFromRoot()`, creating a `Delegation` record that points at the root intent and names a child agent with a **narrowed** scope. That child can call `delegateFromDelegation()` to sub-delegate further, again only narrowing. The registry enforces all four narrowing rules at write time — a bad scope is rejected at delegation creation, before execution is even attempted.

| Property          | Child scope must…                    |
|-------------------|--------------------------------------|
| `maxAmountIn`     | ≤ parent `maxAmountIn`               |
| `minAmountOut`    | ≥ parent `minAmountOut`              |
| `allowedProtocols`| ⊆ parent `allowedProtocols`         |
| `deadline`        | ≤ parent `deadline`                  |

### Enforce

Before any token moves, `ExecutionGate.verifyChain()` walks the delegation chain from the leaf back to the root intent, re-checking every scope constraint plus the root intent's `tokenIn`, `maxAmountIn`, and `deadline`. Only after the full walk succeeds does `executeSwap()` mark the delegation as executed, pull USDC from the user via `transferFrom`, approve the Uniswap router, and call `exactInputSingle`. The `SwapExecuted` event is emitted only on the far side of a real, confirmed swap.

---

## Architecture

```
  User Wallet
      │  EIP-712 signed intent
      ▼
 ┌─────────────────────────────┐
 │       IntentRegistry        │  registerIntent(intent, sig)
 │  immutable hash on-chain    │  → intentId
 └──────────────┬──────────────┘
                │
                ▼  Orchestrator wallet
 ┌─────────────────────────────┐
 │     DelegationRegistry      │  delegateFromRoot(intentId, scope, researchAgent)
 │  scope ⊆ root intent        │  → delegationId_1
 └──────────────┬──────────────┘
                │
                ▼  Research Agent wallet
 ┌─────────────────────────────┐
 │     DelegationRegistry      │  delegateFromDelegation(delId_1, scope, execAgent)
 │  scope ⊆ parent scope       │  → delegationId_2
 └──────────────┬──────────────┘
                │
                ▼  Execution Agent wallet
 ┌─────────────────────────────┐
 │       ExecutionGate         │  verifyChain(delId_2, txParams)  ← view call, free
 │  walks chain → root intent  │  checks every hop, all 4 rules + root tokenIn/deadline
 └──────────────┬──────────────┘
                │  chain verified ✓
                ▼
 ┌─────────────────────────────┐
 │       ExecutionGate         │  executeSwap(delId_2, txParams)
 │  1. markExecuted            │  ← checks-effects-interactions order
 │  2. transferFrom(user→gate) │
 │  3. approve(router, amountIn)│
 └──────────────┬──────────────┘
                │
                ▼
 ┌─────────────────────────────┐
 │   Uniswap V3 SwapRouter02   │  exactInputSingle(USDC→WETH, fee=3000)
 │  0x3bFA4769...Ae48 (Sepolia)│  delivers WETH to params.recipient (user)
 └─────────────────────────────┘
```

Agent messages flow over AXL (Yggdrasil-routed, ed25519-authenticated):

```
  Orchestrator ──TASK──▶ Research Agent ──EXECUTE──▶ Execution Agent
       ▲                                                    │
       └─────────────────COMPLETE / FAILED─────────────────┘
```

---

## Deployed Contracts — Ethereum Sepolia

| Contract              | Address                                    | Etherscan |
|-----------------------|--------------------------------------------|-----------|
| `AgentRegistry`       | `0xcD5954121BbE13a4867c2Df886e24E924D006883` | [view](https://sepolia.etherscan.io/address/0xcD5954121BbE13a4867c2Df886e24E924D006883) |
| `IntentRegistry`      | `0xf2a52EAf8E2440F9aFa28aDA5426Bc2908DDc5b4` | [view](https://sepolia.etherscan.io/address/0xf2a52EAf8E2440F9aFa28aDA5426Bc2908DDc5b4) |
| `DelegationRegistry`  | `0x51bF1E9C33ACF135E7C6ca83AD4Cf36d5B8BBa45` | [view](https://sepolia.etherscan.io/address/0x51bF1E9C33ACF135E7C6ca83AD4Cf36d5B8BBa45) |
| `ExecutionGate`       | `0x076e8cd66be8B927CcB9adA63505e8027b209cb6` | [view](https://sepolia.etherscan.io/address/0x076e8cd66be8B927CcB9adA63505e8027b209cb6) |

> All four contracts were redeployed together. `ExecutionGate` includes the Uniswap V3
> SwapRouter02 address in its constructor and performs real swaps.

Tokens used in the demo (Ethereum Sepolia):

| Token  | Address                                      |
|--------|----------------------------------------------|
| USDC   | `0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238` |
| WETH   | `0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14` |

---

## Quick Start — Python SDK

```bash
pip install web3 eth-account python-dotenv
```

```python
import time
from utils.sign_intent import build_intent, sign_intent
from utils.contract_client import ContractClient
from config.config import (
    USER_ADDRESS, ORCHESTRATOR_ADDRESS, EXECUTION_AGENT_ADDRESS,
    USDC_ADDRESS, WETH_ADDRESS, EXECUTION_GATE_ADDRESS,
)
from web3 import Web3

UNISWAP_V3 = Web3.keccak(text="Uniswap-V3").hex()

# 1. User signs an intent
user_client = ContractClient(USER_PRIVATE_KEY)
nonce = user_client.intent_registry.functions.nonces(USER_ADDRESS).call()

intent = build_intent(
    owner=USER_ADDRESS,
    authorized_orchestrator=ORCHESTRATOR_ADDRESS,
    token_in=USDC_ADDRESS,
    max_amount_in=500_000_000,              # 500 USDC (6 decimals)
    min_amount_out=150_000_000_000_000_000, # 0.15 WETH (18 decimals)
    allowed_protocols=["Uniswap-V3"],
    deadline=int(time.time()) + 3600,
    nonce=nonce,
)
sig = sign_intent(intent, USER_PRIVATE_KEY)

# 2. Register on-chain; non-blocking 0G and ENS storage happens automatically
intent_id = user_client.register_intent(intent, sig)

# 3. Delegate — scope narrows at each hop
scope = {
    "maxAmountIn":      400_000_000,
    "minAmountOut":     180_000_000_000_000_000,
    "allowedProtocols": [UNISWAP_V3],
    "deadline":         int(time.time()) + 3300,
}
orch_client = ContractClient(ORCHESTRATOR_PRIVATE_KEY)
delegation_id = orch_client.delegate_from_root(intent_id, scope, EXECUTION_AGENT_ADDRESS)

# 4. User approves ExecutionGate to pull USDC, then execution agent swaps
user_client.ensure_token_approval(USDC_ADDRESS, EXECUTION_GATE_ADDRESS, 400_000_000)

tx_params = {
    "amountIn":     400_000_000,
    "minAmountOut": 180_000_000_000_000_000,
    "protocol":     UNISWAP_V3,
    "tokenIn":      USDC_ADDRESS,
    "tokenOut":     WETH_ADDRESS,
    "recipient":    USER_ADDRESS,
}
exec_client = ContractClient(EXECUTION_PRIVATE_KEY)
tx_hash = exec_client.execute_swap(delegation_id, tx_params)
print(f"Swap: https://sepolia.etherscan.io/tx/{tx_hash}")
```

---

## Quick Start — TypeScript SDK

```bash
cd poip_ts
npm install
npm run build          # compiles to dist/
```

Or import directly from source in a ts-node project:

```typescript
import * as dotenv from 'dotenv';
dotenv.config();

import { Wallet } from 'ethers';
import {
  loadConfig, loadDeployedAddresses,
  buildIntent, signIntent, getNonce,
  ContractClient, verifyChain, UNISWAP_V3,
} from 'proof-of-intent';

const config = loadConfig({
  ...loadDeployedAddresses(require('./config/deployed.json')),
});

const userKey   = process.env.USER_PRIVATE_KEY!;
const orchKey   = process.env.ORCHESTRATOR_PRIVATE_KEY!;
const execKey   = process.env.EXECUTION_PRIVATE_KEY!;
const USDC      = process.env.USDC_ADDRESS!;
const WETH      = process.env.WETH_ADDRESS!;

const userAddress = new Wallet(userKey).address;
const orchAddress = new Wallet(orchKey).address;
const execAddress = new Wallet(execKey).address;

// 1. Sign the intent
const nonce  = await getNonce(config, userAddress);
const intent = buildIntent({
  owner:                  userAddress,
  authorizedOrchestrator: orchAddress,
  tokenIn:                USDC,
  maxAmountIn:            500n * 10n**6n,
  minAmountOut:           150n * 10n**15n,
  allowedProtocols:       ['Uniswap-V3'],
  deadline:               BigInt(Math.floor(Date.now() / 1000) + 3600),
  nonce,
});
const sig = await signIntent(intent, userKey, config);

// 2. Register on-chain (ENS linking happens non-blocking if ENS_NAME is set)
const orchClient = new ContractClient(orchKey, config);
const intentId   = await orchClient.registerIntent(intent, sig);

// 3. Delegate to execution agent
const scope = {
  maxAmountIn:      intent.maxAmountIn,
  minAmountOut:     intent.minAmountOut,
  allowedProtocols: intent.allowedProtocols,
  deadline:         intent.deadline,
};
const delegationId = await orchClient.delegateFromRoot(intentId, scope, execAddress);

// 4. Verify then execute
const txParams = {
  amountIn:     500n * 10n**6n,
  minAmountOut: 150n * 10n**15n,
  protocol:     UNISWAP_V3,
  tokenIn:      USDC,
  tokenOut:     WETH,
  recipient:    userAddress,
};
const ok = await verifyChain(delegationId, txParams, config);
if (!ok) throw new Error('chain verification failed');

const execClient = new ContractClient(execKey, config);
const txHash = await execClient.executeSwap(delegationId, txParams);
console.log('https://sepolia.etherscan.io/tx/' + txHash);
```

A full end-to-end example with env-var loading is in [poip_ts/examples/tradingBot.ts](poip_ts/examples/tradingBot.ts).

---

## Agent Pipeline Setup

The full pipeline runs three Python agents that communicate over AXL — a local Yggdrasil network. Each agent gets its own AXL node.

### 1. Build the AXL binary

The binary must live at `vendor/axl/node` — that is the path `agents/axl_test.py` and the
agent startup commands below expect.

```bash
cd vendor/axl
go build -o node ./cmd/node/
cd ../..
```

### 2. Start the three AXL nodes

Each node reads a config file from `agents/axl_configs/`. Start them from the **project root** (paths in the config files are relative to the root):

```bash
# Terminal 1 — orchestrator node (bootstrap peer, listens on :9001)
./vendor/axl/node -config agents/axl_configs/orchestrator.json &

# Terminal 2 — research agent node (connects to orchestrator)
./vendor/axl/node -config agents/axl_configs/research.json &

# Terminal 3 — execution agent node (connects to orchestrator)
./vendor/axl/node -config agents/axl_configs/execution.json &
```

Node HTTP APIs are available at:
- Orchestrator: `http://127.0.0.1:9002`
- Research agent: `http://127.0.0.1:9012`
- Execution agent: `http://127.0.0.1:9022`

### 3. Run the agents

After the AXL nodes are up and the Yggdrasil spanning tree has propagated (a few seconds):

```bash
# Terminal 4 — execution agent (listens for EXECUTE messages)
python -m agents.execution_agent

# Terminal 5 — research agent (listens for TASK messages, creates sub-delegation)
python -m agents.research_agent

# Terminal 6 — orchestrator (call once with an intentId from a prior registerIntent)
python -m agents.orchestrator <intentId> "swap 400 USDC for max WETH"
```

To run the research agent in **compromised mode** (demonstrates the attack scenario):

```bash
python -m agents.research_agent --compromised
```

The compromised agent attempts a delegation with `maxAmountIn=800 USDC` against a root intent
that only authorised 500 USDC. The `DelegationRegistry` rejects it with `"Amount exceeds scope"`.

### Required env vars for the pipeline

```
DEPLOYER_PRIVATE_KEY    # orchestrator wallet
RESEARCH_PRIVATE_KEY    # research agent wallet
EXECUTION_PRIVATE_KEY   # execution agent wallet
USER_PRIVATE_KEY        # user wallet (for approvals in demo)
RPC_URL                 # Sepolia RPC endpoint
```

---

## Environment Variables

All variables are read from `.env` (copy from `.env.example`).

| Variable                   | Required   | Description                                               | Example |
|----------------------------|------------|-----------------------------------------------------------|---------|
| `RPC_URL`                  | yes        | Ethereum JSON-RPC endpoint                                | `https://ethereum-sepolia-rpc.publicnode.com` |
| `CHAIN_ID`                 | no         | EVM chain ID (default: `11155111` for Sepolia)            | `11155111` |
| `DEPLOYER_PRIVATE_KEY`     | yes        | Orchestrator agent's Ethereum private key                 | `0xabc...` |
| `USER_PRIVATE_KEY`         | yes        | User's Ethereum private key (signs intents, holds USDC)   | `0xdef...` |
| `RESEARCH_PRIVATE_KEY`     | yes        | Research agent's Ethereum private key                     | `0x123...` |
| `EXECUTION_PRIVATE_KEY`    | yes        | Execution agent's Ethereum private key                    | `0x456...` |
| `ORCHESTRATOR_ADDRESS`     | deploy     | Orchestrator address (passed to Deploy.s.sol for agent registration) | `0x...` |
| `RESEARCH_ADDRESS`         | deploy     | Research agent address (same purpose)                     | `0x...` |
| `EXECUTION_ADDRESS`        | deploy     | Execution agent address (same purpose)                    | `0x...` |
| `USDC_ADDRESS`             | no         | USDC token on Sepolia (default: `0x1c7D4B196...`)        | `0x1c7D4B...` |
| `WETH_ADDRESS`             | no         | WETH token on Sepolia (default: `0xfFf99767...`)         | `0xfFf997...` |
| `UNISWAP_ROUTER_ADDRESS`   | no         | SwapRouter02 on Sepolia (default: `0x3bFA4769...`)       | `0x3bFA47...` |
| `USE_CLAUDE`               | no         | `true` to use Claude as the LLM, `false` for OpenAI (default: `false`) | `false` |
| `CLAUDE_API_KEY`           | if USE_CLAUDE=true  | Anthropic API key                              | `sk-ant-...` |
| `OPENAI_API_KEY`           | if USE_CLAUDE=false | OpenAI API key                                 | `sk-...` |
| `ZG_API_KEY`               | no         | 0G network private key (hex); intent storage is skipped if unset | `0x789...` |
| `ZG_RPC_URL`               | no         | 0G EVM RPC (default: `https://evmrpc-testnet.0g.ai`)     | — |
| `ZG_INDEXER_URL`           | no         | 0G storage indexer (default: `https://indexer-storage-testnet-turbo.0g.ai`) | — |
| `ENS_NAME`                 | no         | ENS name to link active intents (e.g. `yourname.eth`); skipped if unset | `alice.eth` |

Contract addresses for Python are read from `config/deployed.json` (written by `deploy.sh`).
For TypeScript, pass a `Config` object to `loadConfig()` or set the corresponding env vars:
`AGENT_REGISTRY_ADDRESS`, `INTENT_REGISTRY_ADDRESS`, `DELEGATION_REGISTRY_ADDRESS`, `EXECUTION_GATE_ADDRESS`.

---

## Deploying

```bash
cp .env.example .env
# Fill in RPC_URL, DEPLOYER_PRIVATE_KEY, and the agent address vars

./deploy.sh
# Contracts are deployed, addresses written to config/deployed.json
```

To set a specific Uniswap router address (defaults to Sepolia SwapRouter02):

```bash
UNISWAP_ROUTER_ADDRESS=0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E ./deploy.sh
```

---

## Running Tests

### Forge (contract unit tests)

```bash
cd contracts
forge test
```

58 tests across four suites — all pass:

| Suite                    | Tests | What is covered |
|--------------------------|-------|-----------------|
| `AgentRegistry.t.sol`    | 4     | Register, freeze, unfreeze, duplicate prevention |
| `IntentRegistry.t.sol`   | 13    | EIP-712 signature validation, nonce replay protection, revocation, deadline enforcement |
| `DelegationRegistry.t.sol` | 22  | Scope narrowing at each delegation level, replay protection, frozen agents, multi-hop scope inheritance |
| `ExecutionGate.t.sol`    | 19    | `verifyChain` happy path and all 6 revert cases, `executeSwap` with real `MockERC20` token transfers through `MockSwapRouter`, multi-hop end-to-end execution |

`ExecutionGate` tests use two mock contracts from `contracts/test/mocks/`:
- `MockERC20` — open-mint ERC20 used as the swap input token
- `MockSwapRouter` — accepts `exactInputSingle`, pulls tokenIn from the caller, no real pool required

### Python integration test (against local Anvil)

Deploys all contracts fresh on a local Anvil node, runs a complete 10-step scenario:

```bash
# Terminal 1
anvil --port 8545

# Terminal 2
python -m utils.integration_test
```

Steps:
1. Deploy AgentRegistry, IntentRegistry, DelegationRegistry, MockERC20, MockSwapRouter, ExecutionGate
2. Register orchestrator, research, and execution agents
3. Build and EIP-712 sign an intent (500 USDC, Uniswap-V3, 60 min)
4. Register the intent on-chain
5. Delegate from root intent to research agent (400 USDC scope)
6. Sub-delegate from research to execution agent (300 USDC scope)
7. Call `verifyChain` as a view — must return `True`
8. Mint MockERC20 tokens to the recipient; approve ExecutionGate
9. Call `executeSwap` — marks delegation as executed, pulls tokens, routes through mock router
10. Attempt a malicious delegation (800 USDC against a 400 USDC scope) — must revert with `"Amount exceeds scope"`

---

## Running the Demo

`agents/demo.py` runs two live scenarios on Ethereum Sepolia. It requires funded wallets — the user wallet needs Sepolia ETH for gas and Sepolia USDC for the swap.

```bash
python -m agents.demo
```

**Scenario 1 — Clean pipeline:**

1. User builds a 500 USDC → 0.15 WETH intent, signs it with EIP-712
2. Intent is registered on-chain (intentId printed, links to Etherscan)
3. Orchestrator delegates to Research Agent with the same scope
4. Research Agent narrows scope to 400 USDC / 0.18 WETH and sub-delegates to Execution Agent
5. Execution Agent calls `verifyChain` (view call) — all 4 scope rules checked
6. User's USDC allowance to ExecutionGate is checked; approval sent if needed
7. `executeSwap` is called — USDC pulled from user, routed through Uniswap V3, WETH delivered
8. Before/after USDC, WETH, and ETH balances of the user wallet are printed
9. Transaction hash and Etherscan link are printed

**Scenario 2 — Attack path:**

1. Fresh intent registered (500 USDC limit)
2. Orchestrator delegates (full scope)
3. Research Agent "reads a malicious webpage" suggesting 800 USDC
4. Research Agent attempts `delegateFromDelegation` with `maxAmountIn = 800 USDC`
5. The `DelegationRegistry` reverts: `"Amount exceeds scope"`
6. Zero USDC moves; the attack is blocked entirely by contract math

Expected terminal output for Scenario 2:

```
  Research Agent attempting: maxAmountIn = 800 USDC
  (Root intent only authorised: 500 USDC)
  TRANSACTION REVERTED
  Revert reason: Amount exceeds scope
```

---

## Sponsor Integrations

### Uniswap V3

`ExecutionGate` calls `ISwapRouter.exactInputSingle` on SwapRouter02
(`0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E` on Sepolia) at the moment of execution.
This is not a wrapper or a simulation — it is the actual DeFi swap that delivers WETH to the
user's wallet. The integration uses the 0.3% fee tier for USDC/WETH, no price limit
(`sqrtPriceLimitX96 = 0`), and relies entirely on `amountOutMinimum` (the `minAmountOut`
from the intent) for slippage protection. The swap is gated behind a full delegation chain
verification and only executes if every scope constraint in every hop back to the root intent
passes. See [FEEDBACK.md](FEEDBACK.md) for honest integration notes.

### ENS

When `registerIntent()` succeeds, the returned `intentId` is written to the `"active-intent"`
text record on the configured ENS name via the public resolver's `setText()`. This means any
off-chain observer can do `resolver.text(namehash("yourname.eth"), "active-intent")` to find
the user's current on-chain intent without knowing the contract address or scanning logs. The
call is non-blocking — if ENS fails, the intent registration still succeeds. Implemented in
both the Python SDK (`ContractClient.store_intent_on_ens`) and the TypeScript SDK
(`ContractClient.storeIntentOnEns`), which both look up the live resolver from the ENS
registry rather than hardcoding it.

### 0G Decentralised Storage

After a successful `registerIntent`, the intent metadata (intentId, owner, amounts, protocols,
deadline) is serialised to JSON and uploaded to 0G decentralised storage as a content-addressed
blob. The root-hash reference is printed to stdout. This provides a tamper-evident off-chain
record of every intent that any participant in the pipeline can independently retrieve and
verify. The Python upload runs in a subprocess (to avoid namespace collisions between the 0G
SDK and the project's own `config`/`utils` packages). Set `ZG_API_KEY` in `.env` to enable;
the integration is skipped silently without it. The TypeScript SDK's `storeIntentOn0g` method
is a documented stub — the upload endpoint is available but the 0G JavaScript SDK was not
integrated in this version.

### AXL

The three agents (Orchestrator, Research, Execution) communicate exclusively through AXL, a
lightweight peer-to-peer network built on Yggdrasil routing with ed25519 node identities. Each
agent runs a local AXL node (`vendor/axl/`) and sends JSON messages to peer nodes by public
key — no broker, no central server. The Orchestrator sends a `TASK` message to the Research
Agent after creating the root delegation. The Research Agent forwards an `EXECUTE` message to
the Execution Agent after creating the sub-delegation. The Execution Agent reports `COMPLETE`
(with tx hash) or `FAILED` (with revert reason) back to the Orchestrator. Python talks to each
node only on localhost via a thin HTTP API (`/send`, `/recv`, `/topology`). The routing between
nodes happens inside the AXL network transparently.

---

## License

MIT
