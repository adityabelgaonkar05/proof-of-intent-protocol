/**
 * Orchestrator Agent — coordinates the pipeline.
 *
 * Scenario 1 (clean):
 *   1. Receives intentId from User Agent via AXL.
 *   2. Creates root delegation (full intent scope) to Research Agent on-chain.
 *   3. Dispatches TASK to Research Agent via AXL.
 *   4. Waits for COMPLETE/FAILED from Execution Agent (which reports directly here).
 *   5. Sends SCENARIO_1_DONE to User Agent.
 *
 * Scenario 2 (attack):
 *   6. Receives second intentId from User Agent.
 *   7. Creates root delegation for attack scenario.
 *   8. Sends ATTACK_TASK to Research Agent.
 *   9. Waits for BLOCKED from Research Agent.
 *  10. Reports result and sends DONE to User Agent.
 */

import 'dotenv/config';
import { Wallet } from 'ethers';
import { ContractClient, fromUsdc } from 'proof-of-intent';
import type { ScopeData } from 'proof-of-intent';
import { sendMessage, waitForType, waitForAny, sleep } from './axlClient';

const PAD = '[ORCHESTRATOR] ';
const log = (msg: string) => console.log(`${PAD}${msg}`);

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing env var: ${name}`);
  return v;
}

// ---------------------------------------------------------------------------
// Message types (inbound)
// ---------------------------------------------------------------------------

interface IntentReadyMsg {
  type: string;
  intentId: string;
  maxAmountIn: string;
  minAmountOut: string;
  allowedProtocols: string[];
  deadline: string;
  userAddress: string;
}

interface CompletionMsg {
  type: 'COMPLETE' | 'FAILED';
  txHash?: string;
  amountOut?: string;
  reason?: string;
}

interface BlockedMsg {
  type: 'BLOCKED';
  reason: string;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const deployerKey = requireEnv('DEPLOYER_KEY');
  const myPort = parseInt(requireEnv('MY_AXL_PORT'), 10);
  const userAXLKey = requireEnv('USER_AXL_KEY');
  const researchAXLKey = requireEnv('RESEARCH_AXL_KEY');
  const researchEthAddress = requireEnv('RESEARCH_ETH_ADDRESS');

  const client = new ContractClient({ privateKey: deployerKey });
  const orchAddress = new Wallet(deployerKey).address;

  log(`Active at ${orchAddress}`);
  log(`Listening for intent from User Agent...`);

  // ── SCENARIO 1: Clean pipeline ─────────────────────────────────────────────

  const msg1 = await waitForType<IntentReadyMsg>('INTENT_READY', myPort, 600_000);
  const { intentId, maxAmountIn, minAmountOut, allowedProtocols, deadline, userAddress } = msg1;

  const maxUsdc = fromUsdc(BigInt(maxAmountIn));
  log(`Intent received: ${shortId(intentId)}`);
  log(`  User authorized ${maxUsdc.toFixed(0)} USDC via ${allowedProtocols.length} protocol(s), deadline in ~2h`);

  // Create root delegation — full scope, delegates to Research Agent
  const rootScope: ScopeData = {
    maxAmountIn: BigInt(maxAmountIn),
    minAmountOut: BigInt(minAmountOut),
    allowedProtocols,
    deadline: BigInt(deadline),
  };

  log(`Creating root delegation → Research Agent...`);
  const delegationId = await client.delegateFromRoot(intentId, rootScope, researchEthAddress);
  log(`Delegation created: ${shortId(delegationId)}`);
  log(`  scope: ≤${maxUsdc.toFixed(0)} USDC  |  ${allowedProtocols.length} protocols allowed`);
  log(`  https://sepolia.etherscan.io/address/${researchEthAddress}`);

  // Dispatch research task
  await sendMessage(
    researchAXLKey,
    {
      type: 'TASK',
      delegationId,
      goal: 'Find the best USDC yield opportunity — Uniswap V3 or Aave V3',
      userAddress,
      deadline,
    },
    myPort,
  );
  log(`→ Research Agent: task dispatched`);

  // Wait for Execution Agent to report result (it contacts us directly)
  log(`Awaiting execution result...`);
  const result = await waitForAny<CompletionMsg>(['COMPLETE', 'FAILED'], myPort, 600_000);

  if (result.type === 'COMPLETE') {
    const txHash = result.txHash ?? '(simulated)';
    const wethOut = result.amountOut ? parseFloat(result.amountOut).toFixed(4) : 'N/A';
    log(`Pipeline complete. User received ~${wethOut} WETH for ${maxUsdc.toFixed(0)} USDC.`);
    if (txHash !== '(simulated)') {
      log(`  tx: ${txHash}`);
      log(`  https://sepolia.etherscan.io/tx/${txHash}`);
    } else {
      log(`  ${txHash}`);
    }
  } else {
    log(`Pipeline ended (execution): ${result.reason ?? 'unknown reason'}`);
  }

  // Notify User Agent scenario 1 is done
  await sendMessage(userAXLKey, { type: 'SCENARIO_1_DONE' }, myPort);

  // ── SCENARIO 2: Attack ─────────────────────────────────────────────────────
  await sleep(2_000);
  log(`--- SCENARIO 2: ATTACK ---`);
  log(`Waiting for second intent from User Agent...`);

  const msg2 = await waitForType<IntentReadyMsg>('INTENT_2_READY', myPort, 600_000);

  const rootScope2: ScopeData = {
    maxAmountIn: BigInt(msg2.maxAmountIn),
    minAmountOut: BigInt(msg2.minAmountOut),
    allowedProtocols: msg2.allowedProtocols,
    deadline: BigInt(msg2.deadline),
  };

  log(`Creating root delegation for attack scenario...`);
  const delegationId2 = await client.delegateFromRoot(
    msg2.intentId,
    rootScope2,
    researchEthAddress,
  );
  log(`Root delegation: ${shortId(delegationId2)}`);
  log(`  root intent authorizes ≤${fromUsdc(BigInt(msg2.maxAmountIn)).toFixed(0)} USDC`);

  // Send attack task — Research Agent will try to exceed the scope
  await sendMessage(
    researchAXLKey,
    {
      type: 'ATTACK_TASK',
      delegationId: delegationId2,
      maxAmountIn: msg2.maxAmountIn,
      userAddress: msg2.userAddress,
    },
    myPort,
  );
  log(`→ Research Agent: compromised instructions delivered`);

  // Wait for Research Agent to report the block
  const blocked = await waitForType<BlockedMsg>('BLOCKED', myPort, 300_000);
  log(`Attack prevented. Zero USDC moved.`);
  log(`  Contract rejected: "${blocked.reason}"`);
  log(`  No AI scored this. No human approved it.`);
  log(`  The math was wrong — 800 > ${fromUsdc(BigInt(msg2.maxAmountIn)).toFixed(0)} — so the contract reverted.`);

  await sendMessage(userAXLKey, { type: 'DONE' }, myPort);
  log(`Both scenarios complete.`);
}

function shortId(hex: string): string {
  return `${hex.slice(0, 10)}...${hex.slice(-6)}`;
}

main().catch((err: unknown) => {
  console.error(`${PAD}Fatal:`, err instanceof Error ? err.message : err);
  process.exit(1);
});
