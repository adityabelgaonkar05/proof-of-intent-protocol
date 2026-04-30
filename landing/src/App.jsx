import { useState, useEffect, useRef, useCallback } from 'react'

/* ─── helpers ─── */
const delay = (ms) => new Promise((r) => setTimeout(r, ms))

function useReveal() {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect() } },
      { threshold: 0.08 }
    )
    if (ref.current) obs.observe(ref.current)
    return () => obs.disconnect()
  }, [])
  return [ref, visible]
}

function useCountUp(target, duration, started) {
  const [count, setCount] = useState(0)
  const rafRef = useRef(null)
  useEffect(() => {
    if (!started) return
    let t0 = null
    const step = (ts) => {
      if (!t0) t0 = ts
      const p = Math.min((ts - t0) / duration, 1)
      const e = 1 - Math.pow(1 - p, 3)
      setCount(Math.round(e * target))
      if (p < 1) rafRef.current = requestAnimationFrame(step)
    }
    rafRef.current = requestAnimationFrame(step)
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [target, duration, started])
  return count
}

/* ================================================================
   NAV
================================================================= */
function Nav() {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 48)
    window.addEventListener('scroll', h, { passive: true })
    return () => window.removeEventListener('scroll', h)
  }, [])
  return (
    <nav className={`nav${scrolled ? ' scrolled' : ''}`}>
      <div className="nav__brand">
        <span className="nav__pip">PIP</span>
        <span className="nav__full">Proof of Intent Protocol</span>
      </div>
      <div className="nav__links">
        <a href="#mechanism">Protocol</a>
        <a href="#build">Build</a>
        <a href="#demo">Demo</a>
        <a href="#stack">Stack</a>
        <a
          href="https://sepolia.etherscan.io/address/0x98d9ccA9b5F8abACB4c8BEC833C4ed206DC77954"
          target="_blank"
          rel="noopener noreferrer"
          className="nav__cta"
        >
          Audit Contracts ↗
        </a>
      </div>
    </nav>
  )
}

/* ================================================================
   HERO
================================================================= */
function Hero() {
  return (
    <section id="hero" className="hero">
      <div className="hero__grid" />
      <div className="hero__scan" />
      <div className="hero__glow" />
      <div className="hero__glow2" />

      <div className="hero__inner">
        <div className="hero__badge">
          <span className="dot dot--live" />
          Live on Ethereum Sepolia · 4 contracts deployed
        </div>

        <h1 className="hero__h1">
          YOUR AI AGENTS<br />
          WON'T SPEND<br />
          A CENT MORE<br />
          <em>THAN YOU SIGNED.</em>
        </h1>

        <p className="hero__sub">
          <strong>Users sign cryptographic intents.</strong> Orchestrators delegate within bounds.
          Execution agents narrow scope step by step. ExecutionGate enforces the full chain
          on-chain — no scope creep, no unauthorized delegation, no capital drift.
        </p>

        <div className="hero__ctas">
          <a href="#mechanism" className="btn btn--primary">Read the Protocol</a>
          <a href="#demo" className="btn btn--outline">Run the Demo</a>
        </div>

        <div className="hero__install">
          <div className="install-block">
            <span className="install-block__lang">Python</span>
            <code>$ <span>pip install -r requirements.txt</span></code>
          </div>
          <div className="install-block">
            <span className="install-block__lang">TypeScript</span>
            <code>$ <span>npm install intent-custody ethers</span></code>
          </div>
        </div>

        <div className="hero__chips">
          <div className="chip">
            <span className="chip__fn">buildIntent</span>
            <span className="chip__args">(token, maxAmount, protocols[], deadline)</span>
          </div>
          <div className="chip">
            <span className="chip__fn">signIntent</span>
            <span className="chip__args">(intent, privateKey, config)</span>
          </div>
          <div className="chip">
            <span className="chip__fn">delegateFromRoot</span>
            <span className="chip__args">(intentId, scope, agentAddr)</span>
          </div>
          <div className="chip">
            <span className="chip__fn">executeSwap</span>
            <span className="chip__args">(delegationId, txParams)</span>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ================================================================
   STATS BAR
================================================================= */
function StatItem({ value, label, prefix = '', suffix = '' }) {
  const [started, setStarted] = useState(false)
  const ref = useRef(null)
  const count = useCountUp(value, 1900, started)

  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setStarted(true); obs.disconnect() } },
      { threshold: 0.5 }
    )
    if (ref.current) obs.observe(ref.current)
    return () => obs.disconnect()
  }, [])

  return (
    <div className="stat-item" ref={ref}>
      <div className="stat-item__val">{prefix}{count.toLocaleString()}{suffix}</div>
      <div className="stat-item__lbl">{label}</div>
    </div>
  )
}

