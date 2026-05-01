# POIP Full-Stack Demo

A realistic DeFi trading bot pipeline demonstrating every feature of the
Proof-of-Intent Protocol: on-chain intent signing, scope-narrowing delegations,
live market data, and cryptographic attack prevention.

## Scenario

A user authorizes: _"Find the best USDC yield opportunity and execute it, max
400 USDC, only Uniswap or Aave, valid for 2 hours."_

Four specialized agents collaborate:

| Agent | Role |
|-------|------|
| **User** | Compiles intent (optionally via Claude), signs with EIP-712, registers on Sepolia |
| **Orchestrator** | Loads intent from chain, creates root delegation to Research Agent |
| **Research** | Fetches live ETH price from CoinGecko, calculates slippage-adjusted minAmountOut, narrows scope to Uniswap V3 only |
| **Execution** | Verifies the full delegation chain, executes the swap on Sepolia |

Then the demo replays with a compromised Research Agent that tries to move 800 USDC
instead of 400. The smart contract rejects it. Zero funds at risk.

## Requirements

- **Node.js 18+** (for built-in `fetch`)
- **4 Sepolia testnet wallets** with ETH for gas
- User wallet optionally needs Sepolia USDC to execute the swap
  (chain verification runs regardless — demo is fully meaningful without USDC)

## Setup

```bash
# 1. Install dependencies (builds the proof-of-intent package locally)
cd agents/demo_app
npm install

# 2. Configure environment
cp .env.example .env
# Edit .env — fill in PRIVATE_KEY, DEPLOYER_KEY, RESEARCH_KEY, EXECUTION_KEY

# 3. Run
npx tsx src/index.ts
```

If you have `CLAUDE_API_KEY` set, the User Agent will parse the goal string
with Claude Haiku and extract the intent parameters dynamically.

## What happens on-chain

Every step hits Ethereum Sepolia:

1. `IntentRegistry.registerIntent()` — user's signed authorization stored immutably
2. `DelegationRegistry.delegateFromRoot()` — orchestrator creates first delegation
3. `DelegationRegistry.delegateFromDelegation()` — research agent narrows scope
4. `ExecutionGate.verifyChain()` — dry-run: traverses entire chain against root intent
5. `ExecutionGate.executeSwap()` — live Uniswap V3 swap (if wallet has USDC)
6. Attack: `delegateFromDelegation()` with 800 USDC → **reverts with "Amount exceeds scope"**

All contract addresses are the hardcoded Sepolia deployment in `proof-of-intent` v0.1.1.

## Architecture

Each agent runs as a separate OS process with its own AXL Yggdrasil P2P node.
Agents communicate **exclusively via AXL** — no direct function calls, no shared memory.

```
[User Agent]  ──AXL──▶  [Orchestrator]  ──AXL──▶  [Research Agent]  ──AXL──▶  [Execution Agent]
     ▲                        │                                                        │
     └────────────────────────┘  (COMPLETE/FAILED sent directly to Orchestrator) ◀────┘
```

AXL nodes:
- Orchestrator: TLS listen `127.0.0.1:9001`, API port `9002`
- Research:     Peer `9001`, API port `9012`
- Execution:    Peer `9001`, API port `9022`
- User:         Peer `9001`, API port `9042`

The user's AXL key (`agents/keys/user.key`) is auto-generated if it doesn't exist.

## Using the published npm package

The `package.json` uses `file:../../poip_ts` for local development.
To use the published package instead:

```bash
npm install proof-of-intent
```

Then update `package.json` to `"proof-of-intent": "^0.1.1"`.
