/**
 * Human-readable helpers for token amounts and deadlines.
 *
 * Import from the package root:
 *   import { toUsdc, toWeth, inMinutes } from 'proof-of-intent';
 *
 * For precision-critical amounts (> 15 significant digits) use BigInt
 * arithmetic directly rather than these helpers.
 */

/** Convert a human-readable USDC amount to raw units (6 decimals). toUsdc(500) → 500_000_000n */
export function toUsdc(amount: number): bigint {
  return BigInt(Math.round(amount * 1e6));
}

/** Convert raw USDC units to a human-readable amount. fromUsdc(500_000_000n) → 500 */
export function fromUsdc(units: bigint): number {
  return Number(units) / 1e6;
}

/** Convert a human-readable ETH/WETH amount to raw units (18 decimals). toWeth(0.15) → 150_000_000_000_000_000n */
export function toWeth(amount: number): bigint {
  return BigInt(Math.round(amount * 1e18));
}

/** Convert raw WETH/ETH units to a human-readable amount. fromWeth(150_000_000_000_000_000n) → 0.15 */
export function fromWeth(units: bigint): number {
  return Number(units) / 1e18;
}

/** Convert a human-readable token amount to raw units for any ERC20. toToken(100, 6) → 100_000_000n */
export function toToken(amount: number, decimals: number): bigint {
  return BigInt(Math.round(amount * 10 ** decimals));
}

/** Convert raw ERC20 units to a human-readable amount. */
export function fromToken(units: bigint, decimals: number): number {
  return Number(units) / 10 ** decimals;
}

/**
 * Return a Unix timestamp (as bigint) n minutes from now.
 * Use as the deadline parameter:
 *   deadline: inMinutes(60)   // valid for 1 hour
 */
export function inMinutes(n: number): bigint {
  return BigInt(Math.floor(Date.now() / 1000) + n * 60);
}
