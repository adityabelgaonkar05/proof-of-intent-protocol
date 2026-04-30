# Uniswap V3 Integration Feedback

Honest builder feedback from integrating SwapRouter02 into an intent-delegation protocol
on Ethereum Sepolia. The protocol has an `ExecutionGate` contract that pulls USDC from a
user, calls the router, and delivers WETH to a recipient — a straightforward single-hop swap
as a contract caller, not a wallet.

---

## The SwapRouter02 interface is not in the main npm package and this is a real problem

This was the first real blocker. `@uniswap/v3-periphery` ships `ISwapRouter.json` — which is
SwapRouter **01**. SwapRouter02's `ExactInputSingleParams` removes `deadline`. SwapRouter01's
keeps it. The structs are otherwise identical.

The consequence: if you copy the interface from the periphery repo or the npm package, you
write a Solidity interface with a `deadline` field. The function selector doesn't match. You
call `exactInputSingle`, the transaction reverts with no reason string, and you have no idea
why. I spent time re-checking my approval flow, my amounts, my token addresses — none of
which were wrong — before I realised the ABI was the problem.

SwapRouter02 lives in `@uniswap/swap-router-contracts`, a completely separate package that is
not mentioned anywhere in the main V3 integration guide. The correct interface is
`IV3SwapRouter.sol` in that repo. The main docs link to the periphery repo throughout.

Fix: the integration guide should say in the first paragraph: "If you're using SwapRouter02
(deployed at 0x68b3...), use `@uniswap/swap-router-contracts`, not `@uniswap/v3-periphery`.
The structs differ."

---

## Testnet pools are a black box

The docs recommend `amountOutMinimum > 0` for slippage protection. Good. But on Sepolia there
is no way to know whether the pool you're targeting (a) exists, (b) has any liquidity, or (c)
uses a fee tier that matches what you're passing. The Uniswap app doesn't display Sepolia
pools. The V3 subgraph isn't reliably indexed on Sepolia.

The practical result: you call `exactInputSingle` with `fee = 500` and get a revert. You try
`fee = 3000` and get a revert. You're not sure whether the pool doesn't exist at all, whether
your `amountOutMinimum` is too high for available liquidity, or whether you're hitting a
completely empty pool that just returns 0 when `amountOutMinimum = 0`. Each of these feels
identical from the outside — you get a transaction failure or a silent success with zero output.

There's no `getPool()` conveniently accessible from the router itself on SwapRouter02 (the
factory address isn't a public field). You have to separately look up the factory address,
make an off-chain call to `factory.getPool(tokenA, tokenB, fee)`, and check for `address(0)`
before you even attempt a swap. This is a mandatory step for any production integration and
it isn't in the tutorial.

---

## The error messages are nearly useless

When something goes wrong inside the pool, you get three-letter errors: `SPL`, `LOK`, `IIA`.
These are storage variable names from inside Uniswap's pool contracts that were kept short to
save gas. Fair tradeoff on mainnet. But on testnet where you're debugging, a `LOK` revert
tells you almost nothing. You have to know that `LOK` means the pool's re-entrancy lock is
engaged, which on a testnet usually means the pool got into a bad state from a prior failed
transaction, not that your code is wrong.

I'd want either: (1) a debug build of the pool contracts with full error strings that's
available on testnets, or (2) a lookup table in the docs mapping these abbreviations to their
meaning and common causes.

---

## The approve-from-contract pattern isn't covered

Every tutorial shows a wallet directly calling the router after approving it. No tutorial shows
the pattern where a smart contract is the `msg.sender` to the router. This is a different flow:

- The user approves **your contract** (not the router)
- Your contract calls `transferFrom` to pull funds from the user
- Your contract approves the **router** to spend those funds
- Your contract calls `exactInputSingle` — the router pulls from your contract

This is the only sensible architecture for any protocol that sits between the user and the DEX
(aggregators, intent systems, smart accounts, etc.). But the docs don't cover it. The mental
model they sell is wallet → router, and bridging to contract → router requires inferring from
the periphery source code how `TransferHelper.safeTransferFrom(tokenIn, msg.sender, pool, ...)` 
works. It's discoverable but it should be documented.

---

## `sqrtPriceLimitX96 = 0` is never explained well

The docs say "use 0 for no price limit." What they don't say: with `sqrtPriceLimitX96 = 0`
and `amountOutMinimum = 0`, the call will succeed and return 0 tokens if the pool is empty or
illiquid. It looks like a successful swap. You get a SwapExecuted log, the tx has status 1,
and the user just lost their tokenIn.

For a test on Sepolia with a sparse pool, this meant a transaction that appeared to work but
actually did nothing useful. The fix is obvious (`amountOutMinimum > 0`) but the docs should
be explicit: "if you set both of these to 0, you have no protection and the router will happily
output nothing."

---

## What actually worked well

The core contract surface is genuinely good. `exactInputSingle` with a single struct call is
the right abstraction — no tick math, no pool address resolution, no callback to implement.
The fee-tier model (100/500/3000/10000 bps) maps cleanly to intent parameters. The fact that
SwapRouter02 handles permit2 and multicall transparently is useful for more complex flows.

The deployment addresses were stable throughout development. No surprise contract upgrades,
no address changes. That reliability matters when you're building on top of a dependency.

---

## What I'd actually want

1. One page titled "Integrating as a smart contract caller (not a wallet)" — covers the double-approve pattern, `msg.sender` semantics, and how to avoid the common mistake of having the user approve the router directly.

2. `factory.getPool()` check as a mandatory step in any swap tutorial, with sample code.

3. A Sepolia pool seeder or at minimum a list of which USDC/WETH pools have testnet liquidity and at which fee tiers. Even a rough "here are the pools we've seeded on Sepolia" in the docs would save hours.

4. The SwapRouter02 ABI in `@uniswap/v3-periphery` or a clear redirect at the top of the SwapRouter page.
