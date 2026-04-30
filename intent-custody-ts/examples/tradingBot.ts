/**
 * Trading bot example — end-to-end flow:
 *   1. User signs an intent authorising the orchestrator to trade on their behalf
 *   2. Orchestrator registers the intent on-chain
 *   3. Orchestrator delegates execution to an execution agent
 *   4. Execution agent verifies the chain and executes the swap
 *
 * Run with:
 *   npx ts-node examples/tradingBot.ts
 *
 * Required env vars (copy .env.example → .env):
 *   RPC_URL, CHAIN_ID
 *   AGENT_REGISTRY_ADDRESS, INTENT_REGISTRY_ADDRESS,
 *   DELEGATION_REGISTRY_ADDRESS, EXECUTION_GATE_ADDRESS
 *   USER_PRIVATE_KEY, ORCHESTRATOR_PRIVATE_KEY, EXECUTION_PRIVATE_KEY
 *   USDC_ADDRESS, WETH_ADDRESS
 */

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
  verifyChain,
  UNISWAP_V3,
} from '../src/index';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing env var: ${name}`);
  return v;
}

function nowPlusSecs(secs: number): bigint {
  return BigInt(Math.floor(Date.now() / 1000) + secs);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  // ── Config ────────────────────────────────────────────────────────────────

  const deployedJson = {
    agentRegistry: requireEnv('AGENT_REGISTRY_ADDRESS'),
    intentRegistry: requireEnv('INTENT_REGISTRY_ADDRESS'),
    delegationRegistry: requireEnv('DELEGATION_REGISTRY_ADDRESS'),
    executionGate: requireEnv('EXECUTION_GATE_ADDRESS'),
  };

  const config = loadConfig({
    ...loadDeployedAddresses(deployedJson),
  });

  const userKey = requireEnv('USER_PRIVATE_KEY');
  const orchestratorKey = requireEnv('ORCHESTRATOR_PRIVATE_KEY');
  const executionKey = requireEnv('EXECUTION_PRIVATE_KEY');

  const userAddress = new Wallet(userKey).address;
  const orchestratorAddress = new Wallet(orchestratorKey).address;
  const executionAddress = new Wallet(executionKey).address;

  const USDC = requireEnv('USDC_ADDRESS');
  const WETH = requireEnv('WETH_ADDRESS');

  console.log('User:         ', userAddress);
  console.log('Orchestrator: ', orchestratorAddress);
  console.log('Execution:    ', executionAddress);

  // ── Step 1: Build and sign the intent (user side) ────────────────────────

  const nonce = await getNonce(config, userAddress);
  console.log(`\nCurrent nonce for user: ${nonce}`);

  const intent = buildIntent({
    owner: userAddress,
    authorizedOrchestrator: orchestratorAddress,
    tokenIn: USDC,
    maxAmountIn: 100n * 10n ** 6n,   // 100 USDC (6 decimals)
    minAmountOut: 95n * 10n ** 18n,  // 95 WETH (18 decimals)
    allowedProtocols: ['Uniswap-V3'],
    deadline: nowPlusSecs(3600),      // 1 hour
    nonce,
  });

  const signature = await signIntent(intent, userKey, config);
  console.log('\nIntent signed:', intent);
  console.log('Signature:    ', signature);

  // ── Step 2: Register the intent (orchestrator side) ──────────────────────

  const orchestratorClient = new ContractClient(orchestratorKey, config);

  console.log('\nRegistering intent on-chain...');
  const intentId = await orchestratorClient.registerIntent(intent, signature);
  console.log('Intent ID:', intentId);

  // ── Step 3: Delegate execution to the execution agent ────────────────────

  console.log('\nDelegating to execution agent...');
  const delegationId = await orchestratorClient.delegateFromRoot(
    intentId,
    {
      maxAmountIn: intent.maxAmountIn,
      minAmountOut: intent.minAmountOut,
      allowedProtocols: intent.allowedProtocols,
      deadline: intent.deadline,
    },
    executionAddress,
  );
  console.log('Delegation ID:', delegationId);

  // ── Step 4: Execution agent verifies and executes the swap ───────────────

  const txParams = {
    amountIn: 100n * 10n ** 6n,
    minAmountOut: 95n * 10n ** 18n,
    protocol: UNISWAP_V3,
    tokenIn: USDC,
    tokenOut: WETH,
    recipient: userAddress,
  };

  console.log('\nVerifying delegation chain before execution...');
  const isValid = await verifyChain(delegationId, txParams, config);
  if (!isValid) {
    throw new Error('Chain verification failed — aborting swap');
  }
  console.log('Chain verified ✓');

  console.log('\nExecuting swap...');
  const executionClient = new ContractClient(executionKey, config);
  const txHash = await executionClient.executeSwap(delegationId, txParams);
  console.log('Swap executed! tx:', txHash);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