function StatsBar() {
  return (
    <section id="stats" className="stats">
      <div className="stats__inner">
        <div className="stats__eyebrow">
          <span className="dot dot--live" style={{ background: 'rgba(0,0,0,0.4)' }} />
          Sepolia Testnet · Live contract data
        </div>
        <div className="stats__grid">
          <StatItem value={47}    label="Intents Registered" />
          <StatItem value={124}   label="Delegations Created" />
          <StatItem value={18}    label="Attacks Blocked" />
          <StatItem value={14400} label="USDC Protected" prefix="$" />
        </div>
        <div className="stats__note">
          ↗ Every counter verifiable on-chain via Etherscan Sepolia
        </div>
      </div>
    </section>
  )
}

/* ================================================================
   HOW IT WORKS
================================================================= */
function HowItWorks() {
  const [ref, vis] = useReveal()
  return (
    <section id="mechanism" className="hiw">
      <div className="wrap">
        <div className={`sec-head reveal${vis ? ' visible' : ''}`} ref={ref}>
          <span className="sec-label">02 / Mechanism</span>
          <h2 className="sec-title">SIGN → DELEGATE → ENFORCE</h2>
          <p className="sec-sub">
            Three deterministic steps. No human in the loop after signing.
            Every constraint enforced at the contract layer.
          </p>
        </div>

        <div className="hiw__cards">
          <div className="hiw-card">
            <div className="hiw-card__num">01 / SIGN</div>
            <span className="hiw-card__glyph">◈</span>
            <h3 className="hiw-card__title">SIGN</h3>
            <p className="hiw-card__desc">
              User constructs an EIP-712 structured intent specifying token,
              maximum amount in, minimum amount out, a whitelist of allowed
              protocols, a deadline, and the authorized orchestrator address.
              The signature binds every parameter. No execution is possible
              without a valid signature from the intent owner.
            </p>
            <div className="hiw-card__code">
              <code>buildIntent(USDC, 500e6, [UNISWAP_V3], +1h)</code>
              <code>signIntent(intent, userKey, config)</code>
              <code>registerIntent(intent, sig) → intentId</code>
            </div>
            <div className="hiw-card__arrow">→</div>
          </div>

          <div className="hiw-card">
            <div className="hiw-card__num">02 / DELEGATE</div>
            <span className="hiw-card__glyph">⬡</span>
            <h3 className="hiw-card__title">DELEGATE</h3>
            <p className="hiw-card__desc">
              The authorized orchestrator creates a root delegation to a
              registered research agent. That agent narrows the scope further
              and sub-delegates to an execution agent. Each hop can only
              tighten constraints — the child scope must be a strict subset
              of the parent. DelegationRegistry enforces this algebraically.
            </p>
            <div className="hiw-card__code">
              <code>delegateFromRoot(intentId, scope₁, agentA)</code>
              <code>delegateFromDelegation(delId, scope₂, agentB)</code>
              <code><em>// scope₂ ⊆ scope₁ ⊆ intent — enforced on-chain</em></code>
            </div>
            <div className="hiw-card__arrow">→</div>
          </div>

          <div className="hiw-card">
            <div className="hiw-card__num">03 / ENFORCE</div>
            <span className="hiw-card__glyph">✦</span>
            <h3 className="hiw-card__title">ENFORCE</h3>
            <p className="hiw-card__desc">
              ExecutionGate walks the full delegation chain before any token
              moves. It checks every scope constraint against the root intent:
              token, amount, minimum output, allowed protocols, and deadline.
              Any violation — wrong token, exceeded amount, disallowed DEX —
              reverts the entire transaction atomically.
            </p>
            <div className="hiw-card__code">
              <code>verifyChain(delegationId, txParams) → bool</code>
              <code>executeSwap(delegationId, txParams)</code>
              <code><em>// full revert on any constraint violation</em></code>
            </div>
          </div>
        </div>

        <div className="hiw__pipeline">
          <div className="pipeline">
            <div className="pipe-node">USER</div>
            <div className="pipe-edge" />
            <div className="pipe-node">ORCHESTRATOR</div>
            <div className="pipe-edge" />
            <div className="pipe-node">RESEARCH AGENT</div>
            <div className="pipe-edge" />
            <div className="pipe-node pipe-node--gate">EXECUTION GATE</div>
            <div className="pipe-edge" />
            <div className="pipe-node pipe-node--exec">UNISWAP V3</div>
          </div>
          <div className="pipe-labels">
            <span>signs intent</span>
            <span>root delegation</span>
            <span>narrows scope</span>
            <span>verifies chain</span>
            <span>atomic swap</span>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ================================================================
   GET STARTED
================================================================= */
const PY_CODE = `from utils.sign_intent import build_intent, sign_intent
from utils.contract_client import ContractClient
import time

# 1. Build and sign the intent
intent = build_intent(
    token_in=USDC_ADDRESS,
    max_amount_in=500_000_000,        # 500 USDC (6 decimals)
    min_amount_out=140_000_000_000_000_000,  # 0.14 WETH
    protocols=["uniswap-v3"],
    deadline=int(time.time()) + 3600,
    authorized_orchestrator=ORCH_ADDRESS,
)
sig = sign_intent(intent, USER_PRIVATE_KEY)

# 2. Register on-chain
client = ContractClient(config)
intent_id = await client.register_intent(intent, sig)
# → 0x3f2a...bytes32

# 3. Orchestrator delegates to research agent
delegation_id = await client.delegate_from_root(
    intent_id,
    scope={"max_amount_in": 500_000_000, "protocols": ["uniswap-v3"]},
    delegate_to=RESEARCH_AGENT_ADDRESS,
)

# 4. Research agent narrows scope and sub-delegates
sub_id = await client.delegate_from_delegation(
    delegation_id,
    scope={"max_amount_in": 400_000_000},  # narrowed from 500
    delegate_to=EXECUTION_AGENT_ADDRESS,
)

# 5. Execution agent executes within bounds
await client.execute_swap(sub_id, tx_params)
`

const TS_CODE = `import { buildIntent, signIntent, ContractClient } from 'intent-custody'

// 1. Build and sign
const intent = buildIntent({
  tokenIn:               USDC_ADDRESS,
  maxAmountIn:           500_000_000n,
  minAmountOut:          140_000_000_000_000_000n,
  allowedProtocols:      ['uniswap-v3'],
  deadline:              Math.floor(Date.now() / 1000) + 3600,
  authorizedOrchestrator: ORCH_ADDRESS,
})
const sig = await signIntent(intent, userKey, config)

// 2. Register on-chain
const client = new ContractClient(config)
const intentId = await client.registerIntent(intent, sig)
// → 0x3f2a...bytes32

// 3. Orchestrator delegates to research agent
const delegationId = await client.delegateFromRoot(
  intentId,
  { maxAmountIn: 500_000_000n, allowedProtocols: ['uniswap-v3'] },
  researchAgentAddress,
)

// 4. Research agent narrows scope
const subId = await client.delegateFromDelegation(
  delegationId,
  { maxAmountIn: 400_000_000n },  // narrowed from 500
  executionAgentAddress,
)

// 5. Execute within bounds
await client.executeSwap(subId, txParams)
`

const API_METHODS = [
  { name: 'buildIntent', sig: '(params: IntentParams) → IntentData', desc: 'Construct an intent struct with auto-hashed protocol names and validated defaults.' },
  { name: 'signIntent',  sig: '(intent, privateKey, config) → Promise<string>', desc: 'EIP-712 sign an intent against the IntentRegistry domain. Returns a hex signature.' },
  { name: 'registerIntent', sig: '(intent, signature) → Promise<string>', desc: 'Submit signed intent to IntentRegistry on-chain. Returns intentId (bytes32).' },
  { name: 'delegateFromRoot', sig: '(intentId, scope, delegateTo) → Promise<string>', desc: 'Authorized orchestrator creates the root delegation for an intent. Returns delegationId.' },
  { name: 'delegateFromDelegation', sig: '(parentId, scope, delegateTo) → Promise<string>', desc: 'Agent sub-delegates to the next agent with a strictly narrowed scope.' },
  { name: 'verifyChain', sig: '(delegationId, txParams) → Promise<boolean>', desc: 'Read-only walk of the full delegation chain against proposed tx parameters. No gas.' },
  { name: 'executeSwap', sig: '(delegationId, txParams) → Promise<string>', desc: 'Execute Uniswap V3 swap. ExecutionGate verifies the full chain atomically before any tokens move.' },
]

const ERRORS = [
  { code: 'Already registered',       desc: 'Agent address is already in AgentRegistry. Each address can only register once.' },
  { code: 'Zero address',             desc: 'A zero address was passed where a valid agent or orchestrator address was required.' },
  { code: 'Not owner',                desc: 'Caller is not the intent owner. Only the original signer can revoke or manage their intent.' },
  { code: 'Deadline passed',          desc: 'The intent or scope deadline is in the past. Create a new intent with a valid future deadline.' },
  { code: 'Zero amount',              desc: 'maxAmountIn was zero. The intent must specify a positive token amount.' },
  { code: 'No orchestrator set',      desc: 'The intent has no authorizedOrchestrator. An orchestrator address is required at registration.' },
  { code: 'Invalid signature',        desc: 'EIP-712 signature does not match the intent owner. The intent data or signing key is wrong.' },
  { code: 'Intent not found',         desc: 'No intent exists for the provided intentId. Verify the ID was returned from registerIntent.' },
  { code: 'Not authorized orchestrator', desc: 'Caller is not the orchestrator named in the intent. Only the named orchestrator can create a root delegation.' },
  { code: 'Target not registered agent', desc: 'The delegateTo address is not in AgentRegistry. Agents must self-register before receiving delegations.' },
  { code: 'Amount exceeds root',      desc: 'Child scope maxAmountIn is larger than the root intent. Scope can only narrow — never widen.' },
  { code: 'MinOut below root',        desc: 'Child scope minAmountOut is below the root floor. The protocol prevents accepting worse slippage than the user signed.' },
  { code: 'Deadline exceeds root',    desc: 'Child scope deadline is later than the root intent. Delegations cannot extend the user\'s authorized window.' },
  { code: 'Protocols not subset',     desc: 'The child scope includes a protocol not in the parent allowlist. Agents can only use a subset of parent-approved protocols.' },
  { code: 'Root already delegated',   desc: 'A root delegation already exists for this intent. Each intent produces exactly one root delegation.' },
  { code: 'Parent not found',         desc: 'The parent delegationId does not exist. Verify the ID returned from delegateFromRoot.' },
  { code: 'Not delegated agent',      desc: 'Caller is not the agent the parent delegation was assigned to. Only the named agent can sub-delegate.' },
  { code: 'Already executed',         desc: 'This delegation has already been used for a swap. Each delegation can trigger exactly one execution.' },
  { code: 'Amount exceeds scope',     desc: 'Requested amountIn exceeds the delegation scope. ExecutionGate blocked the transaction before any tokens moved.' },
  { code: 'MinOut below scope',       desc: 'Requested minAmountOut is below the scope floor. The agent attempted to accept worse slippage than authorized.' },
  { code: 'Deadline exceeds scope',   desc: 'Execution timestamp is beyond the scope deadline. The delegation window has closed.' },
  { code: 'Already sub-delegated',    desc: 'This delegation has already produced a child. Each delegation can be sub-delegated exactly once.' },
  { code: 'Not execution gate',       desc: 'Caller is not the registered ExecutionGate. Only ExecutionGate can mark delegations as executed.' },
  { code: 'Protocol not allowed',     desc: 'The swap protocol is not in the delegation\'s allowedProtocols list. Agent tried to use an unauthorized DEX.' },
  { code: 'Exceeds root intent',      desc: 'Transaction amount exceeds the original root intent. ExecutionGate catches this even if intermediate delegations passed.' },
  { code: 'Wrong token',              desc: 'tokenIn does not match the root intent. Agent tried to swap a different asset than the user authorized.' },
  { code: 'Root deadline passed',     desc: 'Root intent deadline has expired even if the delegation deadline has not. The original authorization window is closed.' },
  { code: 'Not authorized',           desc: 'Caller is not the agent assigned to this delegation. Only the delegated-to address can execute.' },
  { code: 'Chain verification failed', desc: 'One or more nodes in the delegation chain failed validation. The full path from intent to execution is checked.' },
]

function GetStarted() {
  const [codeTab, setCodeTab] = useState('python')
  const [docTab, setDocTab] = useState('api')
  const [ref, vis] = useReveal()

  return (
    <section id="build" className="gs">
      <div className="wrap">
        <div className={`sec-head reveal${vis ? ' visible' : ''}`} ref={ref}>
          <span className="sec-label">03 / Build</span>
          <h2 className="sec-title">GET STARTED</h2>
        </div>

        <div className="gs__layout">
          {/* ── LEFT ── */}
          <div>
            <h3 className="gs__col-title">TRADING BOT: BEFORE & AFTER</h3>
            <div className="ba">
              <div className="ba__col ba__col--before">
                <div className="ba__lbl">Before · Uncontrolled Agent</div>
                <div className="ba__row"><span className="ba__icon">✗</span>Agent spends 2,400 USDC — user wanted 500</div>
                <div className="ba__row"><span className="ba__icon">✗</span>Uses Curve instead of authorized Uniswap V3</div>
                <div className="ba__row"><span className="ba__icon">✗</span>Deadline ignored; executes 3 hours late</div>
                <div className="ba__row"><span className="ba__icon">✗</span>No audit trail, no on-chain proof, no recourse</div>
              </div>
              <div className="ba__col ba__col--after">
                <div className="ba__lbl">After · Proof of Intent</div>
                <div className="ba__row"><span className="ba__icon">✓</span>500 USDC hard cap enforced at ExecutionGate</div>
                <div className="ba__row"><span className="ba__icon">✓</span>Protocol list is a signed, immutable subset</div>
                <div className="ba__row"><span className="ba__icon">✓</span>Deadline checked at every delegation layer</div>
                <div className="ba__row"><span className="ba__icon">✓</span>Full delegation chain verifiable on Sepolia</div>
              </div>
            </div>

            <h3 className="gs__col-title" style={{ marginBottom: 16 }}>QUICKSTART</h3>
            <div className="tabs">
              <button className={`tab-btn${codeTab === 'python' ? ' active' : ''}`} onClick={() => setCodeTab('python')}>Python</button>
              <button className={`tab-btn${codeTab === 'typescript' ? ' active' : ''}`} onClick={() => setCodeTab('typescript')}>TypeScript</button>
            </div>
            <pre className="code-panel"><code>{codeTab === 'python' ? PY_CODE : TS_CODE}</code></pre>
          </div>

          {/* ── RIGHT ── */}
          <div>
            <h3 className="gs__col-title" style={{ marginBottom: 16 }}>REFERENCE</h3>
            <div className="tabs">
              <button className={`tab-btn${docTab === 'api' ? ' active' : ''}`} onClick={() => setDocTab('api')}>API Reference</button>
              <button className={`tab-btn${docTab === 'errors' ? ' active' : ''}`} onClick={() => setDocTab('errors')}>Error Reference</button>
            </div>
            <div className="docs-panel docs-panel--scroll">
              {docTab === 'api'
                ? API_METHODS.map((m) => (
                    <div key={m.name} className="api-row">
                      <div className="api-row__name">{m.name}</div>
                      <div className="api-row__sig">{m.sig}</div>
                      <div className="api-row__desc">{m.desc}</div>
                    </div>
                  ))
                : ERRORS.map((e) => (
                    <div key={e.code} className="err-row">
                      <div className="err-row__code">"{e.code}"</div>
                      <div className="err-row__desc">{e.desc}</div>
                    </div>
                  ))
              }
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ================================================================
   LIVE DEMO
================================================================= */
const NODES = [
  { label: 'USER',           sub: 'Signs intent' },
  { label: 'ORCHESTRATOR',   sub: 'Root delegation' },
  { label: 'RESEARCH AGENT', sub: 'Narrows scope' },
  { label: 'EXECUTION GATE', sub: 'Verifies chain' },
]

function LiveDemo() {
  const [phase, setPhase]       = useState('idle')   // idle|running|blocked|done
  const [active, setActive]     = useState(-1)
  const [scope, setScope]       = useState(500)
  const [risk, setRisk]         = useState(500)
  const [attackAmt, setAttack]  = useState(null)
  const [glitch, setGlitch]     = useState(false)
  const [edgeActive, setEdge]   = useState([false, false, false])
  const [ref, vis] = useReveal()

  const activateEdge = (i) =>
    setEdge((prev) => { const n = [...prev]; n[i] = true; return n })

  const runClean = useCallback(async () => {
    setPhase('running'); setActive(-1); setScope(500); setRisk(500)
    setAttack(null); setGlitch(false); setEdge([false, false, false])

    setActive(0); await delay(700)
    activateEdge(0); await delay(400)
    setActive(1); setScope(500); await delay(700)
    activateEdge(1); await delay(400)
    setActive(2); setScope(400); setRisk(400); await delay(700)
    activateEdge(2); await delay(400)
    setActive(3); setScope(300); setRisk(300); await delay(700)
    setPhase('done')
  }, [])

  const runAttack = useCallback(async () => {
    setPhase('running'); setActive(-1); setScope(500); setRisk(500)
    setAttack(null); setGlitch(false); setEdge([false, false, false])

    setActive(0); await delay(700)
    activateEdge(0); await delay(400)
    setActive(1); await delay(700)
    activateEdge(1); await delay(400)
    setActive(2); setAttack(800); await delay(600)
    setGlitch(true); await delay(1100)
    setGlitch(false); setPhase('blocked'); setRisk(0)
  }, [])

  const reset = () => {
    setPhase('idle'); setActive(-1); setScope(500); setRisk(500)
    setAttack(null); setGlitch(false); setEdge([false, false, false])
  }

  return (
    <section id="demo" className="demo-sec">
      <div className="wrap">
        <div className={`sec-head reveal${vis ? ' visible' : ''}`} ref={ref}>
          <span className="sec-label">04 / Simulation</span>
          <h2 className="sec-title">LIVE DEMO</h2>
          <p className="sec-sub">
            Two paths. One outcome: out-of-scope attacks are rejected atomically.
            No funds move. The chain reverts.
          </p>
        </div>

        <div className={`demo-panel${glitch ? ' glitching' : ''}`}>
          {/* header bar */}
          <div className="demo-panel__hd">
            <div className="demo-status">
              <span className={`dot dot--${phase === 'blocked' ? 'red' : phase === 'done' ? 'green' : 'live'}`} />
              {phase === 'idle'    && 'READY · AWAITING INPUT'}
              {phase === 'running' && (attackAmt ? 'ATTACK SIMULATION · ACTIVE' : 'CLEAN RUN · ACTIVE')}
              {phase === 'blocked' && 'ATTACK BLOCKED · REVERTED ON-CHAIN'}
              {phase === 'done'    && 'CLEAN RUN · SWAP EXECUTED SUCCESSFULLY'}
            </div>
            <div className="demo-metrics">
              <div className="demo-metric">
                <span className="demo-metric__lbl">Scope ceiling</span>
                <span className="demo-metric__val">{scope} USDC</span>
              </div>
              <div className="demo-metric">
                <span className="demo-metric__lbl">Funds at risk</span>
                <span className={`demo-metric__val${risk === 0 ? ' demo-metric__val--safe' : ''}`}>
                  ${risk.toLocaleString()}
                </span>
              </div>
              {attackAmt && (
                <div className="demo-metric">
                  <span className="demo-metric__lbl">Attempted</span>
                  <span className="demo-metric__val demo-metric__val--red">{attackAmt} USDC</span>
                </div>
              )}
            </div>
          </div>

          {/* pipeline */}
          <div className="demo-pipe">
            {NODES.map((node, i) => (
              <div key={i} className="demo-pipe__step">
                <div className={[
                  'demo-node',
                  active >= i && 'active',
                  glitch && i === 2 && 'glitch-node',
                  phase === 'blocked' && i >= 2 && 'blocked',
                  phase === 'done' && i === 3 && 'success',
                ].filter(Boolean).join(' ')}>
                  <div className="demo-node__lbl">{node.label}</div>
                  <div className="demo-node__sub">{node.sub}</div>
                  {i === 0 && active >= 0 && (
                    <div className="demo-node__scope">500 USDC max</div>
                  )}
                  {i === 1 && active >= 1 && (
                    <div className="demo-node__scope">→ delegating 500 USDC</div>
                  )}
                  {i === 2 && active >= 2 && !attackAmt && (
                    <div className="demo-node__scope">→ 400 USDC scope</div>
                  )}
                  {i === 2 && attackAmt && (
                    <div className="demo-node__scope demo-node__scope--attack">→ 800 USDC ✗ EXCEEDS ROOT</div>
                  )}
                  {i === 3 && phase === 'done' && (
                    <div className="demo-node__scope">→ 300 USDC · VERIFIED</div>
                  )}
                </div>
                {i < NODES.length - 1 && (
                  <div className={[
                    'demo-pipe__edge',
                    edgeActive[i] && 'active',
                    glitch && i >= 2 && 'blocked',
                  ].filter(Boolean).join(' ')} />
                )}
              </div>
            ))}
          </div>

          {/* result: blocked */}
          {phase === 'blocked' && (
            <div className="demo-result demo-result--blocked">
              <div className="demo-result__hd">
                <span className="demo-result__icon">⬛</span>
                <span className="demo-result__title">TRANSACTION REVERTED</span>
              </div>
              <div className="demo-result__revert">revert: "Amount exceeds root"</div>
              <p className="demo-result__body">
                Research agent attempted to sub-delegate 800 USDC.
                The root intent authorized a maximum of 500 USDC.
                DelegationRegistry rejected the sub-delegation atomically.
                No tokens were approved, transferred, or swapped.
                Zero funds moved.
              </p>
              <div className="demo-result__badge">ATTACK BLOCKED ON-CHAIN · 0 USDC LOST</div>
            </div>
          )}

          {/* result: success */}
          {phase === 'done' && (
            <div className="demo-result demo-result--success">
              <div className="demo-result__hd">
                <span className="demo-result__icon">✓</span>
                <span className="demo-result__title">SWAP EXECUTED SUCCESSFULLY</span>
              </div>
              <p className="demo-result__body">
                300 USDC swapped for WETH via Uniswap V3 on Ethereum Sepolia.
                ExecutionGate walked the full delegation chain (intent → root delegation
                → sub-delegation) and verified every constraint before allowing
                the swap to proceed. Delegation marked as executed on-chain.
              </p>
              <div className="demo-result__badge">INTENT CUSTODY VERIFIED · CHAIN VALIDATED</div>
              <div className="demo-result__links">
                <a
                  className="etherscan-link"
                  href="https://sepolia.etherscan.io/address/0x98d9ccA9b5F8abACB4c8BEC833C4ed206DC77954"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  View ExecutionGate ↗
                </a>
                <div className="qr-wrap">
                  {/* stylized QR placeholder — links to ExecutionGate on Sepolia */}
                  <a
                    href="https://sepolia.etherscan.io/address/0x98d9ccA9b5F8abACB4c8BEC833C4ed206DC77954"
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Etherscan Sepolia · ExecutionGate"
                  >
                    <svg width="72" height="72" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <rect width="72" height="72" fill="#0d0d0d"/>
                      {/* top-left finder */}
                      <rect x="4" y="4" width="22" height="22" rx="0" fill="none" stroke="#ffe600" strokeWidth="2"/>
                      <rect x="8" y="8" width="14" height="14" fill="#ffe600"/>
                      {/* top-right finder */}
                      <rect x="46" y="4" width="22" height="22" fill="none" stroke="#ffe600" strokeWidth="2"/>
                      <rect x="50" y="8" width="14" height="14" fill="#ffe600"/>
                      {/* bottom-left finder */}
                      <rect x="4" y="46" width="22" height="22" fill="none" stroke="#ffe600" strokeWidth="2"/>
                      <rect x="8" y="50" width="14" height="14" fill="#ffe600"/>
                      {/* data modules */}
                      <rect x="30" y="4" width="4" height="4" fill="#ffe600"/>
                      <rect x="36" y="4" width="4" height="4" fill="#ffe600"/>
                      <rect x="30" y="10" width="4" height="4" fill="#ffe600"/>
                      <rect x="4" y="30" width="4" height="4" fill="#ffe600"/>
                      <rect x="4" y="36" width="4" height="4" fill="#ffe600"/>
                      <rect x="10" y="30" width="4" height="4" fill="#ffe600"/>
                      <rect x="30" y="30" width="4" height="4" fill="#ffe600"/>
                      <rect x="36" y="30" width="4" height="4" fill="#ffe600"/>
                      <rect x="42" y="30" width="4" height="4" fill="#ffe600"/>
                      <rect x="48" y="30" width="4" height="4" fill="#ffe600"/>
                      <rect x="54" y="30" width="4" height="4" fill="#ffe600"/>
                      <rect x="60" y="30" width="4" height="4" fill="#ffe600"/>
                      <rect x="30" y="36" width="4" height="4" fill="#ffe600"/>
                      <rect x="42" y="36" width="4" height="4" fill="#ffe600"/>
                      <rect x="54" y="36" width="4" height="4" fill="#ffe600"/>
                      <rect x="30" y="42" width="4" height="4" fill="#ffe600"/>
                      <rect x="36" y="42" width="4" height="4" fill="#ffe600"/>
                      <rect x="48" y="42" width="4" height="4" fill="#ffe600"/>
                      <rect x="60" y="42" width="4" height="4" fill="#ffe600"/>
                      <rect x="30" y="48" width="4" height="4" fill="#ffe600"/>
                      <rect x="42" y="48" width="4" height="4" fill="#ffe600"/>
                      <rect x="54" y="48" width="4" height="4" fill="#ffe600"/>
                      <rect x="36" y="54" width="4" height="4" fill="#ffe600"/>
                      <rect x="48" y="54" width="4" height="4" fill="#ffe600"/>
                      <rect x="60" y="54" width="4" height="4" fill="#ffe600"/>
                      <rect x="30" y="60" width="4" height="4" fill="#ffe600"/>
                      <rect x="42" y="60" width="4" height="4" fill="#ffe600"/>
                      <rect x="60" y="60" width="4" height="4" fill="#ffe600"/>
                    </svg>
                  </a>
                  <span>SEPOLIA<br/>ETHERSCAN</span>
                </div>
              </div>
            </div>
          )}

          {/* controls */}
          <div className="demo-panel__ft">
            {phase === 'idle' && (
              <>
                <button className="btn btn--primary" onClick={runClean}>Run Clean Path</button>
                <button className="btn btn--danger" onClick={runAttack}>Simulate Attack</button>
              </>
            )}
            {phase === 'running' && (
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
                · · · Executing on-chain
              </span>
            )}
            {(phase === 'blocked' || phase === 'done') && (
              <>
                <button className="btn btn--ghost" onClick={reset}>Reset</button>
                {phase === 'idle' || phase === 'done' ? (
                  <button className="btn btn--danger" onClick={() => { reset(); setTimeout(runAttack, 50) }}>Simulate Attack</button>
                ) : (
                  <button className="btn btn--outline" onClick={() => { reset(); setTimeout(runClean, 50) }}>Run Clean Path</button>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}

/* ================================================================
   BUILT WITH
================================================================= */
const STACK = [
  {
    name: 'FOUNDRY',
    type: 'Contract Testing',
    problem: 'ABI parity between Python web3.py, ethers v6, and Solidity ABIs required deterministic artifact output across all three runtimes without manual transcription.',
    solved: 'forge build generates canonical JSON ABIs consumed by both SDKs and the Python ContractClient. Single source of truth; no manual ABI copying.',
  },
  {
    name: 'ETHERS V6',
    type: 'TypeScript SDK',
    problem: 'EIP-712 signing with nested structs and dynamic arrays requires exact domain encoding. Small field-order differences silently produce invalid signatures that revert on-chain.',
    solved: 'ethers v6 TypedDataEncoder handles the full signing pipeline. Output was tested against web3.py encode_structured_data to guarantee cross-SDK consistency.',
  },
  {
    name: 'WEB3.PY',
    type: 'Python Agents',
    problem: 'Python agents need async contract reads and writes with proper revert reason surfacing. Raw web3 calls swallow revert strings by default.',
    solved: 'ContractClient wraps async call patterns, decodes revert reason strings, and surfaces them directly — matching the error reference exactly.',
  },
  {
    name: 'AXL',
    type: 'Agent Transport',
    problem: 'Orchestrator, research agent, and execution agent must communicate without shared memory — simulating real multi-agent process separation.',
    solved: 'AXL handles agent-to-agent message routing across process boundaries, enabling the demo to mirror production-grade multi-agent separation of concerns.',
  },
  {
    name: 'ENS',
    type: 'Optional Persistence',
    problem: 'Intent metadata needed a human-readable on-chain anchor that survives contract redeployment and is independent of the intentId bytes32.',
    solved: 'ENS text record integration via Ethereum Sepolia Resolver. Non-blocking — the protocol proceeds even if the ENS write fails or the name is not configured.',
  },
  {
    name: '0G NETWORK',
    type: 'Optional Storage',
    problem: 'Full intent payloads are too large for practical on-chain storage. A decentralized alternative is needed without compromising protocol correctness.',
    solved: '0G provides verifiable decentralized storage for raw intent JSON. Upload is non-blocking; all security guarantees hold whether or not 0G is available.',
  },
  {
    name: 'ETHEREUM SEPOLIA',
    type: 'Testnet',
    problem: 'Live testnet verification requires stable Uniswap V3 pool liquidity, reproducible contract addresses, and readable revert reasons surfaced through Etherscan.',
    solved: 'Four contracts deployed at fixed Sepolia addresses. SwapRouter02 provides real Uniswap V3 execution. All transactions independently verifiable via Etherscan.',
  },
]

function BuiltWith() {
  const [ref, vis] = useReveal()
  return (
    <section id="stack" className="bw">
      <div className="wrap">
        <div className={`sec-head reveal${vis ? ' visible' : ''}`} ref={ref}>
          <span className="sec-label">05 / Stack</span>
          <h2 className="sec-title">BUILT WITH</h2>
          <p className="sec-sub">
            Engineering cards. Every dependency chosen because it solved a specific
            problem that nothing else solved the same way.
          </p>
        </div>

        <div className="bw__grid">
          {STACK.map((s) => (
            <div key={s.name} className="stack-card">
              <div className="stack-card__name">{s.name}</div>
              <div className="stack-card__type">{s.type}</div>
              <div className="stack-card__block">
                <span className="stack-card__tag">Problem</span>
                {s.problem}
              </div>
              <div className="stack-card__block">
                <span className="stack-card__tag stack-card__tag--solved">Solved</span>
                {s.solved}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ================================================================
   FOOTER
================================================================= */
function Footer() {
  return (
    <footer className="footer">
      <div className="wrap">
        <div className="footer__inner">
          <div className="footer__brand">Proof of Intent Protocol</div>
          <div className="footer__links">
            <a href="https://github.com" target="_blank" rel="noopener noreferrer">GitHub ↗</a>
            <a href="https://sepolia.etherscan.io/address/0x98d9ccA9b5F8abACB4c8BEC833C4ed206DC77954" target="_blank" rel="noopener noreferrer">ExecutionGate ↗</a>
            <a href="https://sepolia.etherscan.io/address/0xBaAb83d5C2Ef13ac523CEc8989F514F0c4d31A47" target="_blank" rel="noopener noreferrer">IntentRegistry ↗</a>
          </div>
          <div className="footer__stack">
            EIP-712 · Foundry · ethers v6 · Uniswap V3 · Ethereum Sepolia
          </div>
        </div>
        <div className="footer__credit">
          Made by{' '}
          <a href="https://github.com/adityabelgaonkar05" target="_blank" rel="noopener noreferrer">adityabelgaonkar05</a>
          {' '}and{' '}
          <a href="https://github.com/akankshaagroya" target="_blank" rel="noopener noreferrer">akankshaagroya</a>
        </div>
      </div>
    </footer>
  )
}

/* ================================================================
   APP
================================================================= */
export default function App() {
  return (
    <>
      <Nav />
      <Hero />
      <StatsBar />
      <HowItWorks />
      <GetStarted />
      <LiveDemo />
      <BuiltWith />
      <Footer />
    </>
  )
}
