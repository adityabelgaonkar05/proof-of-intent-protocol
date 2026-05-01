import { useState } from 'react'

/* ── code strings ─────────────────────────────────────────────── */
const PY_INSTALL = `pip install proof-of-intent

# With dev extras (pytest, python-dotenv)
pip install "proof-of-intent[dev]"

# With AI extras (anthropic, openai) for compile_intent()
pip install "proof-of-intent[ai]"`

const PY_ENV = `# .env — copy from poip_py/.env.example

# Required
PRIVATE_KEY=0x...

# Optional — for compile_intent()
CLAUDE_API_KEY=sk-ant-...

# Optional — 0G decentralised storage (leave blank to skip)
ZG_API_KEY=0x...
ZG_RPC_URL=https://evmrpc-testnet.0g.ai
ZG_INDEXER_URL=https://indexer-storage-testnet-turbo.0g.ai`

const PY_HELPERS = `from proof_of_intent import usdc, weth, token, in_hours, in_minutes
from proof_of_intent import from_usdc, from_weth, from_token

usdc(40)               # → 40_000_000          (6 decimals)
usdc(0.5)              # → 500_000
weth(0.01)             # → 10_000_000_000_000_000
token(100, 18)         # → 100_000_000_000_000_000_000  (generic)
in_hours(2)            # → int(time.time()) + 7200
in_minutes(30)         # → int(time.time()) + 1800

from_usdc(40_000_000)                    # → 40.0
from_weth(10_000_000_000_000_000)        # → 0.01`

const PY_QUICKSTART = `import os
from proof_of_intent import (
    ContractClient, build_intent, sign_intent,
    usdc, weth, in_hours, UNISWAP_V3,
)

USDC = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"   # Sepolia USDC
WETH = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"   # Sepolia WETH

client = ContractClient(private_key=os.environ["PRIVATE_KEY"])
addr   = client.account.address

# One-call convenience: build + sign + register
intent_id = client.create_intent(
    token_in=USDC,
    max_amount_in=usdc(40),          # user authorizes 40 USDC max
    min_amount_out=weth(0.01),
    allowed_protocols=["Uniswap-V3"],
    deadline=in_hours(2),
)
print("intentId:", intent_id)

# Orchestrator creates root delegation
scope = ContractClient.build_scope(
    max_amount_in=usdc(40),
    min_amount_out=weth(0.01),
    allowed_protocols=["Uniswap-V3"],
    deadline=in_hours(2),
)
delegation_id = client.delegate_from_root(intent_id, scope, addr)

# Verify chain (view call — no gas)
tx_params = {
    "amountIn":     usdc(4),          # actual swap: 4 USDC
    "minAmountOut": weth(0.001),
    "protocol":     UNISWAP_V3.hex(),
    "tokenIn":      USDC,
    "tokenOut":     WETH,
    "recipient":    addr,
}
assert client.verify_chain(delegation_id, tx_params)

# Execute
client.ensure_token_approval(USDC, client.execution_gate.address, usdc(4))
tx_hash = client.execute_swap(delegation_id, tx_params)
print("https://sepolia.etherscan.io/tx/" + tx_hash)`

const PY_ERRORS_CODE = `from proof_of_intent.errors import (
    TransactionRevertError,
    ScopeViolationError,
    DeadlineExpiredError,
)

try:
    delegation_id = orch.delegate_from_root(intent_id, bad_scope, agent)
except ScopeViolationError as exc:
    print(exc.reason)    # "Amount exceeds scope"
except DeadlineExpiredError as exc:
    print(exc.reason)    # "Deadline expired"
except TransactionRevertError as exc:
    print(exc.reason)    # any other revert string

# Error hierarchy:
# POIPError → TransactionRevertError → ScopeViolationError / DeadlineExpiredError`

