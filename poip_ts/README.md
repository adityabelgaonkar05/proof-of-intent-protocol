# proof-of-intent

TypeScript SDK for the [Proof-of-Intent Protocol](https://github.com/proof-of-intent-protocol) —
on-chain intent registration, cryptographic delegation, and scope-enforced execution on
Ethereum Sepolia. Uses **ethers v6**.

## Install

```bash
npm install proof-of-intent
```

## Environment variables

```bash
# Required: your wallet private key (Sepolia testnet only)
PRIVATE_KEY=0x...

# Optional: only needed if you call compileIntent()
CLAUDE_API_KEY=sk-ant-...
```

## Five-line quickstart

```typescript
import { ContractClient, usdc, inHours, UNISWAP_V3 } from 'proof-of-intent';

// Instantiate — all contract addresses default to deployed Sepolia contracts
const client = new ContractClient({ privateKey: process.env.PRIVATE_KEY! });

// Register an intent (build + EIP-712 sign + on-chain register in one call)
const intentId = await client.createIntent({
  tokenIn:          '0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238', // Sepolia USDC
  maxAmountIn:      usdc(100),      // 100 USDC
  minAmountOut:     1n,
  allowedProtocols: ['Uniswap-V3'],
  deadline:         inHours(1),
});
console.log('intent registered:', intentId);

// Delegate execution rights to an agent address
import { buildScope } from 'proof-of-intent';
const delegationId = await client.delegateFromRoot(
  intentId,
  buildScope({ maxAmountIn: usdc(100), minAmountOut: 1n, allowedProtocols: ['Uniswap-V3'], deadline: inHours(1) }),
  client.wallet.address,   // delegate to self for demo
);
console.log('delegation created:', delegationId);
```

## Helpers

```typescript
import { usdc, weth, inMinutes, inHours, UNISWAP_V3 } from 'proof-of-intent';

usdc(500)          // → 500_000_000n   (500 USDC in raw units)
weth(0.15)         // → 150_000_000_000_000_000n
inMinutes(60)      // → Unix timestamp 60 minutes from now (bigint)
inHours(1)         // → Unix timestamp 1 hour from now (bigint)
UNISWAP_V3         // → '0x1cc...'  (bytes32 protocol ID as hex string)
```

## Overriding defaults

```typescript
const client = new ContractClient({
  privateKey: process.env.PRIVATE_KEY!,
  rpcUrl:     'https://my-node.example.com',
  chainId:    11155111,
  // intentRegistryAddress, delegationRegistryAddress, executionGateAddress...
});
```

## Natural-language intent compilation (optional)

No extra npm packages required — `compileIntent` uses native `fetch`.

```typescript
import { compileIntent, buildIntent, signIntent, loadConfig, getNonce } from 'proof-of-intent';

// Uses CLAUDE_API_KEY if set (claude-haiku-4-5-20251001), else OPENAI_API_KEY (gpt-5-mini).
// Set MODEL=<id> to override the default model for whichever provider is selected.
const compiled = await compileIntent('swap 500 USDC for WETH via Uniswap, deadline 1 hour');
// compiled: CompiledIntent {
//   tokenIn:          string   // ERC20 address
//   maxAmountIn:      bigint
//   minAmountOut:     bigint
//   allowedProtocols: string[]
//   deadline:         number   // Unix timestamp
// }

const config = loadConfig();
const nonce  = await getNonce(config, wallet.address);
const intent = buildIntent({
  owner:                  wallet.address,
  authorizedOrchestrator: wallet.address,
  tokenIn:                compiled.tokenIn,
  maxAmountIn:            compiled.maxAmountIn,
  minAmountOut:           compiled.minAmountOut,
  allowedProtocols:       compiled.allowedProtocols,
  deadline:               BigInt(compiled.deadline),
  nonce,
});
```

## Building from source

```bash
npm install
npm run build   # produces dist/ with .js and .d.ts
```


## Contributors

- [@adityabelgaonkar05](https://github.com/adityabelgaonkar05)
- [@akankshaagroya](https://github.com/akankshaagroya)
