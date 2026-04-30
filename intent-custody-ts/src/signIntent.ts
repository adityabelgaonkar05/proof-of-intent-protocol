import { Wallet, getAddress, id } from 'ethers';
import type { IntentData } from './types';

const INTENT_TYPES = {
  Intent: [
    { name: 'owner', type: 'address' },
    { name: 'authorizedOrchestrator', type: 'address' },
    { name: 'tokenIn', type: 'address' },
    { name: 'maxAmountIn', type: 'uint256' },
    { name: 'minAmountOut', type: 'uint256' },
    { name: 'allowedProtocols', type: 'bytes32[]' },
    { name: 'deadline', type: 'uint256' },
    { name: 'nonce', type: 'uint256' },
  ],
};

/**
 * EIP-712 sign an IntentData object.
 * Returns a 0x-prefixed hex signature.
 */
export async function signIntent(
  intent: IntentData,
  privateKey: string,
  config: { chainId: number; intentRegistryAddress: string },
): Promise<string> {
  const wallet = new Wallet(privateKey);
  const domain = {
    name: 'IntentRegistry',
    version: '1',
    chainId: config.chainId,
    verifyingContract: config.intentRegistryAddress,
  };
  return wallet.signTypedData(domain, INTENT_TYPES, intent);
}

/**
 * Build an IntentData object from human-readable inputs.
 * Protocol names (e.g. "Uniswap-V3") are hashed to bytes32 automatically.
 */
export function buildIntent(params: {
  owner: string;
  authorizedOrchestrator: string;
  tokenIn: string;
  maxAmountIn: bigint;
  minAmountOut: bigint;
  /** Protocol names, e.g. ["Uniswap-V3", "Curve"] */
  allowedProtocols: string[];
  deadline: bigint;
  nonce: bigint;
}): IntentData {
  return {
    owner: getAddress(params.owner),
    authorizedOrchestrator: getAddress(params.authorizedOrchestrator),
    tokenIn: getAddress(params.tokenIn),
    maxAmountIn: params.maxAmountIn,
    minAmountOut: params.minAmountOut,
    allowedProtocols: params.allowedProtocols.map(id),
    deadline: params.deadline,
    nonce: params.nonce,
  };
}