const PY_COMPILER = `from agents.compiler import compile_intent, display_intent

# Convert plain English to a structured intent dict
compiled = compile_intent("swap 4 USDC for max ETH via Uniswap, deadline 30 min")
display_intent(compiled)

# Returns:
# {
#   "tokenIn":         "USDC",
#   "tokenInAddress":  "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
#   "maxAmountIn":     4000000,
#   "minAmountOut":    <int>,
#   "allowedProtocols": ["Uniswap-V3"],
#   "deadlineMinutes": 30,
#   "reasoning":       "<one sentence from LLM>"
# }

# Interactive REPL:
# python -m agents.compiler`

/* ── TypeScript strings ───────────────────────────────────────── */
const TS_INSTALL = `npm i proof-of-intent

# ethers ^6.0.0 is a required peer dependency
npm i ethers`

const TS_ENV = `# .env — copy from poip_ts/.env.example

# Required
PRIVATE_KEY=0x...

# Optional — for compileIntent()
CLAUDE_API_KEY=sk-ant-...

# Optional — 0G decentralised storage (leave blank to skip)
ZG_API_KEY=0x...
ZG_RPC_URL=https://evmrpc-testnet.0g.ai
ZG_INDEXER_URL=https://indexer-storage-testnet-turbo.0g.ai`

const TS_QUICKSTART = `import { ethers } from 'ethers'
import {
  ContractClient, buildIntent, buildScope, signIntent,
  usdc, weth, inHours, UNISWAP_V3, loadConfig, getNonce,
} from 'proof-of-intent'

const USDC = '0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238'
const WETH = '0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14'

const config = loadConfig()                                    // Sepolia defaults
const wallet = new ethers.Wallet(process.env.PRIVATE_KEY!)
const client = new ContractClient({ privateKey: wallet.privateKey, ...config })

// 1. Build + sign + register
const nonce  = await getNonce(config, wallet.address)
const intent = buildIntent({
  owner: wallet.address,
  authorizedOrchestrator: wallet.address,
  tokenIn: USDC,
  maxAmountIn: usdc(40),          // user authorizes 40 USDC max
  minAmountOut: weth(0.01),
  allowedProtocols: ['Uniswap-V3'],
  deadline: inHours(2),
  nonce,
})
const sig      = await signIntent(intent, wallet.privateKey, config)
const intentId = await client.registerIntent(intent, sig)

// 2. Delegate
const scope        = buildScope({ maxAmountIn: usdc(40), minAmountOut: weth(0.01),
                                  allowedProtocols: ['Uniswap-V3'], deadline: inHours(2) })
const delegationId = await client.delegateFromRoot(intentId, scope, wallet.address)

// 3. Verify + execute
const txParams = {
  amountIn:     usdc(4),          // actual swap: 4 USDC
  minAmountOut: weth(0.001),
  protocol:     UNISWAP_V3,       // ← pre-hashed bytes32, NOT the string "Uniswap-V3"
  tokenIn:      USDC,
  tokenOut:     WETH,
  recipient:    wallet.address,
}
if (await client.verifyChain(delegationId, txParams)) {
  await client.ensureTokenApproval(USDC, config.executionGateAddress, usdc(4))
  const txHash = await client.executeSwap(delegationId, txParams)
  console.log('https://sepolia.etherscan.io/tx/' + txHash)
}`

const TS_PROTOCOL = `// buildIntent() and buildScope() auto-hash protocol names — pass strings freely
const intent = buildIntent({ ..., allowedProtocols: ['Uniswap-V3'] })  // ✓
const scope  = buildScope({  ..., allowedProtocols: ['Uniswap-V3'] })  // ✓

// txParams.protocol is NOT auto-hashed — always use the exported constant
import { UNISWAP_V3, AAVE_V3, CURVE, BALANCER_V2, ONEINCH } from 'proof-of-intent'

const txParams = {
  protocol: UNISWAP_V3,         // ✓ pre-hashed bytes32
  // protocol: 'Uniswap-V3',   // ✗ raw string — will NOT match on-chain
}

// Or hash dynamically:
import { protocolId } from 'proof-of-intent'
const id = protocolId('Uniswap-V3')  // same result as UNISWAP_V3`

