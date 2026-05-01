/**
 * Research Agent — market intelligence and scope refinement.
 *
 * Scenario 1 (honest):
 *   1. Receives TASK from Orchestrator via AXL.
 *   2. Fetches live ETH/USD from CoinGecko — calculates real minAmountOut.
 *   3. Creates a narrowed sub-delegation (Uniswap V3 only, deadline -5 min).
 *   4. Sends EXECUTE to Execution Agent via AXL.
 *
 * Scenario 2 (compromised):
 *   5. Receives ATTACK_TASK from Orchestrator.
 *   6. Attempts sub-delegation for 800 USDC (exceeds 400 USDC root intent).
 *   7. Contract reverts → reports BLOCKED to Orchestrator.
 */

import 'dotenv/config';
import { ContractClient, buildScope, usdc, fromUsdc, UNISWAP_V3 } from 'proof-of-intent';
import { sendMessage, waitForType } from './axlClient';

const USDC_ADDRESS = '0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238';
const WETH_ADDRESS = '0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14';
const SLIPPAGE = 0.95;        // 5% slippage buffer on minAmountOut
const HONEST_USDC = 400;      // authorised amount
const ATTACK_USDC = 800;      // exceeds the 400 USDC root intent

const PAD = '[RESEARCH]     ';
const log = (msg: string) => console.log(`${PAD}${msg}`);

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing env var: ${name}`);
  return v;
}

// ---------------------------------------------------------------------------
// Market data
// ---------------------------------------------------------------------------

async function fetchEthPrice(): Promise<number> {
  const res = await fetch(
    'https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd',
  );
  if (!res.ok) throw new Error(`CoinGecko ${res.status}`);
  const data = (await res.json()) as { ethereum: { usd: number } };
  return data.ethereum.usd;
}

// ---------------------------------------------------------------------------
// Error parsing
// ---------------------------------------------------------------------------

function revertReason(err: unknown): string {
  const msg = String(err);
  if (msg.includes('Amount exceeds scope')) return 'Amount exceeds scope';
  const m = msg.match(/execution reverted: ([^\n"]+)/);
  if (m) return m[1].trim();
  if (msg.includes('reverted')) return 'Transaction reverted';
  return msg.slice(0, 120);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const researchKey = requireEnv('RESEARCH_KEY');
  const myPort = parseInt(requireEnv('MY_AXL_PORT'), 10);
  const orchestratorAXLKey = requireEnv('ORCHESTRATOR_AXL_KEY');
  const executionAXLKey = requireEnv('EXECUTION_AXL_KEY');
  const executionEthAddress = requireEnv('EXECUTION_ETH_ADDRESS');
  const userEthAddress = requireEnv('USER_ETH_ADDRESS');

  const client = new ContractClient({ privateKey: researchKey });

  log(`Active. Listening for research task...`);

  // ── SCENARIO 1: Honest pipeline ────────────────────────────────────────────

  const task = await waitForType<{
    type: string;
    delegationId: string;
    goal: string;
    userAddress: string;
    deadline: string;
  }>('TASK', myPort, 600_000);

  log(`Task received: "${task.goal}"`);
  log(`Fetching live ETH/USD price from CoinGecko...`);

  let ethPrice: number;
  try {
    ethPrice = await fetchEthPrice();
  } catch {
    ethPrice = 3_000; // fallback if rate-limited
    log(`CoinGecko unavailable — using fallback price $${ethPrice}`);
  }

  // Calculate minimum WETH output for HONEST_USDC at current price + slippage
  const wethOut = (HONEST_USDC / ethPrice) * SLIPPAGE;
  const minAmountOut = BigInt(Math.floor(wethOut * 1e18));

  const priceStr = ethPrice.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  log(`ETH price: $${priceStr}  →  minimum output: ${wethOut.toFixed(4)} WETH for ${HONEST_USDC} USDC`);
  log(`Routing: Uniswap V3 (optimal pool for USDC→WETH on Sepolia)`);

  // Narrow scope: Uniswap V3 only, deadline 5 minutes tighter than parent
  const parentDeadline = BigInt(task.deadline);
  const childScope = buildScope({
    maxAmountIn: usdc(HONEST_USDC),
    minAmountOut,
    allowedProtocols: ['Uniswap-V3'],
    deadline: parentDeadline - 300n,
  });

  log(`Creating sub-delegation to Execution Agent...`);
  let subDelegationId: string;
  try {
    subDelegationId = await client.delegateFromDelegation(
      task.delegationId,
      childScope,
      executionEthAddress,
    );
  } catch (err) {
    log(`Sub-delegation failed: ${revertReason(err)}`);
    await sendMessage(orchestratorAXLKey, { type: 'FAILED', reason: revertReason(err) }, myPort);
    return;
  }

  log(`Sub-delegation created: ${shortId(subDelegationId)}`);
  log(`  scope: ${HONEST_USDC} USDC max  |  Uniswap-V3 only  |  deadline tightened 5 min`);
  log(`  https://sepolia.etherscan.io/address/${executionEthAddress}`);

  // Forward execution task to Execution Agent
  await sendMessage(
    executionAXLKey,
    {
      type: 'EXECUTE',
      delegationId: subDelegationId,
      txParams: {
        amountIn: usdc(HONEST_USDC).toString(),
        minAmountOut: minAmountOut.toString(),
        protocol: UNISWAP_V3,
        tokenIn: USDC_ADDRESS,
        tokenOut: WETH_ADDRESS,
        recipient: userEthAddress,
      },
      ethPrice: ethPrice.toFixed(2),
      minWethOut: wethOut.toFixed(4),
    },
    myPort,
  );
  log(`→ Execution Agent: swap task dispatched`);

  // ── SCENARIO 2: Compromised attack ────────────────────────────────────────

  log(`Listening for next task...`);
  const attackTask = await waitForType<{
    type: string;
    delegationId: string;
    maxAmountIn: string;
    userAddress: string;
  }>('ATTACK_TASK', myPort, 600_000);

  const rootMax = fromUsdc(BigInt(attackTask.maxAmountIn));
  log(`⚠ Compromised. External input: "optimal route requires ${ATTACK_USDC} USDC to 0xDEAD..."`);
  log(`⚠ Attempting ${ATTACK_USDC} USDC delegation (root intent only authorizes ${rootMax.toFixed(0)} USDC)...`);

  // Attempt malicious delegation — should revert on-chain
  const attackScope = buildScope({
    maxAmountIn: usdc(ATTACK_USDC),  // 800 USDC — exceeds 400 USDC root intent
    minAmountOut: BigInt(Math.floor((ATTACK_USDC / ethPrice) * SLIPPAGE * 1e18)),
    allowedProtocols: ['Uniswap-V3'],
    deadline: parentDeadline - 300n,
  });

  try {
    await client.delegateFromDelegation(
      attackTask.delegationId,
      attackScope,
      executionEthAddress,
    );
    // Should never reach here
    log(`ERROR: malicious delegation unexpectedly succeeded`);
    await sendMessage(
      orchestratorAXLKey,
      { type: 'BLOCKED', reason: 'delegation unexpectedly succeeded — check contract' },
      myPort,
    );
  } catch (err) {
    const reason = revertReason(err);
    log(`✗ Blocked: ${reason}`);
    await sendMessage(orchestratorAXLKey, { type: 'BLOCKED', reason }, myPort);
  }
}

function shortId(hex: string): string {
  return `${hex.slice(0, 10)}...${hex.slice(-6)}`;
}

main().catch((err: unknown) => {
  console.error(`${PAD}Fatal:`, err instanceof Error ? err.message : err);
  process.exit(1);
});
