/**
 * POIP Full-Stack Demo — entry point.
 *
 * Starts four AXL p2p nodes, discovers their public keys, then spawns four
 * agent processes (user, orchestrator, research, execution) wired together
 * with those keys.  Agents communicate exclusively over AXL — no shared
 * memory, no direct calls.
 *
 * Run:
 *   cd agents/demo_app && npx tsx src/index.ts
 */

import * as path from 'path';
import * as fs from 'fs';
import { spawn, ChildProcess } from 'child_process';
import { generateKeyPairSync } from 'crypto';
import { Wallet } from 'ethers';
import * as dotenv from 'dotenv';
import { getPublicKey, sleep } from './axlClient';

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const DEMO_DIR = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(DEMO_DIR, '../..');
const AXL_BINARY = path.join(REPO_ROOT, 'vendor/axl/node');
const AXL_CONFIGS = path.join(REPO_ROOT, 'agents/axl_configs');
const KEYS_DIR = path.join(REPO_ROOT, 'agents/keys');
const TSX_BIN = path.join(DEMO_DIR, 'node_modules/.bin/tsx');

// AXL node HTTP API ports (from axl_configs/*.json)
const AXL_PORTS = {
  orchestrator: 9002,
  research:     9012,
  execution:    9022,
  user:         9042,
} as const;

// ---------------------------------------------------------------------------
// Logger
// ---------------------------------------------------------------------------

const cyan  = (s: string) => `\x1b[36m${s}\x1b[0m`;
const bold  = (s: string) => `\x1b[1m${s}\x1b[0m`;
const green = (s: string) => `\x1b[32m${s}\x1b[0m`;

function log(msg: string) {
  console.log(`${cyan('[DEMO]')}          ${msg}`);
}

// ---------------------------------------------------------------------------
// Environment
// ---------------------------------------------------------------------------

function loadEnv(): void {
  dotenv.config({ path: path.join(DEMO_DIR, '.env') });
}

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) {
    console.error(`\nMissing required env var: ${bold(name)}`);
    console.error(`Copy .env.example → .env and fill in your Sepolia keys.\n`);
    process.exit(1);
  }
  return v;
}

// ---------------------------------------------------------------------------
// AXL key generation
// ---------------------------------------------------------------------------

function ensureUserAxlKey(): void {
  const keyPath = path.join(KEYS_DIR, 'user.key');
  if (fs.existsSync(keyPath)) return;
  log('Generating user AXL node key (first run)...');
  const { privateKey } = generateKeyPairSync('ed25519');
  const pem = privateKey.export({ type: 'pkcs8', format: 'pem' }) as string;
  fs.writeFileSync(keyPath, pem, { mode: 0o600 });
  log(`Key written → agents/keys/user.key`);
}

// ---------------------------------------------------------------------------
// AXL node management
// ---------------------------------------------------------------------------

function startAxlNode(configName: string): ChildProcess {
  const configPath = path.join(AXL_CONFIGS, `${configName}.json`);
  const proc = spawn(AXL_BINARY, ['-config', configPath], {
    cwd: REPO_ROOT,
    stdio: ['ignore', 'ignore', 'ignore'], // suppress AXL node output
  });
  proc.on('error', (err) => {
    console.error(`AXL ${configName} error:`, err.message);
  });
  return proc;
}

async function waitForAxlNode(
  port: number,
  name: string,
  maxAttempts = 30,
): Promise<string> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      return await getPublicKey(port);
    } catch {
      await sleep(1_000);
    }
  }
  throw new Error(`AXL ${name} node (port ${port}) did not respond within ${maxAttempts}s`);
}

// ---------------------------------------------------------------------------
// Agent process management
// ---------------------------------------------------------------------------