/* ── Shared data ──────────────────────────────────────────────── */
const AXL_PIPELINE = `# All three nodes must run from the PROJECT ROOT (key paths are relative)

# Terminal 1 — Orchestrator bootstrap node
./vendor/axl/node -config agents/axl_configs/orchestrator.json

# Terminal 2 — Research node  (peers to orchestrator on boot)
./vendor/axl/node -config agents/axl_configs/research.json

# Terminal 3 — Execution node (peers to orchestrator on boot)
./vendor/axl/node -config agents/axl_configs/execution.json

# Wait ~5 s for mesh convergence, then start agents:

# Terminal 4
python -m agents.execution_agent

# Terminal 5 (add --compromised to trigger attack scenario)
python -m agents.research_agent

# Terminal 6
python -m agents.orchestrator <INTENT_ID> "swap 4 USDC for max WETH"`

const PY_METHODS = [
  { sig: 'ContractClient(private_key, *, rpc_url, chain_id, ...)',
    desc: 'Main SDK class. private_key is positional; all overrides keyword-only. Sepolia addresses hardcoded as defaults.' },
  { sig: '.create_intent(token_in, max_amount_in, min_amount_out, allowed_protocols, deadline, orchestrator?, owner?) → str',
    desc: 'Build + sign + register in one call. Returns intentId. Convenience wrapper over build_intent + sign_intent + register_intent.' },
  { sig: '.register_intent(intent, signature) → str',
    desc: 'Submit a pre-built, pre-signed intent on-chain. Returns bytes32 intentId.' },
  { sig: '.delegate_from_root(intent_id, scope, delegate_to) → str',
    desc: 'Create the root delegation from an intent to a registered agent. Returns delegationId.' },
  { sig: '.delegate_from_delegation(parent_id, scope, delegate_to) → str',
    desc: 'Sub-delegate with a strictly narrowed scope.' },
  { sig: '.execute_swap(delegation_id, tx_params) → str',
    desc: 'Execute swap via ExecutionGate. Atomically verifies the full delegation chain before tokens move.' },
  { sig: '.verify_chain(delegation_id, tx_params) → bool',
    desc: 'View call — validate chain without gas. Use this to pre-check before execute_swap.' },
  { sig: '.ensure_token_approval(token, spender, amount) → None',
    desc: 'Approve ERC20 spending only if current allowance < amount. No-op if already sufficient.' },
  { sig: '.token_balance(token, account) → int',
    desc: 'ERC20 balance in raw units (e.g. 40_000_000 for 40 USDC).' },
  { sig: '.register_agent(address, name, skip_if_active?) → str|None',
    desc: 'Register address in AgentRegistry. Agents must be registered before they can receive delegations.' },
  { sig: 'ContractClient.build_scope(max_amount_in, min_amount_out, allowed_protocols, deadline) → dict',
    desc: 'Static method. Build a scope dict with auto-hashed protocol names. Use for delegate_from_root / delegate_from_delegation.' },
]

const TS_METHODS = [
  { sig: 'new ContractClient({ privateKey, rpcUrl?, chainId?, ...addresses })',
    desc: 'Options-object constructor. All address fields optional — loadConfig() provides Sepolia defaults.' },
  { sig: '.registerIntent(intent, sig) → Promise<string>',
    desc: 'Submit signed intent on-chain. Returns bytes32 intentId.' },
  { sig: '.delegateFromRoot(intentId, scope, delegateTo) → Promise<string>',
    desc: 'Create root delegation. Returns delegationId.' },
  { sig: '.delegateFromDelegation(parentId, scope, delegateTo) → Promise<string>',
    desc: 'Sub-delegate with a strictly narrowed scope.' },
  { sig: '.executeSwap(delegationId, txParams) → Promise<string>',
    desc: 'Execute via ExecutionGate. Atomically verifies full chain.' },
  { sig: '.verifyChain(delegationId, txParams) → Promise<boolean>',
    desc: 'View call — no gas. Pre-validate before executeSwap.' },
  { sig: '.ensureTokenApproval(token, spender, amount) → Promise<void>',
    desc: 'Approve ERC20 only if allowance is insufficient.' },
  { sig: '.tokenBalance(token, account) → Promise<bigint>',
    desc: 'ERC20 balance as bigint.' },
  { sig: 'signIntent(intent, key, config) → Promise<string>',
    desc: 'Module-level EIP-712 signer. Returns hex signature.' },
  { sig: 'getNonce(config, owner) → Promise<bigint>',
    desc: 'Module-level. Fetch nonce from IntentRegistry.' },
  { sig: 'buildIntent(params) → IntentData',
    desc: 'Sync. Auto-hashes allowedProtocols to bytes32.' },
  { sig: 'buildScope(params) → ScopeData',
    desc: 'Sync. Auto-hashes allowedProtocols to bytes32.' },
  { sig: 'loadConfig(overrides?) → Config',
    desc: 'Load from env vars; fall back to Sepolia defaults for all address fields.' },
]

