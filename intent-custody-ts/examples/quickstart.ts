/**
 * Proof-of-Intent Protocol — TypeScript quickstart.
 *
 * Minimum .env requirements (project root .env is loaded automatically):
 *   DEPLOYER_PRIVATE_KEY=0x...
 *
 * USER_PRIVATE_KEY is optional — defaults to DEPLOYER_PRIVATE_KEY when not set.
 * Contract addresses are read automatically from config/deployed.json.
 * No RESEARCH_PRIVATE_KEY or EXECUTION_PRIVATE_KEY needed.
 *
 * Run from the intent-custody-ts directory:
 *   npx ts-node examples/quickstart.ts
 */

import * as dotenv from 'dotenv';
import * as path from 'path';

// Load .env from the project root (two levels up from intent-custody-ts/examples/)
dotenv.config({ path: path.resolve(__dirname, '../../.env') });

import { Wallet } from 'ethers';
import {
  loadConfig,
  ContractClient,
  buildScope,
  toUsdc,
  inMinutes,
  UNISWAP_V3,
} from '../src/index';

// Sepolia token addresses (same defaults as Python config)
const USDC = '0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238';
const WETH = '0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14';

async function main(): Promise<void> {
  const deployerKey = process.env.DEPLOYER_PRIVATE_KEY;
  if (!deployerKey) {
    console.error('DEPLOYER_PRIVATE_KEY is required. Add it to .env at the project root.');
    process.exit(1);
  }

  // USER_PRIVATE_KEY defaults to DEPLOYER_PRIVATE_KEY (single-key mode)
  const userKey = process.env.USER_PRIVATE_KEY ?? deployerKey;

  const config = loadConfig();
  const orchestratorAddress = new Wallet(deployerKey).address;
  const userAddress         = new Wallet(userKey).address;

  console.log('='.repeat(55));
  console.log('  Proof-of-Intent Protocol — TypeScript Quickstart');
  console.log('='.repeat(55));
  console.log('  Wallet :', orchestratorAddress);
  console.log('  Chain  : Ethereum Sepolia (11155111)');
  console.log();

  const client     = new ContractClient(deployerKey, config);
  const userClient = new ContractClient(userKey, config);

  // ── Step 1: Register the agent (idempotent) ──────────────────────────────
  console.log('Step 1/5  Register agent');
  const regTx = await client.registerAgent(orchestratorAddress, 'QuickstartAgent');
  console.log(regTx
    ? `          tx: ${regTx}`
    : '          Already registered — skipping.');
  console.log();

  // ── Step 2: Create intent (build + sign + register in one call) ───────────
  console.log('Step 2/5  Create intent');
  const intentId = await userClient.createIntent({
    tokenIn          : USDC,
    maxAmountIn      : toUsdc(100),     // 100 USDC
    minAmountOut     : 1n,              // demo: accept any output
    allowedProtocols : ['Uniswap-V3'],
    deadline         : inMinutes(60),   // valid for 1 hour
    orchestrator     : orchestratorAddress,
  });
  console.log('          intentId:', intentId);
  console.log();

  // ── Step 3: Create root delegation (orchestrator → itself) ────────────────
  console.log('Step 3/5  Create delegation');
  const scope = buildScope({
    maxAmountIn      : toUsdc(100),
    minAmountOut     : 1n,             // demo: accept any output
    allowedProtocols : ['Uniswap-V3'],
    deadline         : inMinutes(55),  // 5 min tighter than intent deadline
  });
  const delegationId = await client.delegateFromRoot(intentId, scope, orchestratorAddress);
  console.log('          delegationId:', delegationId);
  console.log();

  // ── Step 4: Verify the delegation chain (view call — no gas) ─────────────
  console.log('Step 4/5  Verify chain');
  const txParams = {
    amountIn    : toUsdc(100),
    minAmountOut: 1n,                  // demo: accept any output
    protocol    : UNISWAP_V3,
    tokenIn     : USDC,
    tokenOut    : WETH,
    recipient   : userAddress,
  };
  const isValid = await client.verifyChain(delegationId, txParams);
  if (!isValid) {
    console.error('          FAIL — verifyChain returned false');
    process.exit(1);
  }
  console.log('          Chain verified ✓');
  console.log();

  // ── Step 5: Execute swap (requires Sepolia USDC in userAddress) ───────────
  console.log('Step 5/5  Execute swap');
  const balance = await userClient.tokenBalance(USDC, userAddress);
  console.log(`          USDC balance: ${Number(balance) / 1e6} USDC`);

  if (balance < toUsdc(100)) {
    console.log();
    console.log(`  Wallet ${userAddress} needs ≥ 100 Sepolia USDC.`);
    console.log('  Get some at: https://faucet.circle.com');
    console.log();
    console.log('  Steps 1–4 already completed on-chain.');
    console.log('  Re-run after funding to execute the swap.');
    return;
  }

  await userClient.ensureTokenApproval(USDC, config.executionGateAddress, toUsdc(100));
  console.log('          Approval confirmed.');

  const txHash = await client.executeSwap(delegationId, txParams);
  console.log();
  console.log('  ✓ Swap executed!');
  console.log(`  tx: https://sepolia.etherscan.io/tx/${txHash}`);

  const wethAfter = await userClient.tokenBalance(WETH, userAddress);
  console.log(`  WETH balance: ${Number(wethAfter) / 1e18} WETH`);
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
