import { id } from 'ethers';

export const UNISWAP_V3 = id('Uniswap-V3');
export const CURVE = id('Curve');
export const BALANCER_V2 = id('Balancer-V2');
export const AAVE_V3 = id('Aave-V3');
export const ONEINCH = id('1inch');

export const PROTOCOL_NAMES: Record<string, string> = {
  [UNISWAP_V3]: 'Uniswap-V3',
  [CURVE]: 'Curve',
  [BALANCER_V2]: 'Balancer-V2',
  [AAVE_V3]: 'Aave-V3',
  [ONEINCH]: '1inch',
};

export const ALL_PROTOCOLS = [UNISWAP_V3, CURVE, BALANCER_V2, AAVE_V3, ONEINCH];

/** Return the human-readable name for a protocol bytes32 hash. */
export function protocolName(hash: string): string {
  return PROTOCOL_NAMES[hash] ?? 'Unknown';
}

/** Return the bytes32 keccak256 hash for a protocol name string. */
export function protocolId(name: string): string {
  return id(name);
}