const TS_EXPORTS = [
  { name: 'ContractClient', type: 'class',    desc: 'Main SDK class — async methods, options-object constructor' },
  { name: 'buildIntent', type: 'function',    desc: 'Build IntentData — auto-hashes protocol names' },
  { name: 'buildScope',  type: 'function',    desc: 'Build ScopeData — auto-hashes protocol names' },
  { name: 'signIntent',  type: 'function',    desc: 'EIP-712 sign an intent — returns hex string' },
  { name: 'loadConfig',  type: 'function',    desc: 'Load Config from env vars + Sepolia defaults' },
  { name: 'getNonce',    type: 'function',    desc: 'Fetch nonce from IntentRegistry' },
  { name: 'verifyChain', type: 'function',    desc: 'Module-level read-only chain verify' },
  { name: 'usdc / toUsdc', type: 'helper',   desc: 'n → bigint in USDC base units (6 decimals)' },
  { name: 'fromUsdc',    type: 'helper',      desc: 'bigint → number in USDC' },
  { name: 'weth / toWeth', type: 'helper',   desc: 'n → bigint in WETH base units (18 decimals)' },
  { name: 'fromWeth',    type: 'helper',      desc: 'bigint → number in WETH' },
  { name: 'inHours / inMinutes', type: 'helper', desc: 'bigint Unix timestamp offset from now' },
  { name: 'UNISWAP_V3',  type: 'constant',   desc: 'Pre-hashed bytes32 — keccak256("Uniswap-V3")' },
  { name: 'AAVE_V3',     type: 'constant',   desc: 'Pre-hashed bytes32 — keccak256("Aave-V3")' },
  { name: 'CURVE',       type: 'constant',   desc: 'Pre-hashed bytes32 — keccak256("Curve")' },
  { name: 'BALANCER_V2', type: 'constant',   desc: 'Pre-hashed bytes32 — keccak256("Balancer-V2")' },
  { name: 'protocolId(name)',   type: 'function', desc: 'Hash a protocol name to bytes32' },
  { name: 'protocolName(id)',   type: 'function', desc: 'Reverse lookup a protocol constant' },
]

const PY_EXPORTS = [
  { name: 'ContractClient',       type: 'class',    desc: 'Main SDK class' },
  { name: 'build_intent',         type: 'function', desc: 'Build intent dict — auto-hashes protocol names' },
  { name: 'sign_intent',          type: 'function', desc: 'EIP-712 sign — returns hex string' },
  { name: 'usdc(amount)',         type: 'helper',   desc: 'amount → int in USDC base units (6 decimals)' },
  { name: 'from_usdc(units)',     type: 'helper',   desc: 'reverse conversion' },
  { name: 'weth(amount)',         type: 'helper',   desc: 'amount → int in WETH base units (18 decimals)' },
  { name: 'from_weth(units)',     type: 'helper',   desc: 'reverse conversion' },
  { name: 'token(amount, dec)',   type: 'helper',   desc: 'generic ERC20 amount conversion' },
  { name: 'in_hours(n)',          type: 'helper',   desc: 'Unix timestamp n hours from now' },
  { name: 'in_minutes(n)',        type: 'helper',   desc: 'Unix timestamp n minutes from now' },
  { name: 'UNISWAP_V3',          type: 'constant', desc: 'Pre-hashed bytes32 — keccak256("Uniswap-V3")' },
  { name: 'AAVE_V3',             type: 'constant', desc: 'Pre-hashed bytes32' },
  { name: 'CURVE',               type: 'constant', desc: 'Pre-hashed bytes32' },
  { name: 'BALANCER_V2',         type: 'constant', desc: 'Pre-hashed bytes32' },
  { name: 'TransactionRevertError', type: 'error',  desc: 'Base error class with .reason attribute' },
  { name: 'ScopeViolationError',  type: 'error',   desc: 'Raised when child scope exceeds parent bounds' },
  { name: 'DeadlineExpiredError', type: 'error',   desc: 'Raised when deadline has passed' },
]

