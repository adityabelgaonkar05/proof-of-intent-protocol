import * as fs from 'fs';
import * as path from 'path';
import type { Config } from './types';

const ENS_RESOLVER_ADDRESS = '0x8FADE66B79cC9f707aB26799354482EB93a5B7dD';
const ENS_REGISTRY_ADDRESS = '0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e';

// Hardcoded Sepolia defaults — used when deployed.json is absent (clean install).
const SEPOLIA_DEFAULTS: Record<string, string> = {
  agentRegistry:      '0xcD5954121BbE13a4867c2Df886e24E924D006883',
  intentRegistry:     '0xf2a52EAf8E2440F9aFa28aDA5426Bc2908DDc5b4',
  delegationRegistry: '0x51bF1E9C33ACF135E7C6ca83AD4Cf36d5B8BBa45',
  executionGate:      '0x076e8cd66be8B927CcB9adA63505e8027b209cb6',
};

// Optional: load a deployed.json override (e.g. local dev deployment).
// Falls back to SEPOLIA_DEFAULTS when no file is found.
function loadDeployedJson(): Record<string, string> {
  const candidates = [
    path.resolve(__dirname, '../deployed.json'),   // bundled alongside dist/
    path.resolve(__dirname, '../../config/deployed.json'), // monorepo dev
  ];
  for (const p of candidates) {
    try {
      const raw = fs.readFileSync(p, 'utf8');
      return { ...SEPOLIA_DEFAULTS, ...(JSON.parse(raw) as Record<string, string>) };
    } catch {
      // not present — try next
    }
  }
  return SEPOLIA_DEFAULTS;
}

/**
 * Build a Config from environment variables, with optional field overrides.
 * Contract addresses fall back to hardcoded Sepolia defaults when env vars are not set.
 * Priority: overrides > env vars > deployed.json > built-in Sepolia defaults.
 */
export function loadConfig(overrides?: Partial<Config>): Config {
  const deployed = loadDeployedJson();
  return {
    rpcUrl: process.env.RPC_URL ?? 'https://ethereum-sepolia-rpc.publicnode.com',
    chainId: parseInt(process.env.CHAIN_ID ?? '11155111', 10),
    agentRegistryAddress: process.env.AGENT_REGISTRY_ADDRESS ?? deployed['agentRegistry'],
    intentRegistryAddress: process.env.INTENT_REGISTRY_ADDRESS ?? deployed['intentRegistry'],
    delegationRegistryAddress: process.env.DELEGATION_REGISTRY_ADDRESS ?? deployed['delegationRegistry'],
    executionGateAddress: process.env.EXECUTION_GATE_ADDRESS ?? deployed['executionGate'],
    ensName: process.env.ENS_NAME ?? '',
    ensResolverAddress: ENS_RESOLVER_ADDRESS,
    ensRegistryAddress: ENS_REGISTRY_ADDRESS,
    zgApiKey: process.env.ZG_API_KEY ?? '',
    zgRpcUrl: process.env.ZG_RPC_URL ?? 'https://evmrpc-testnet.0g.ai',
    zgIndexerUrl: process.env.ZG_INDEXER_URL ?? 'https://indexer-storage-testnet-turbo.0g.ai',
    ...overrides,
  };
}

/**
 * Convert a deployed.json object (keys: agentRegistry, intentRegistry,
 * delegationRegistry, executionGate) into Config overrides.
 */
export function loadDeployedAddresses(deployed: Record<string, string>): Partial<Config> {
  return {
    agentRegistryAddress: deployed['agentRegistry'],
    intentRegistryAddress: deployed['intentRegistry'],
    delegationRegistryAddress: deployed['delegationRegistry'],
    executionGateAddress: deployed['executionGate'],
  };
}
