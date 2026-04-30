import type { Config } from './types';

const ENS_RESOLVER_ADDRESS = '0x8FADE66B79cC9f707aB26799354482EB93a5B7dD';
const ENS_REGISTRY_ADDRESS = '0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e';

/**
 * Build a Config from environment variables, with optional field overrides.
 * Contract addresses default to empty strings — you must supply them either
 * via env vars or the overrides argument.
 */
export function loadConfig(overrides?: Partial<Config>): Config {
  return {
    rpcUrl: process.env.RPC_URL ?? 'https://ethereum-sepolia-rpc.publicnode.com',
    chainId: parseInt(process.env.CHAIN_ID ?? '11155111', 10),
    agentRegistryAddress: process.env.AGENT_REGISTRY_ADDRESS ?? '',
    intentRegistryAddress: process.env.INTENT_REGISTRY_ADDRESS ?? '',
    delegationRegistryAddress: process.env.DELEGATION_REGISTRY_ADDRESS ?? '',
    executionGateAddress: process.env.EXECUTION_GATE_ADDRESS ?? '',
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