const COMMON_ERRORS = [
  { code: 'Amount exceeds scope',     fix: 'Child scope maxAmountIn is larger than the parent. Scope can only narrow — never widen.' },
  { code: 'MinOut below root',        fix: 'Child scope minAmountOut is below the root floor. Cannot accept worse slippage than the user signed.' },
  { code: 'Deadline exceeds root',    fix: 'Child scope deadline is later than the root intent. Delegations cannot extend the authorized window.' },
  { code: 'Protocols not subset',     fix: 'Child scope includes a protocol not in parent allowlist. Must be a strict subset.' },
  { code: 'Not authorized orchestrator', fix: 'Caller is not the orchestrator named in the intent. Only the named orchestrator can create a root delegation.' },
  { code: 'Target not registered agent', fix: 'delegateTo address is not in AgentRegistry. Agents must register before receiving delegations.' },
  { code: 'Root already delegated',   fix: 'Each intent produces exactly one root delegation.' },
  { code: 'Already executed',         fix: 'Each delegation can trigger exactly one execution.' },
  { code: 'Already sub-delegated',    fix: 'Each delegation can be sub-delegated exactly once.' },
  { code: 'Invalid signature',        fix: 'EIP-712 signature does not match intent owner. Check intent data or signing key.' },
  { code: 'Wrong token',              fix: 'tokenIn does not match the root intent. Agent tried to swap a different asset.' },
  { code: 'Protocol not allowed',     fix: 'Swap protocol not in delegation\'s allowedProtocols list.' },
  { code: 'Chain verification failed', fix: 'One or more nodes in the delegation chain failed validation. Verify the full path.' },
  { code: 'Intent not found',         fix: 'No intent exists for the provided intentId. Verify the ID was returned from register_intent.' },
  { code: 'ConnectionError: Cannot connect to RPC', fix: 'Public Sepolia RPC is rate-limited. Set a private RPC_URL in .env (e.g. Infura, Alchemy).' },
]

const ADDRESSES = [
  { name: 'AgentRegistry',      address: '0xcD5954121BbE13a4867c2Df886e24E924D006883' },
  { name: 'IntentRegistry',     address: '0xf2a52EAf8E2440F9aFa28aDA5426Bc2908DDc5b4' },
  { name: 'DelegationRegistry', address: '0x51bF1E9C33ACF135E7C6ca83AD4Cf36d5B8BBa45' },
  { name: 'ExecutionGate',      address: '0x076e8cd66be8B927CcB9adA63505e8027b209cb6' },
]

/* ── Section building blocks ──────────────────────────────────── */
function DgSection({ num, label, title, children, mono }) {
  return (
    <div className="dg-section">
      <div className="dg-section__hd">
        <span className="dg-section__num">{num}</span>
        <span className="dg-section__lbl">{label}</span>
      </div>
      <h3 className={`dg-section__title${mono ? ' mono' : ''}`}>{title}</h3>
      {children}
    </div>
  )
}

function MethodList({ methods }) {
  return (
    <div className="dg-methods">
      {methods.map((m, i) => (
        <div key={i} className="dg-method">
          <div className="dg-method__sig">{m.sig}</div>
          <div className="dg-method__desc">{m.desc}</div>
        </div>
      ))}
    </div>
  )
}

