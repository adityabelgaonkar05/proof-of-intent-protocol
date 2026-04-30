# intent-custody

TypeScript SDK for the [Proof of Intent Protocol](https://github.com/your-org/proof-of-intent-protocol).

Mirrors the Python SDK (`utils/contract_client.py`, `utils/sign_intent.py`, `utils/protocol_ids.py`) exactly, using **ethers v6**.

## Installation

```bash
npm install intent-custody ethers
```

## Quick start

```typescript
import * as dotenv from 'dotenv';
dotenv.config();

import { Wallet } from 'ethers';
import {
  loadConfig,
  loadDeployedAddresses,
  buildIntent,
  signIntent,
  getNonce,
  ContractClient,
  UNISWAP_V3,
} from 'intent-custody';

const config = loadConfig({
  ...loadDeployedAddresses({
    agentRegistry:      process.env.AGENT_REGISTRY_ADDRESS!,
    intentRegistry:     process.env.INTENT_REGISTRY_ADDRESS!,
    delegationRegistry: process.env.DELEGATION_REGISTRY_ADDRESS!,
    executionGate:      process.env.EXECUTION_GATE_ADDRESS!,
  }),
});

const userKey = process.env.USER_PRIVATE_KEY!;
const userAddress = new Wallet(userKey).address;

// 1. Build and sign the intent (user side)
const nonce = await getNonce(config, userAddress);

const intent = buildIntent({
  owner:                   userAddress,
  authorizedOrchestrator:  process.env.ORCHESTRATOR_ADDRESS!,
  tokenIn:                 process.env.USDC_ADDRESS!,
  maxAmountIn:             100n * 10n ** 6n,  // 100 USDC
  minAmountOut:            95n  * 10n ** 18n, // 95 WETH
  allowedProtocols:        ['Uniswap-V3'],    // hashed to bytes32 automatically
  deadline:                BigInt(Math.floor(Date.now() / 1000) + 3600),
  nonce,
});

const signature = await signIntent(intent, userKey, config);

// 2. Register on-chain (orchestrator side)
const orchestratorClient = new ContractClient(process.env.ORCHESTRATOR_PRIVATE_KEY!, config);
const intentId = await orchestratorClient.registerIntent(intent, signature);
console.log('Intent ID:', intentId);

// 3. Delegate to an execution agent
const delegationId = await orchestratorClient.delegateFromRoot(
  intentId,
  {
    maxAmountIn:      intent.maxAmountIn,
    minAmountOut:     intent.minAmountOut,
    allowedProtocols: intent.allowedProtocols,
    deadline:         intent.deadline,
  },
  process.env.EXECUTION_AGENT_ADDRESS!,
);
console.log('Delegation ID:', delegationId);

// 4. Execute the swap (execution agent side)
const executionClient = new ContractClient(process.env.EXECUTION_PRIVATE_KEY!, config);
const txHash = await executionClient.executeSwap(delegationId, {
  amountIn:     100n * 10n ** 6n,
  minAmountOut: 95n  * 10n ** 18n,
  protocol:     UNISWAP_V3,
  tokenIn:      process.env.USDC_ADDRESS!,
  tokenOut:     process.env.WETH_ADDRESS!,
  recipient:    userAddress,
});
console.log('Swap tx:', txHash);
```

## Configuration

### Environment variables

| Variable                    | Default                                          | Description                          |
|-----------------------------|--------------------------------------------------|--------------------------------------|
| `RPC_URL`                   | `https://ethereum-sepolia-rpc.publicnode.com`   | JSON-RPC endpoint                    |
| `CHAIN_ID`                  | `11155111`                                      | EVM chain ID                         |
| `AGENT_REGISTRY_ADDRESS`    | —                                               | Deployed AgentRegistry address       |
| `INTENT_REGISTRY_ADDRESS`   | —                                               | Deployed IntentRegistry address      |
| `DELEGATION_REGISTRY_ADDRESS` | —                                             | Deployed DelegationRegistry address  |
| `EXECUTION_GATE_ADDRESS`    | —                                               | Deployed ExecutionGate address       |
| `ENS_NAME`                  | `""` (disabled)                                 | ENS name for intent text records     |
| `ZG_API_KEY`                | `""` (disabled)                                 | 0G decentralised storage API key     |
| `ZG_RPC_URL`                | `https://evmrpc-testnet.0g.ai`                  | 0G RPC endpoint                      |
| `ZG_INDEXER_URL`            | `https://indexer-storage-testnet-turbo.0g.ai`   | 0G indexer endpoint                  |

### Passing config explicitly

```typescript
import { loadConfig } from 'intent-custody';

const config = loadConfig({
  rpcUrl:                   'https://mainnet.infura.io/v3/YOUR_KEY',
  chainId:                  1,
  intentRegistryAddress:    '0x...',
  agentRegistryAddress:     '0x...',
  delegationRegistryAddress:'0x...',
  executionGateAddress:     '0x...',
});
```

### Using a deployed.json file

```typescript
import { loadConfig, loadDeployedAddresses } from 'intent-custody';
import deployed from './config/deployed.json';

const config = loadConfig(loadDeployedAddresses(deployed));
```

## API

### `buildIntent(params)`

Builds an `IntentData` object. Protocol names (e.g. `"Uniswap-V3"`) are hashed to `bytes32` automatically.

```typescript
const intent = buildIntent({
  owner, authorizedOrchestrator, tokenIn,
  maxAmountIn, minAmountOut,
  allowedProtocols: ['Uniswap-V3', 'Curve'],
  deadline, nonce,
});
```

### `signIntent(intent, privateKey, config)`

EIP-712 signs an `IntentData`. Returns a `0x`-prefixed hex signature.

### `ContractClient`

The main class. Accepts a private key and a `Config` object.

| Method | Description |
|--------|-------------|
| `registerIntent(intent, signature)` | Register a signed intent; returns `intentId` |
| `delegateFromRoot(intentId, scope, delegateTo)` | Delegate from a root intent; returns `delegationId` |
| `delegateFromDelegation(delegationId, scope, delegateTo)` | Sub-delegate; returns `delegationId` |
| `executeSwap(delegationId, txParams)` | Execute a delegated swap; returns tx hash |
| `verifyChain(delegationId, txParams)` | Read-only chain verification; returns `bool` |
| `storeIntentOn0g(intent, intentId)` | Non-blocking 0G storage (stub — implement with your 0G SDK) |
| `storeIntentOnEns(intentId, ensName)` | Non-blocking ENS text-record update |

### Module-level helpers

These mirror the Python module-level functions for ad-hoc use without a `ContractClient` instance.

| Function | Description |
|----------|-------------|
| `getNonce(config, owner)` | Read current nonce from IntentRegistry |
| `getDomainSeparator(config)` | Read EIP-712 domain separator |
| `registerIntentRaw(intent, sig, key, config)` | Register intent, returns raw `TransactionReceipt` |
| `extractIntentIdFromReceipt(receipt, config)` | Parse `intentId` from a receipt |
| `delegateFromRoot(intentId, scope, to, key, config)` | Delegate, returns raw receipt |
| `delegateFromDelegation(parentId, scope, to, key, config)` | Sub-delegate, returns raw receipt |
| `extractDelegationIdFromReceipt(receipt, config)` | Parse `delegationId` from a receipt |
| `getDelegation(delegationId, config)` | Fetch `DelegationData` from chain |
| `verifyChain(delegationId, txParams, config)` | Verify delegation chain (read-only) |
| `executeSwap(delegationId, txParams, key, config)` | Execute swap, returns raw receipt |

### Protocol IDs

```typescript
import { UNISWAP_V3, CURVE, BALANCER_V2, AAVE_V3, ONEINCH, protocolId, protocolName } from 'intent-custody';

// Pre-computed keccak256 hashes
console.log(UNISWAP_V3); // 0x...

// Convert a name to its hash
const id = protocolId('Uniswap-V3');

// Convert a hash back to its name
const name = protocolName(UNISWAP_V3); // "Uniswap-V3"
```

## Running the example

```bash
cd examples
cp ../.env.example .env   # fill in your keys and addresses
npx ts-node tradingBot.ts
```

## Building

```bash
npm install
npm run build
# Output: dist/
```

## Types

```typescript
interface IntentData {
  owner: string;
  authorizedOrchestrator: string;
  tokenIn: string;
  maxAmountIn: bigint;
  minAmountOut: bigint;
  allowedProtocols: string[];  // bytes32 hex strings
  deadline: bigint;
  nonce: bigint;
}

interface ScopeData {
  maxAmountIn: bigint;
  minAmountOut: bigint;
  allowedProtocols: string[];
  deadline: bigint;
}

interface TxParamsData {
  amountIn: bigint;
  minAmountOut: bigint;
  protocol: string;   // bytes32 hex string
  tokenIn: string;
  tokenOut: string;
  recipient: string;
}

interface DelegationData {
  parentId: string;
  isRootIntent: boolean;
  scope: ScopeData;
  delegatedTo: string;
  executed: boolean;
}
```
