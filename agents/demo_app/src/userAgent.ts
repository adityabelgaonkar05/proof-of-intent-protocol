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
} from 'proof-of-intent';
import type { IntentData } from 'proof-of-intent';
import { sendMessage, waitForType, sleep } from './axlClient';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const USDC_ADDRESS = '0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238';
const GOAL = 'Find the best USDC yield opportunity and execute it, max 400 USDC, only use Uniswap or Aave, valid for 2 hours.';

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

interface CompiledParams {
  maxUsdc: number;
  deadlineHours: number;
  protocols: string[];
}

async function compileWithClaude(goal: string, apiKey: string): Promise<CompiledParams> {
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 256,
      messages: [
        {
          role: 'user',
          content: `Extract DeFi intent parameters from this goal: "${goal}"

Respond with ONLY valid JSON (no markdown):
{"maxUsdc": <number>, "deadlineHours": <number>, "protocols": [<string>...]}

Protocol names must be exactly from: "Uniswap-V3", "Aave-V3"
Example: {"maxUsdc": 400, "deadlineHours": 2, "protocols": ["Uniswap-V3", "Aave-V3"]}`,
        },
      ],
    }),
  });
  if (!res.ok) throw new Error(`Claude API ${res.status}`);
  const data = (await res.json()) as { content: Array<{ type: string; text: string }> };
  return JSON.parse(data.content[0]?.text ?? '{}') as CompiledParams;
}

async function buildAndRegisterIntent(
  client: ContractClient,
  userAddress: string,
  orchestratorAddress: string,
  params: CompiledParams,
): Promise<{ intentId: string; intent: IntentData }> {
  const config = loadConfig();
  const nonce = (await client.intentRegistry.nonces(userAddress)) as bigint;

  const intent = buildIntent({
    owner: userAddress,
    authorizedOrchestrator: orchestratorAddress,
    tokenIn: USDC_ADDRESS,
    maxAmountIn: usdc(params.maxUsdc),
    minAmountOut: 1n, // research agent refines this from live market data
    allowedProtocols: params.protocols,
    deadline: inHours(params.deadlineHours),
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
  let params: CompiledParams;
  const claudeKey = process.env['CLAUDE_API_KEY'];

  if (claudeKey) {
    log(`Compiling intent with Claude AI...`);
    try {
      params = await compileWithClaude(GOAL, claudeKey);
      log(`Claude extracted: ${params.maxUsdc} USDC | ${params.protocols.join(', ')} | ${params.deadlineHours}h`);
    } catch {
      log(`Claude unavailable — using defaults`);
      params = { maxUsdc: 400, deadlineHours: 2, protocols: ['Uniswap-V3', 'Aave-V3'] };
    }
  } else {
    params = { maxUsdc: 400, deadlineHours: 2, protocols: ['Uniswap-V3', 'Aave-V3'] };
    log(`Goal: "${GOAL}"`);
    log(`Parsed: max ${params.maxUsdc} USDC | ${params.protocols.join(', ')} | ${params.deadlineHours}h deadline`);
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
  log(`  max:      ${params.maxUsdc} USDC  |  protocols: ${params.protocols.join(', ')}`);
  log(`  deadline: ${params.deadlineHours}h from now`);
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