function ExportTable({ items }) {
  return (
    <div className="dg-export-table">
      {items.map((item, i) => (
        <div key={i} className="dg-export-row">
          <span className="dg-export-row__name">{item.name}</span>
          <span className={`dg-export-row__type dg-export-row__type--${item.type}`}>{item.type}</span>
          <span className="dg-export-row__desc">{item.desc}</span>
        </div>
      ))}
    </div>
  )
}

/* ── Tab content ─────────────────────────────────────────────── */
function PythonContent() {
  return (
    <div className="dg-tab-content">
      <DgSection num="01" label="Installation" title="pip install proof-of-intent" mono>
        <pre className="code-panel"><code>{PY_INSTALL}</code></pre>
      </DgSection>

      <DgSection num="02" label="Environment Variables" title="Env Setup">
        <pre className="code-panel"><code>{PY_ENV}</code></pre>
        <div className="dg-env-table">
          {[
            { v: 'PRIVATE_KEY',    req: 'required', note: 'Ethereum wallet private key (0x…)' },
            { v: 'CLAUDE_API_KEY', req: 'optional', note: 'Only for compile_intent() — ignored if blank' },
            { v: 'ZG_API_KEY',     req: 'optional', note: '0G storage key — protocol works without it' },
            { v: 'RPC_URL',        req: 'optional', note: 'Default: ethereum-sepolia-rpc.publicnode.com' },
            { v: 'CHAIN_ID',       req: 'optional', note: 'Default: 11155111 (Sepolia)' },
          ].map((r) => (
            <div key={r.v} className="dg-env-row">
              <span className="dg-env-row__var">{r.v}</span>
              <span className={`dg-env-row__req dg-env-row__req--${r.req}`}>{r.req}</span>
              <span className="dg-env-row__note">{r.note}</span>
            </div>
          ))}
        </div>
      </DgSection>

      <DgSection num="03" label="Exports" title="What you can import">
        <ExportTable items={PY_EXPORTS} />
      </DgSection>

      <DgSection num="04" label="Token & Time Helpers" title="Amount Conversions">
        <pre className="code-panel"><code>{PY_HELPERS}</code></pre>
      </DgSection>

      <DgSection num="05" label="ContractClient API" title="All Methods">
        <MethodList methods={PY_METHODS} />
      </DgSection>

      <DgSection num="06" label="Quickstart" title="5-Step Example">
        <pre className="code-panel"><code>{PY_QUICKSTART}</code></pre>
      </DgSection>

      <DgSection num="07" label="Error Handling" title="Exception Hierarchy">
        <pre className="code-panel"><code>{PY_ERRORS_CODE}</code></pre>
      </DgSection>

      <DgSection num="08" label="Natural Language Compiler" title="Plain English → Intent">
        <div className="dg-info-box">
          <div className="dg-info-box__label">Optional feature</div>
          <p>
            <code>compile_intent()</code> wraps Claude (or OpenAI) to convert a plain English
            sentence into the structured dict that <code>build_intent()</code> expects.
            Requires <code>CLAUDE_API_KEY</code> and <code>proof-of-intent[ai]</code>.
          </p>
        </div>
        <pre className="code-panel"><code>{PY_COMPILER}</code></pre>
      </DgSection>
    </div>
  )
}

