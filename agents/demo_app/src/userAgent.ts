/**
 * User Agent — represents the human.
 *
 * Scenario 1: compiles the natural language goal (optionally via Claude),
 *   signs an EIP-712 intent, registers it on Sepolia, then kicks off the
 *   pipeline by sending the intentId to the Orchestrator over AXL.
 *
 * Scenario 2: after the clean pipeline completes, registers a fresh intent
 *   for the attack scenario and forwards it to the Orchestrator.
 */

import 'dotenv/config';
import { Wallet } from 'ethers';
import {
  ContractClient,
  buildIntent,
  signIntent,
  loadConfig,
  usdc,
  inHours,
  compileIntent,
} from 'proof-of-intent';
import type { IntentData } from 'proof-of-intent';
import { sendMessage, waitForType, sleep } from './axlClient';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const USDC_ADDRESS = '0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238';
const GOAL = 'Find the best USDC yield opportunity and execute it, max 40 USDC, only use Uniswap or Aave, valid for 2 hours.';

const PAD = '[USER]         ';
const log = (msg: string) => console.log(`${PAD}${msg}`);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing env var: ${name}`);
  return v;
}


const HARDCODED_PARAMS = {
  maxAmountIn: usdc(40),
  minAmountOut: 1n,
  allowedProtocols: ['Uniswap-V3', 'Aave-V3'],
  deadline: inHours(2),
};

async function buildAndRegisterIntent(
  client: ContractClient,
  userAddress: string,
  orchestratorAddress: string,
  params: { maxAmountIn: bigint; minAmountOut: bigint; allowedProtocols: string[]; deadline: number | bigint },
): Promise<{ intentId: string; intent: IntentData }> {
  const config = loadConfig();
  const nonce = (await client.intentRegistry.nonces(userAddress)) as bigint;

  const intent = buildIntent({
    owner: userAddress,
    authorizedOrchestrator: orchestratorAddress,
    tokenIn: USDC_ADDRESS,
    maxAmountIn: params.maxAmountIn,
    minAmountOut: params.minAmountOut,
    allowedProtocols: params.allowedProtocols,
    deadline: BigInt(params.deadline),
    nonce,
  });

  const sig = await signIntent(intent, requireEnv('PRIVATE_KEY'), config);
  const intentId = await client.registerIntent(intent, sig);
  return { intentId, intent };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const userKey = requireEnv('PRIVATE_KEY');
  const orchestratorEthAddress = requireEnv('ORCHESTRATOR_ETH_ADDRESS');
  const orchestratorAXLKey = requireEnv('ORCHESTRATOR_AXL_KEY');
  const myPort = parseInt(requireEnv('MY_AXL_PORT'), 10);

  const userAddress = new Wallet(userKey).address;
  const client = new ContractClient({ privateKey: userKey });

  // ── Intent compilation ──────────────────────────────────────────────────────
  const hasLLMKey = Boolean(process.env['CLAUDE_API_KEY'] ?? process.env['OPENAI_API_KEY']);
  let params: typeof HARDCODED_PARAMS;

  if (hasLLMKey) {
    const provider = process.env['CLAUDE_API_KEY'] ? 'Claude' : 'OpenAI';
    log(`Compiling intent with ${provider} AI...`);
    try {
      const compiled = await compileIntent(GOAL);
      params = {
        maxAmountIn: compiled.maxAmountIn,
        minAmountOut: compiled.minAmountOut,
        allowedProtocols: compiled.allowedProtocols,
        deadline: compiled.deadline,
      };
      log(`${provider} compiled: ${compiled.allowedProtocols.join(', ')} | deadline ${new Date(compiled.deadline * 1000).toISOString()}`);
    } catch {
      log(`LLM unavailable — using hardcoded defaults`);
      params = HARDCODED_PARAMS;
    }
  } else {
    params = HARDCODED_PARAMS;
    log(`Goal: "${GOAL}"`);
    log(`No LLM key set — using hardcoded intent (max 40 USDC | Uniswap-V3, Aave-V3 | 2h)`);
  }

  // ── SCENARIO 1: Register intent and kick off pipeline ──────────────────────
  log(`Signing EIP-712 intent...`);
  const { intentId, intent } = await buildAndRegisterIntent(
    client,
    userAddress,
    orchestratorEthAddress,
    params,
  );

  log(`Intent registered on Sepolia.`);
  log(`  intentId: ${intentId}`);
  log(`  owner:    ${userAddress}`);
  log(`  max:      ${params.maxAmountIn} raw  |  protocols: ${params.allowedProtocols.join(', ')}`);
  log(`  deadline: ${new Date(Number(params.deadline) * 1000).toISOString()}`);
  log(`  https://sepolia.etherscan.io/address/${orchestratorEthAddress}`);

  // Relay intent metadata to orchestrator (avoids a chain read on their side)
  await sendMessage(
    orchestratorAXLKey,
    {
      type: 'INTENT_READY',
      intentId,
      maxAmountIn: intent.maxAmountIn.toString(),
      minAmountOut: intent.minAmountOut.toString(),
      allowedProtocols: intent.allowedProtocols,
      deadline: intent.deadline.toString(),
      userAddress,
    },
    myPort,
  );
  log(`→ Pipeline started. Waiting for Orchestrator...`);

  // ── Wait for scenario 1 to complete ──────────────────────────────────────
  await waitForType<{ type: string }>('SCENARIO_1_DONE', myPort, 600_000);

  // ── SCENARIO 2: Register a fresh intent for the attack demo ───────────────
  await sleep(5_000);

  log(`Registering intent for attack scenario...`);
  const { intentId: intentId2, intent: intent2 } = await buildAndRegisterIntent(
    client,
    userAddress,
    orchestratorEthAddress,
    params,
  );
  log(`  intentId: ${intentId2}`);

  await sendMessage(
    orchestratorAXLKey,
    {
      type: 'INTENT_2_READY',
      intentId: intentId2,
      maxAmountIn: intent2.maxAmountIn.toString(),
      minAmountOut: intent2.minAmountOut.toString(),
      allowedProtocols: intent2.allowedProtocols,
      deadline: intent2.deadline.toString(),
      userAddress,
    },
    myPort,
  );

  // Wait for the attack scenario to finish
  await waitForType<{ type: string }>('DONE', myPort, 600_000);
}

main().catch((err: unknown) => {
  console.error(`${PAD}Fatal:`, err instanceof Error ? err.message : err);
  process.exit(1);
});