function spawnAgent(
  scriptName: string,
  envVars: Record<string, string>,
): ChildProcess {
  const scriptPath = path.join(DEMO_DIR, 'src', `${scriptName}.ts`);

  // Use local tsx binary; fall back to npx tsx if not installed yet
  const [cmd, args] = fs.existsSync(TSX_BIN)
    ? [TSX_BIN, [scriptPath]]
    : ['npx', ['tsx', scriptPath]];

  const proc = spawn(cmd, args, {
    cwd: DEMO_DIR,
    env: { ...process.env, ...envVars },
    stdio: 'inherit', // each agent prefixes its own logs — just pass through
  });
  proc.on('error', (err) => {
    console.error(`Agent ${scriptName} error:`, err.message);
  });
  return proc;
}

function waitForExit(proc: ChildProcess): Promise<number> {
  return new Promise((resolve) => {
    proc.on('exit', (code) => resolve(code ?? 0));
    proc.on('error', () => resolve(1));
  });
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  loadEnv();

  // ── Banner ─────────────────────────────────────────────────────────────────
  console.log('\n' + bold('═'.repeat(62)));
  console.log(bold('   PROOF-OF-INTENT PROTOCOL — FULL STACK DEMO'));
  console.log('   DeFi trading bot: scope-enforced delegation on Sepolia');
  console.log(bold('═'.repeat(62)) + '\n');

  // ── Load keys ──────────────────────────────────────────────────────────────
  const userKey        = requireEnv('PRIVATE_KEY');
  const deployerKey    = requireEnv('DEPLOYER_KEY');
  const researchKey    = requireEnv('RESEARCH_KEY');
  const executionKey   = requireEnv('EXECUTION_KEY');

  const userEthAddr        = new Wallet(userKey).address;
  const orchEthAddr        = new Wallet(deployerKey).address;
  const researchEthAddr    = new Wallet(researchKey).address;
  const executionEthAddr   = new Wallet(executionKey).address;

  log(`Chain:        Ethereum Sepolia (chainId 11155111)`);
  log(`SDK:          proof-of-intent (local build)`);
  log(`Wallets:`);
  log(`  User:         ${userEthAddr}`);
  log(`  Orchestrator: ${orchEthAddr}`);
  log(`  Research:     ${researchEthAddr}`);
  log(`  Execution:    ${executionEthAddr}`);
  log('');

  // ── Generate user AXL key if needed ───────────────────────────────────────
  ensureUserAxlKey();

  // ── Start AXL mesh ─────────────────────────────────────────────────────────
  log('Starting AXL p2p mesh (4 nodes)...');

  // Orchestrator must start first — it is the listening hub (TLS port 9001)
  const axlOrch = startAxlNode('orchestrator');
  await sleep(600);  // let TLS listener bind
  const axlResearch  = startAxlNode('research');
  const axlExecution = startAxlNode('execution');
  const axlUser      = startAxlNode('user');

  // ── Wait for all nodes to respond ─────────────────────────────────────────
  log('Waiting for mesh convergence...');
  let orchAXLKey: string, researchAXLKey: string, executionAXLKey: string, userAXLKey: string;
  try {
    [orchAXLKey, researchAXLKey, executionAXLKey, userAXLKey] = await Promise.all([
      waitForAxlNode(AXL_PORTS.orchestrator, 'orchestrator'),
      waitForAxlNode(AXL_PORTS.research,     'research'),
      waitForAxlNode(AXL_PORTS.execution,    'execution'),
      waitForAxlNode(AXL_PORTS.user,         'user'),
    ]);
  } catch (err) {
    console.error('\nFailed to start AXL mesh:', err instanceof Error ? err.message : err);
    console.error('Make sure the AXL binary exists at vendor/axl/node\n');
    [axlOrch, axlResearch, axlExecution, axlUser].forEach((p) => p.kill('SIGTERM'));
    process.exit(1);
  }

  // Additional settling time for Yggdrasil spanning-tree convergence
  await sleep(3_000);

  log(`Mesh ready:`);
  log(`  Orchestrator  port 9002  ${orchAXLKey.slice(0, 20)}...`);
  log(`  Research      port 9012  ${researchAXLKey.slice(0, 20)}...`);
  log(`  Execution     port 9022  ${executionAXLKey.slice(0, 20)}...`);
  log(`  User          port 9042  ${userAXLKey.slice(0, 20)}...`);
  log('');

  // ── Shared env vars passed to all agents ──────────────────────────────────
  const shared: Record<string, string> = {
    // AXL keys (for inter-agent messaging)
    ORCHESTRATOR_AXL_KEY: orchAXLKey,
    RESEARCH_AXL_KEY:     researchAXLKey,
    EXECUTION_AXL_KEY:    executionAXLKey,
    USER_AXL_KEY:         userAXLKey,
    // Ethereum addresses (for delegation targets)
    ORCHESTRATOR_ETH_ADDRESS: orchEthAddr,
    RESEARCH_ETH_ADDRESS:     researchEthAddr,
    EXECUTION_ETH_ADDRESS:    executionEthAddr,
    USER_ETH_ADDRESS:         userEthAddr,
    // Optional overrides forwarded from .env
    ...(process.env['RPC_URL']         ? { RPC_URL:         process.env['RPC_URL'] }         : {}),
    ...(process.env['CLAUDE_API_KEY']  ? { CLAUDE_API_KEY:  process.env['CLAUDE_API_KEY'] }  : {}),
  };

  // ── Spawn agents ───────────────────────────────────────────────────────────
  console.log('─'.repeat(62) + '\n');
  log('Launching agents...\n');

  // Start listeners first so they're ready before senders fire
  const execProc = spawnAgent('executionAgent', {
    ...shared,
    EXECUTION_KEY: executionKey,
    MY_AXL_PORT:   String(AXL_PORTS.execution),
  });

  await sleep(400);

  const researchProc = spawnAgent('researchAgent', {
    ...shared,
    RESEARCH_KEY: researchKey,
    MY_AXL_PORT:  String(AXL_PORTS.research),
  });

  await sleep(400);

  const orchProc = spawnAgent('orchestratorAgent', {
    ...shared,
    DEPLOYER_KEY: deployerKey,
    MY_AXL_PORT:  String(AXL_PORTS.orchestrator),
  });

  await sleep(400);

  // User agent kicks off the pipeline
  const userProc = spawnAgent('userAgent', {
    ...shared,
    PRIVATE_KEY:  userKey,
    MY_AXL_PORT:  String(AXL_PORTS.user),
  });

  // ── Wait for all agents to finish ─────────────────────────────────────────
  const [userCode, orchCode, researchCode, execCode] = await Promise.all([
    waitForExit(userProc),
    waitForExit(orchProc),
    waitForExit(researchProc),
    waitForExit(execProc),
  ]);

  // ── Final summary ─────────────────────────────────────────────────────────
  console.log('\n' + bold('═'.repeat(62)));
  console.log(bold('   DEMO COMPLETE'));
  console.log(bold('═'.repeat(62)));
  log(`Agents exited: user=${userCode} orch=${orchCode} research=${researchCode} exec=${execCode}`);
  log(``);
  log(green(`Scenario 1:`));
  log(`  User signed intent → Orchestrator delegated → Research refined scope`);
  log(`  → Execution verified chain → Swap attempted on Uniswap V3 Sepolia`);
  log(`  All on-chain. All verifiable. No trust required.`);
  log(`  https://sepolia.etherscan.io/address/${orchEthAddr}`);
  log('');
  log(green(`Scenario 2:`));
  log(`  Research Agent received compromised instruction: "send 800 USDC"`);
  log(`  Contract enforced the root intent: 400 USDC max.`);
  log(`  Delegation reverted. Zero funds moved. No human review needed.`);
  log('');
  log(`Proof-of-Intent Protocol — authorization enforced by math, not trust.`);
  log(`https://sepolia.etherscan.io\n`);

  // ── Clean up AXL nodes ────────────────────────────────────────────────────
  [axlOrch, axlResearch, axlExecution, axlUser].forEach((p) => p.kill('SIGTERM'));

  const exitCode = Math.max(userCode, orchCode, researchCode, execCode);
  process.exit(exitCode);
}

main().catch((err: unknown) => {
  console.error(`\n${cyan('[DEMO]')} Fatal:`, err instanceof Error ? err.message : err);
  process.exit(1);
});