function TypeScriptContent() {
  return (
    <div className="dg-tab-content">
      <DgSection num="01" label="Installation" title="npm i proof-of-intent" mono>
        <pre className="code-panel"><code>{TS_INSTALL}</code></pre>
      </DgSection>

      <DgSection num="02" label="Environment Variables" title="Env Setup">
        <pre className="code-panel"><code>{TS_ENV}</code></pre>
        <div className="dg-env-table">
          {[
            { v: 'PRIVATE_KEY',    req: 'required', note: 'Ethereum wallet private key (0x…)' },
            { v: 'CLAUDE_API_KEY', req: 'optional', note: 'For compileIntent() — ignored if blank' },
            { v: 'ZG_API_KEY',     req: 'optional', note: '0G storage key — protocol works without it' },
            { v: 'ZG_RPC_URL',     req: 'optional', note: 'Default: evmrpc-testnet.0g.ai' },
            { v: 'ZG_INDEXER_URL', req: 'optional', note: 'Default: indexer-storage-testnet-turbo.0g.ai' },
            { v: 'RPC_URL',        req: 'optional', note: 'Default: ethereum-sepolia-rpc.publicnode.com' },
            { v: 'CHAIN_ID',       req: 'optional', note: 'Default: 11155111 (Sepolia)' },
          ].map((r) => (
            <div key={r.v} className="dg-env-row">
              <span className="dg-env-row__var">{r.v}</span>
              <span className={`dg-env-row__req dg-env-row__req--${r.req}`}>{r.req}</span>
              <span className="dg-env-row__note">{r.note}</span>
            </div>
          ))}
        </div>
      </DgSection>

      <DgSection num="03" label="Exports" title="What you can import">
        <ExportTable items={TS_EXPORTS} />
      </DgSection>

      <DgSection num="04" label="ContractClient API" title="All Methods">
        <MethodList methods={TS_METHODS} />
      </DgSection>

      <DgSection num="05" label="Quickstart" title="5-Step Example">
        <pre className="code-panel"><code>{TS_QUICKSTART}</code></pre>
      </DgSection>

      <DgSection num="06" label="Protocol Name Hashing" title="Critical: bytes32 vs string">
        <div className="dg-info-box dg-info-box--warn">
          <div className="dg-info-box__label">Common footgun</div>
          <p>
            <code>buildIntent()</code> and <code>buildScope()</code> hash protocol names automatically.
            But <code>txParams.protocol</code> is a raw <code>bytes32</code> field — always pass
            the exported constant, never the string.
          </p>
        </div>
        <pre className="code-panel"><code>{TS_PROTOCOL}</code></pre>
      </DgSection>
    </div>
  )
}

