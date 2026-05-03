# proof-of-intent Python SDK

Python SDK for the [Proof-of-Intent Protocol](https://github.com/proof-of-intent-protocol) —
on-chain intent registration, cryptographic delegation, and scope-enforced execution on
Ethereum Sepolia.

## Install

```bash
pip install proof-of-intent
```

## Environment variables

```bash
# Required: your wallet private key (Sepolia testnet only)
PRIVATE_KEY=0x...

# Optional — for compile_intent() (set one or both; Claude takes priority)
CLAUDE_API_KEY=sk-ant-...   # default model: claude-haiku-4-5-20251001
OPENAI_API_KEY=sk-proj-...  # default model: gpt-5-mini
# MODEL=                    # override whichever model is selected
```

## Five-line quickstart

```python
import os
from proof_of_intent import ContractClient, usdc, in_hours, UNISWAP_V3

# Instantiate — all contract addresses default to deployed Sepolia contracts
client = ContractClient(private_key=os.environ["PRIVATE_KEY"])

# Register an intent (build + EIP-712 sign + on-chain register in one call)
intent_id = client.create_intent(
    token_in="0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",  # Sepolia USDC
    max_amount_in=usdc(100),      # 100 USDC
    min_amount_out=1,
    allowed_protocols=["Uniswap-V3"],
    deadline=in_hours(1),
)
print("intent registered:", intent_id)

# Delegate execution rights to an agent address
delegation_id = client.delegate_from_root(
    intent_id,
    child_scope={
        "maxAmountIn":      usdc(100),
        "minAmountOut":     1,
        "allowedProtocols": [UNISWAP_V3.hex()],
        "deadline":         in_hours(1),
    },
    delegate_to=client.account.address,   # delegate to self for demo
)
print("delegation created:", delegation_id)
```

## Helpers

```python
from proof_of_intent import usdc, weth, in_minutes, in_hours, UNISWAP_V3, CURVE

usdc(500)          # → 500_000_000   (500 USDC in raw units)
weth(0.15)         # → 150_000_000_000_000_000
in_minutes(60)     # → Unix timestamp 60 minutes from now
in_hours(1)        # → Unix timestamp 1 hour from now
UNISWAP_V3.hex()   # → "0x1cc..."  (bytes32 protocol ID)
```

## Error handling

```python
from proof_of_intent.errors import ScopeViolationError, DeadlineExpiredError, POIPError

try:
    client.delegate_from_delegation(parent_id, child_scope, agent)
except ScopeViolationError:
    print("child scope exceeds parent — blocked by the contract")
except DeadlineExpiredError:
    print("deadline has passed")
except POIPError as e:
    print("other protocol error:", e)
```

## Natural-language intent compilation (optional)

```bash
pip install "proof-of-intent[ai]"
```

```python
import os
from proof_of_intent import compile_intent, build_intent, sign_intent, ContractClient, in_hours

# Uses CLAUDE_API_KEY if set (claude-haiku-4-5-20251001), else OPENAI_API_KEY (gpt-5-mini).
# Set MODEL=<id> to override the default model for whichever provider is selected.
compiled = compile_intent("swap 500 USDC for WETH via Uniswap, deadline 1 hour")
# Returns:
# {
#   "token_in":          "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
#   "max_amount_in":     500000000,
#   "min_amount_out":    <int>,
#   "allowed_protocols": ["Uniswap-V3"],
#   "deadline":          <unix timestamp>
# }

# One-liner: pass directly into create_intent()
client    = ContractClient(private_key=os.environ["PRIVATE_KEY"])
intent_id = client.create_intent(**compiled)

# Or unpack into build_intent() for full control:
intent = build_intent(
    owner=client.account.address,
    authorized_orchestrator=client.account.address,
    token_in=compiled["token_in"],
    max_amount_in=compiled["max_amount_in"],
    min_amount_out=compiled["min_amount_out"],
    allowed_protocols=compiled["allowed_protocols"],
    deadline=compiled["deadline"],
    nonce=0,  # fetch from contract: client.intent_registry.functions.nonces(addr).call()
)
```


## Contributors

- [@adityabelgaonkar05](https://github.com/adityabelgaonkar05)
- [@akankshaagroya](https://github.com/akankshaagroya)
