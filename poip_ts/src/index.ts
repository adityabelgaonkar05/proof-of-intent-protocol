export type { IntentData, ScopeData, TxParamsData, DelegationData, Config } from './types';

export { loadConfig, loadDeployedAddresses } from './config';

export {
  UNISWAP_V3,
  CURVE,
  BALANCER_V2,
  AAVE_V3,
  ONEINCH,
  ALL_PROTOCOLS,
  PROTOCOL_NAMES,
  protocolName,
  protocolId,
} from './protocolIds';

export { signIntent, buildIntent, buildScope } from './signIntent';

export {
  toUsdc, fromUsdc,
  toWeth, fromWeth,
  toToken, fromToken,
  inMinutes, inHours,
  // Short-name aliases matching the Python SDK surface
  usdc, weth,
} from './helpers';

export type { CompiledIntent } from './compiler';
export { compileIntent } from './compiler';

export type { ContractClientOptions } from './contractClient';
export {
  ContractClient,
  getProvider,
  getNonce,
  getDomainSeparator,
  registerIntentRaw,
  extractIntentIdFromReceipt,
  delegateFromRoot,
  delegateFromDelegation,
  extractDelegationIdFromReceipt,
  getDelegation,
  verifyChain,
  executeSwap,
} from './contractClient';