/* ── Shared sections ─────────────────────────────────────────── */
function CommonErrors() {
  return (
    <div className="dg-shared-section">
      <div className="dg-shared-section__hd">
        <span className="sec-label">Error Reference</span>
        <h2 className="dg-shared-title">WHAT BREAKS AND WHY</h2>
        <p className="dg-shared-sub">
          All revert strings are deterministic — the same error means the same thing every time.
        </p>
      </div>
      <div className="dg-error-list">
        {COMMON_ERRORS.map((e) => (
          <div key={e.code} className="dg-error-row">
            <div className="dg-error-row__code">"{e.code}"</div>
            <div className="dg-error-row__fix">{e.fix}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ContractAddresses() {
  const [copied, setCopied] = useState(null)
  const copy = (addr) => {
    navigator.clipboard.writeText(addr).catch(() => {})
    setCopied(addr)
    setTimeout(() => setCopied(null), 1400)
  }
  return (
    <div className="dg-shared-section">
      <div className="dg-shared-section__hd">
        <span className="sec-label">Contract Addresses</span>
        <h2 className="dg-shared-title">ETHEREUM SEPOLIA</h2>
        <p className="dg-shared-sub">
          Both SDKs have these hardcoded as defaults — no config needed.
          Network: Sepolia · chainId 11155111.
        </p>
      </div>
      <div className="dg-addr-grid">
        {ADDRESSES.map((a) => (
          <div key={a.name} className="dg-addr-card">
            <div className="dg-addr-card__name">{a.name}</div>
            <div className="dg-addr-card__row">
              <span className="dg-addr-card__addr">{a.address}</span>
              <button
                className="dg-addr-card__copy"
                onClick={() => copy(a.address)}
                title="Copy address"
              >
                {copied === a.address ? '✓' : '⎘'}
              </button>
            </div>
            <a
              className="dg-addr-card__link"
              href={`https://sepolia.etherscan.io/address/${a.address}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              View on Etherscan ↗
            </a>
          </div>
        ))}
      </div>
    </div>
  )
}

function PipelineSection() {
  return (
    <div className="dg-shared-section">
      <div className="dg-shared-section__hd">
        <span className="sec-label">Full Pipeline</span>
        <h2 className="dg-shared-title">RUNNING WITH AXL</h2>
        <p className="dg-shared-sub">
          The Python multi-agent pipeline uses AXL — a local P2P mesh — for
          inter-agent messaging. Each agent runs in its own terminal.
          The TypeScript demo runs all agents as child processes automatically.
        </p>
      </div>

      <div className="dg-pipeline-steps">
        {[
          { n: '01', title: 'Start AXL Nodes', desc: 'Three nodes form a Yggdrasil mesh. Must run from project root.' },
          { n: '02', title: 'Start Agents', desc: 'Execution → Research → Orchestrator (order matters for clean startup).' },
          { n: '03', title: 'Observe Flow', desc: 'Orchestrator sends TASK → Research sub-delegates → Execution verifies and swaps → COMPLETE.' },
        ].map((s) => (
          <div key={s.n} className="dg-pipeline-step">
            <div className="dg-pipeline-step__num">{s.n}</div>
            <div>
              <div className="dg-pipeline-step__title">{s.title}</div>
              <div className="dg-pipeline-step__desc">{s.desc}</div>
            </div>
          </div>
        ))}
      </div>

      <pre className="code-panel" style={{ marginTop: 24 }}><code>{AXL_PIPELINE}</code></pre>

      <div className="dg-info-box" style={{ marginTop: 20 }}>
        <div className="dg-info-box__label">TypeScript demo</div>
        <p>
          The TypeScript version (<code>agents/demo_app/</code>) runs all four agents
          as child processes with a single command: <code>npm run demo</code>.
          No separate AXL node startup needed — it handles everything automatically.
        </p>
      </div>
    </div>
  )
}

/* ── Main export ─────────────────────────────────────────────── */
export default function DevGuide({ navigate }) {
  const [tab, setTab] = useState('python')

  return (
    <div className="dg-page">
      {/* ── Header ── */}
      <div className="dg-header">
        <div className="dg-header__grid" />
        <div className="wrap">
          <button className="dg-back" onClick={() => navigate('home')}>
            ← Back to Protocol
          </button>

          <div className="dg-header__inner">
            <span className="sec-label">Developer Guide</span>
            <h1 className="dg-title">FULL SDK<br />REFERENCE</h1>
            <p className="dg-subtitle">
              Everything you need to integrate Proof of Intent Protocol into your agent pipeline.
              Both SDKs target Ethereum Sepolia with hardcoded contract defaults — no config files required.
            </p>
          </div>

          {/* ── Tab bar ── */}
          <div className="dg-tabbar">
            <button
              className={`dg-tab${tab === 'python' ? ' active' : ''}`}
              onClick={() => setTab('python')}
            >
              <span className="dg-tab__icon">🐍</span>
              <div className="dg-tab__text">
                <span className="dg-tab__lang">Python SDK</span>
                <span className="dg-tab__install">pip install proof-of-intent</span>
              </div>
            </button>
            <button
              className={`dg-tab${tab === 'typescript' ? ' active' : ''}`}
              onClick={() => setTab('typescript')}
            >
              <span className="dg-tab__icon">𝚃𝚂</span>
              <div className="dg-tab__text">
                <span className="dg-tab__lang">TypeScript SDK</span>
                <span className="dg-tab__install">npm i proof-of-intent</span>
              </div>
            </button>
          </div>
        </div>
      </div>

      {/* ── Tab body ── */}
      <div className="dg-body">
        <div className="wrap">
          {tab === 'python' ? <PythonContent /> : <TypeScriptContent />}
        </div>
      </div>

      {/* ── Shared sections ── */}
      <div className="dg-shared">
        <div className="wrap">
          <CommonErrors />
          <ContractAddresses />
          <PipelineSection />
        </div>
      </div>
    </div>
  )
}
