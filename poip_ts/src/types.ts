export interface IntentData {
  owner: string;
  authorizedOrchestrator: string;
  tokenIn: string;
  maxAmountIn: bigint;
  minAmountOut: bigint;
  /** bytes32 hex strings — keccak256 of each protocol name */
  allowedProtocols: string[];
  deadline: bigint;
  nonce: bigint;
}

export interface ScopeData {
  maxAmountIn: bigint;
  minAmountOut: bigint;
  /** bytes32 hex strings — keccak256 of each protocol name */
  allowedProtocols: string[];
  deadline: bigint;
}

export interface TxParamsData {
  amountIn: bigint;
  minAmountOut: bigint;
  /** bytes32 hex string — keccak256 of protocol name */
  protocol: string;
  tokenIn: string;
  tokenOut: string;
  recipient: string;
}

export interface DelegationData {
  parentId: string;
  isRootIntent: boolean;
  scope: ScopeData;
  delegatedTo: string;
  executed: boolean;
}

export interface Config {
  rpcUrl: string;
  chainId: number;
  agentRegistryAddress: string;
  intentRegistryAddress: string;
  delegationRegistryAddress: string;
  executionGateAddress: string;
  ensName: string;
  ensResolverAddress: string;
  ensRegistryAddress: string;
  zgApiKey: string;
  zgRpcUrl: string;
  zgIndexerUrl: string;
}
