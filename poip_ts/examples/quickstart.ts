/**
 * Proof-of-Intent Protocol — TypeScript quickstart.
 *
 * Minimum env requirements:
 *   PRIVATE_KEY=0x...          your wallet private key (Sepolia testnet)
 *
 * USER_PRIVATE_KEY is optional — defaults to PRIVATE_KEY when not set.
 * All contract addresses default to the deployed Sepolia contracts.
 *
 * Run from the poip_ts directory:
 *   npx tsx examples/quickstart.ts
 */

import * as dotenv from 'dotenv';
import * as path from 'path';

// Load .env from the package root (poip_ts/.env).
dotenv.config({ path: path.resolve(__dirname, '../.env') });

import { Wallet } from 'ethers';
import {
  ContractClient,
  buildScope,
  usdc,
  inMinutes,
  UNISWAP_V3,
} from '../src/index';

const USDC_ADDR = '0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238';
const WETH_ADDR = '0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14';

async function main(): Promise<void> {
  const privateKey = process.env.PRIVATE_KEY ?? process.env.DEPLOYER_PRIVATE_KEY;
  if (!privateKey) {
    console.error('PRIVATE_KEY is required. Add it to .env. See .env.sdk.example.');
    process.exit(1);
  }

  const userKey             = process.env.USER_PRIVATE_KEY ?? privateKey;
  const orchestratorAddress = new Wallet(privateKey).address;
  const userAddress         = new Wallet(userKey).address;

  console.log('='.repeat(55));
  console.log('  Proof-of-Intent Protocol — TypeScript Quickstart');
  console.log('='.repeat(55));
  console.log('  Wallet :', orchestratorAddress);
  console.log('  Chain  : Ethereum Sepolia (11155111)');
  console.log();

  const client     = new ContractClient({ privateKey });
  const userClient = new ContractClient({ privateKey: userKey });

  console.log('Step 1/5  Register agent');
  const regTx = await client.registerAgent(orchestratorAddress, 'QuickstartAgent');
  console.log(regTx ? `          tx: ${regTx}` : '          Already registered — skipping.');
  console.log();

  console.log('Step 2/5  Create intent');
  const intentId = await userClient.createIntent({
    tokenIn:          USDC_ADDR,
    maxAmountIn:      usdc(100),
    minAmountOut:     1n,
    allowedProtocols: ['Uniswap-V3'],
    deadline:         inMinutes(60),
    orchestrator:     orchestratorAddress,
  });
  console.log('          intentId:', intentId);
  console.log();

  console.log('Step 3/5  Create delegation');
  const scope = buildScope({
    maxAmountIn:      usdc(100),
    minAmountOut:     1n,
    allowedProtocols: ['Uniswap-V3'],
    deadline:         inMinutes(55),
  });
  const delegationId = await client.delegateFromRoot(intentId, scope, orchestratorAddress);
  console.log('          delegationId:', delegationId);
  console.log();

  console.log('Step 4/5  Verify chain');
  const txParams = {
    amountIn:     usdc(100),
    minAmountOut: 1n,
    protocol:     UNISWAP_V3,
    tokenIn:      USDC_ADDR,
    tokenOut:     WETH_ADDR,
    recipient:    userAddress,
  };
  const isValid = await client.verifyChain(delegationId, txParams);
  if (!isValid) { console.error('FAIL — verifyChain returned false'); process.exit(1); }
  console.log('          Chain verified ✓');
  console.log();

  console.log('Step 5/5  Execute swap');
  const balance = await userClient.tokenBalance(USDC_ADDR, userAddress);
  console.log(`          USDC balance: ${Number(balance) / 1e6} USDC`);

  if (balance < usdc(100)) {
    console.log();
    console.log(`  Wallet ${userAddress} needs ≥ 100 Sepolia USDC.`);
    console.log('  Get some at: https://faucet.circle.com');
    console.log('  Steps 1–4 already completed on-chain. Re-run after funding.');
    return;
  }

  const execGate = client.config.executionGateAddress;
  await userClient.ensureTokenApproval(USDC_ADDR, execGate, usdc(100));
  console.log('          Approval confirmed.');

  const txHash = await client.executeSwap(delegationId, txParams);
  console.log(`  Swap executed! tx: https://sepolia.etherscan.io/tx/${txHash}`);
  const wethAfter = await userClient.tokenBalance(WETH_ADDR, userAddress);
  console.log(`  WETH balance: ${Number(wethAfter) / 1e18} WETH`);
}

main().catch((err: unknown) => { console.error(err); process.exit(1); });
