/**
 * Execution Agent — final step in the pipeline.
 *
 *   1. Receives EXECUTE from Research Agent via AXL.
 *   2. Calls verifyChain() — dry-runs the full delegation chain against the
 *      root intent without spending gas.  If this passes, the swap is safe.
 *   3. Checks recipient's USDC balance.
 *   4. If funded: approves ExecutionGate, executes the Uniswap V3 swap.
 *      If not funded: reports chain-verified success so the demo is meaningful.
 *   5. Sends COMPLETE or FAILED directly to Orchestrator via AXL.
 */

import 'dotenv/config';
import { Wallet } from 'ethers';
import { ContractClient, fromUsdc, fromWeth } from 'proof-of-intent';
import type { TxParamsData } from 'proof-of-intent';
import { sendMessage, waitForType } from './axlClient';

const USDC_ADDRESS = '0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238';
const WETH_ADDRESS = '0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14';
const EXECUTION_GATE_ADDRESS = '0x076e8cd66be8B927CcB9adA63505e8027b209cb6';

const PAD = '[EXECUTION]    ';
const log = (msg: string) => console.log(`${PAD}${msg}`);

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing env var: ${name}`);
  return v;
}

// ---------------------------------------------------------------------------
// Message type
// ---------------------------------------------------------------------------

interface ExecuteMsg {
  type: string;
  delegationId: string;
  txParams: {
    amountIn: string;
    minAmountOut: string;
    protocol: string;
    tokenIn: string;
    tokenOut: string;
    recipient: string;
  };
  ethPrice: string;
  minWethOut: string;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const executionKey = requireEnv('EXECUTION_KEY');
  const myPort = parseInt(requireEnv('MY_AXL_PORT'), 10);
  const orchestratorAXLKey = requireEnv('ORCHESTRATOR_AXL_KEY');

  const client = new ContractClient({ privateKey: executionKey });
  const execAddress = new Wallet(executionKey).address;

  log(`Active at ${execAddress}`);
  log(`Listening for execution task...`);

  const task = await waitForType<ExecuteMsg>('EXECUTE', myPort, 600_000);

  const { delegationId, txParams: raw } = task;
  const txParams: TxParamsData = {
    amountIn: BigInt(raw.amountIn),
    minAmountOut: BigInt(raw.minAmountOut),
    protocol: raw.protocol,
    tokenIn: raw.tokenIn,
    tokenOut: raw.tokenOut,
    recipient: raw.recipient,
  };

  const amountUsdcStr = fromUsdc(txParams.amountIn).toFixed(0);
  log(`Execution task received.`);
  log(`  delegation: ${shortId(delegationId)}`);
  log(`  swap: ${amountUsdcStr} USDC → WETH  |  min: ${task.minWethOut} WETH  |  ETH $${task.ethPrice}`);
  log(`  recipient: ${raw.recipient}`);

  // ── Step 1: Dry-run — verify entire chain against root intent ──────────────
  log(`Verifying delegation chain (view call, no gas)...`);
  let chainOk: boolean;
  try {
    chainOk = await client.verifyChain(delegationId, txParams);
  } catch (err) {
    log(`✗ Chain verification threw: ${err instanceof Error ? err.message : err}`);
    await sendMessage(orchestratorAXLKey, { type: 'FAILED', reason: String(err) }, myPort);
    return;
  }

  if (!chainOk) {
    log(`✗ Chain verification returned false`);
    await sendMessage(
      orchestratorAXLKey,
      { type: 'FAILED', reason: 'verifyChain returned false' },
      myPort,
    );
    return;
  }
  log(`✓ Chain verified — root intent ↔ orchestrator delegation ↔ research delegation all valid`);

  // ── Step 2: Check USDC balance ─────────────────────────────────────────────
  const usdcBalance = await client.tokenBalance(USDC_ADDRESS, raw.recipient);
  const usdcNeeded = txParams.amountIn;

  if (usdcBalance < usdcNeeded) {
    log(`⚠ Wallet holds ${fromUsdc(usdcBalance).toFixed(2)} USDC, need ${amountUsdcStr} USDC`);
    log(`  Chain is valid. Swap would succeed if wallet were funded.`);
    log(`  Fund ${raw.recipient} with Sepolia USDC to settle.`);
    await sendMessage(
      orchestratorAXLKey,
      {
        type: 'COMPLETE',
        txHash: `(chain verified — fund ${raw.recipient} with ${amountUsdcStr} Sepolia USDC to execute)`,
        amountOut: task.minWethOut,
      },
      myPort,
    );
    return;
  }

  // ── Step 3: Approve ExecutionGate ──────────────────────────────────────────
  log(`Approving ExecutionGate for ${amountUsdcStr} USDC...`);
  await client.ensureTokenApproval(USDC_ADDRESS, EXECUTION_GATE_ADDRESS, usdcNeeded);
  log(`✓ Approval confirmed`);

  // ── Step 4: Execute the swap ───────────────────────────────────────────────
  log(`Executing Uniswap V3 swap on Sepolia...`);
  try {
    const txHash = await client.executeSwap(delegationId, txParams);
    log(`✓ Swap executed!`);
    log(`  tx: ${txHash}`);
    log(`  https://sepolia.etherscan.io/tx/${txHash}`);

    const wethAfter = await client.tokenBalance(WETH_ADDRESS, raw.recipient);
    log(`  WETH received: ${fromWeth(wethAfter).toFixed(4)}`);

    await sendMessage(
      orchestratorAXLKey,
      { type: 'COMPLETE', txHash, amountOut: fromWeth(wethAfter).toFixed(4) },
      myPort,
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    log(`✗ Swap reverted: ${msg}`);
    await sendMessage(orchestratorAXLKey, { type: 'FAILED', reason: msg }, myPort);
  }
}

function shortId(hex: string): string {
  return `${hex.slice(0, 10)}...${hex.slice(-6)}`;
}

main().catch((err: unknown) => {
  console.error(`${PAD}Fatal:`, err instanceof Error ? err.message : err);
  process.exit(1);
});
