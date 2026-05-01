/**
 * End-to-end integration test for the Proof-of-Intent Protocol.
 *
 * Requires a local Anvil node:
 *     anvil --port 8545
 *
 * Run with:
 *     npm test
 *
 * The test deploys all four contracts plus a MockERC20 and MockSwapRouter from
 * the Foundry build artifacts, registers agents, runs the full delegation-and-
 * execution flow (including real tokenIn transferFrom + router call), then
 * confirms that a scope-exceeding delegation is correctly rejected.
 */

import { ethers, NonceManager } from 'ethers';
import { readFileSync } from 'fs';
import { join } from 'path';

const CHAIN_ID = 31337; // Anvil default
const TOKEN_OUT = '0x0000000000000000000000000000000000000001';

// Anvil default private keys
const DEPLOYER_KEY      = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'; // key #0
const ORCHESTRATOR_KEY  = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'; // key #1
const RESEARCH_KEY      = '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a'; // key #2
const EXECUTION_KEY     = '0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6'; // key #3

const OUT = join(__dirname, '../../contracts/out');

function loadArtifact(contractName: string): { abi: unknown[]; bytecode: string } {
  const raw = JSON.parse(
    readFileSync(join(OUT, `${contractName}.sol`, `${contractName}.json`), 'utf8'),
  ) as { abi: unknown[]; bytecode: { object: string } };
  return { abi: raw.abi, bytecode: raw.bytecode.object };
}

async function deploy(
  wallet: ethers.Signer,
  artifact: { abi: unknown[]; bytecode: string },
  ...args: unknown[]
): Promise<ethers.Contract> {
  const factory = new ethers.ContractFactory(artifact.abi, artifact.bytecode, wallet);
  const contract = await factory.deploy(...args);
  await contract.waitForDeployment();
  return contract as ethers.Contract;
}

function protocolId(name: string): string {
  return ethers.id(name);
}

async function signIntent(
  intent: Record<string, unknown>,
  wallet: ethers.Signer,
  registryAddress: string,
): Promise<string> {
  const domain = {
    name: 'IntentRegistry',
    version: '1',
    chainId: CHAIN_ID,
    verifyingContract: registryAddress,
  };
  const types = {
    Intent: [
      { name: 'owner',                  type: 'address' },
      { name: 'authorizedOrchestrator', type: 'address' },
      { name: 'tokenIn',                type: 'address' },
      { name: 'maxAmountIn',            type: 'uint256' },
      { name: 'minAmountOut',           type: 'uint256' },
      { name: 'allowedProtocols',       type: 'bytes32[]' },
      { name: 'deadline',               type: 'uint256' },
      { name: 'nonce',                  type: 'uint256' },
    ],
  };
  return wallet.signTypedData(domain, types, intent);
}

function parseEventArg(
  receipt: ethers.TransactionReceipt,
  iface: ethers.Interface,
  eventName: string,
  argName: string,
): string {
  for (const log of receipt.logs) {
    try {
      const parsed = iface.parseLog({ topics: [...log.topics], data: log.data });
      if (parsed?.name === eventName) return parsed.args[argName] as string;
    } catch { /* log belongs to a different contract */ }
  }
  throw new Error(`${eventName} event not found in receipt`);
}

async function run(): Promise<void> {
  const provider = new ethers.JsonRpcProvider('http://localhost:8545');
  try {
    await provider.getNetwork();
  } catch {
    throw new Error('Anvil node not reachable at http://localhost:8545');
  }

  // Wrap each wallet in NonceManager so rapid sequential txs get correct nonces
  // without racing against eth_getTransactionCount returning stale values.
  const deployerWallet      = new NonceManager(new ethers.Wallet(DEPLOYER_KEY, provider));
  const orchestratorWallet  = new NonceManager(new ethers.Wallet(ORCHESTRATOR_KEY, provider));
  const researchWallet      = new NonceManager(new ethers.Wallet(RESEARCH_KEY, provider));
  const executionWallet     = new NonceManager(new ethers.Wallet(EXECUTION_KEY, provider));

  // In the Python test, deployer == accounts[0] == user (Anvil key #0)
  const userAddr         = await deployerWallet.getAddress();
  const orchestratorAddr = await orchestratorWallet.getAddress();
  const researchAddr     = await researchWallet.getAddress();
  const executionAddr    = await executionWallet.getAddress();

  console.log(`User:         ${userAddr}`);
  console.log(`Orchestrator: ${orchestratorAddr}`);
  console.log(`Research:     ${researchAddr}`);
  console.log(`Execution:    ${executionAddr}`);

  // ---------------------------------------------------------------------------
  // [1] Deploy contracts
  // ---------------------------------------------------------------------------
  console.log('\n[1] Deploying contracts...');

  const agentArt      = loadArtifact('AgentRegistry');
  const intentArt     = loadArtifact('IntentRegistry');
  const delegArt      = loadArtifact('DelegationRegistry');
  const gateArt       = loadArtifact('ExecutionGate');
  const mockERC20Art  = loadArtifact('MockERC20');
  const mockRouterArt = loadArtifact('MockSwapRouter');

  const agentReg   = await deploy(deployerWallet, agentArt);
  const intentReg  = await deploy(deployerWallet, intentArt);
  const mockToken  = await deploy(deployerWallet, mockERC20Art);
  const mockRouter = await deploy(deployerWallet, mockRouterArt);

  const agentRegAddr   = await agentReg.getAddress();
  const intentRegAddr  = await intentReg.getAddress();
  const mockTokenAddr  = await mockToken.getAddress();
  const mockRouterAddr = await mockRouter.getAddress();

  const delegReg = await deploy(deployerWallet, delegArt, intentRegAddr, agentRegAddr);
  const delegRegAddr = await delegReg.getAddress();

  const execGate = await deploy(deployerWallet, gateArt, intentRegAddr, delegRegAddr, mockRouterAddr);
  const execGateAddr = await execGate.getAddress();

  // Wire up execution gate
  const wireTx = await delegReg.setExecutionGate(execGateAddr) as ethers.ContractTransactionResponse;
  await wireTx.wait();

  console.log(`  AgentRegistry:      ${agentRegAddr}`);
  console.log(`  IntentRegistry:     ${intentRegAddr}`);
  console.log(`  DelegationRegistry: ${delegRegAddr}`);
  console.log(`  MockERC20 (tokenIn):${mockTokenAddr}`);
  console.log(`  MockSwapRouter:     ${mockRouterAddr}`);
  console.log(`  ExecutionGate:      ${execGateAddr}`);

  // ---------------------------------------------------------------------------
  // [2] Register agents
  // ---------------------------------------------------------------------------
  console.log('\n[2] Registering agents...');

  for (const [addr, name] of [
    [orchestratorAddr, 'Orchestrator'],
    [researchAddr,     'ResearchAgent'],
    [executionAddr,    'ExecutionAgent'],
  ] as [string, string][]) {
    const tx = await agentReg.registerAgent(addr, name) as ethers.ContractTransactionResponse;
    await tx.wait();
    console.log(`  Registered ${name}: ${addr}`);
  }

  // ---------------------------------------------------------------------------
  // [3] Build and sign intent (500 USDC-equivalent, Uniswap-V3, 60 min)
  // ---------------------------------------------------------------------------
  console.log('\n[3] Building and signing intent...');

  const uniswapV3Id  = protocolId('Uniswap-V3');
  const deadline     = BigInt(Math.floor(Date.now() / 1000) + 3600);
  const nonce        = (await intentReg.nonces(userAddr)) as bigint;
  const maxAmountIn  = BigInt(500 * 10 ** 6);   // 500 USDC (6 decimals)
  const minAmountOut = BigInt(490 * 10 ** 6);

  const intentData = {
    owner:                  userAddr,
    authorizedOrchestrator: orchestratorAddr,
    tokenIn:                ethers.getAddress(mockTokenAddr),
    maxAmountIn,
    minAmountOut,
    allowedProtocols:       [uniswapV3Id],
    deadline,
    nonce,
  };

  const signature = await signIntent(intentData, deployerWallet, intentRegAddr);

  // ---------------------------------------------------------------------------
  // [4] Register intent
  // ---------------------------------------------------------------------------
  console.log('\n[4] Registering intent on-chain...');

  const intentTuple = [
    userAddr,
    orchestratorAddr,
    ethers.getAddress(mockTokenAddr),
    maxAmountIn,
    minAmountOut,
    [uniswapV3Id],
    deadline,
    nonce,
  ];

  const regTx = await (intentReg.connect(deployerWallet) as ethers.Contract).registerIntent(
    intentTuple, signature,
  ) as ethers.ContractTransactionResponse;
  const regReceipt = await regTx.wait();
  if (!regReceipt || regReceipt.status !== 1) throw new Error('registerIntent reverted');

  const intentId = parseEventArg(regReceipt, intentReg.interface, 'IntentRegistered', 'intentId');
  console.log(`  intentId: ${intentId}`);

  // ---------------------------------------------------------------------------
  // [5] Delegate from root (orchestrator → research agent, 400 USDC)
  // ---------------------------------------------------------------------------
  console.log('\n[5] Delegating from root to research agent...');

  const scope1 = [
    BigInt(400 * 10 ** 6),
    BigInt(492 * 10 ** 6),
    [uniswapV3Id],
    BigInt(Math.floor(Date.now() / 1000) + 1800),
  ];

  const deleg1Tx = await (delegReg.connect(orchestratorWallet) as ethers.Contract).delegateFromRoot(
    intentId, scope1, researchAddr,
  ) as ethers.ContractTransactionResponse;
  const deleg1Receipt = await deleg1Tx.wait();
  if (!deleg1Receipt || deleg1Receipt.status !== 1) throw new Error('delegateFromRoot reverted');

  const delegationId1 = parseEventArg(deleg1Receipt, delegReg.interface, 'DelegationCreated', 'delegationId');
  console.log(`  delegation1 (root→research): ${delegationId1}`);

  // ---------------------------------------------------------------------------
  // [6] Delegate from delegation (research → execution agent, 300 USDC)
  // ---------------------------------------------------------------------------
  console.log('\n[6] Delegating from delegation to execution agent...');

  const scope2 = [
    BigInt(300 * 10 ** 6),
    BigInt(494 * 10 ** 6),
    [uniswapV3Id],
    BigInt(Math.floor(Date.now() / 1000) + 900),
  ];

  const deleg2Tx = await (delegReg.connect(researchWallet) as ethers.Contract).delegateFromDelegation(
    delegationId1, scope2, executionAddr,
  ) as ethers.ContractTransactionResponse;
  const deleg2Receipt = await deleg2Tx.wait();
  if (!deleg2Receipt || deleg2Receipt.status !== 1) throw new Error('delegateFromDelegation reverted');

  const delegationId2 = parseEventArg(deleg2Receipt, delegReg.interface, 'DelegationCreated', 'delegationId');
  console.log(`  delegation2 (research→execution): ${delegationId2}`);

  // ---------------------------------------------------------------------------
  // [7] Verify chain (view call, must return true)
  // ---------------------------------------------------------------------------
  console.log('\n[7] Verifying chain...');

  const amountIn = BigInt(250 * 10 ** 6); // 250 USDC (<= all scopes)
  const txParams = [
    amountIn,
    BigInt(495 * 10 ** 6), // minAmountOut (>= all scopes)
    uniswapV3Id,
    ethers.getAddress(mockTokenAddr),
    ethers.getAddress(TOKEN_OUT),
    executionAddr, // recipient — also the tx sender
  ];

  const ok = await execGate.verifyChain(delegationId2, txParams) as boolean;
  if (!ok) throw new Error('verifyChain returned false');
  console.log('  verifyChain → True  ✓');

  // ---------------------------------------------------------------------------
  // [7b] Mint tokenIn to executionAddr and approve ExecutionGate
  // ---------------------------------------------------------------------------
  console.log('\n[7b] Setting up token approval for executeSwap...');

  const mintTx = await (mockToken.connect(deployerWallet) as ethers.Contract).mint(
    executionAddr, amountIn * 2n,
  ) as ethers.ContractTransactionResponse;
  await mintTx.wait();

  const approveTx = await (mockToken.connect(executionWallet) as ethers.Contract).approve(
    execGateAddr, amountIn * 2n,
  ) as ethers.ContractTransactionResponse;
  await approveTx.wait();

  console.log(`  Minted ${amountIn} tokenIn to ${executionAddr}`);
  console.log(`  Approved ExecutionGate (${execGateAddr}) to spend tokenIn  ✓`);

  // ---------------------------------------------------------------------------
  // [8] Execute swap
  // ---------------------------------------------------------------------------
  console.log('\n[8] Calling executeSwap...');

  const swapTx = await (execGate.connect(executionWallet) as ethers.Contract).executeSwap(
    delegationId2, txParams,
  ) as ethers.ContractTransactionResponse;
  const swapReceipt = await swapTx.wait();
  if (!swapReceipt || swapReceipt.status !== 1) throw new Error('executeSwap reverted');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const delegState = (await delegReg.getDelegation(delegationId2)) as any;
  if (!delegState.executed) throw new Error('executed flag not set after executeSwap');
  console.log(`  executeSwap tx: ${swapReceipt.hash}`);
  console.log('  delegation.executed → True  ✓');

  // ---------------------------------------------------------------------------
  // [9] Malicious delegation: 800 USDC when only 400 was authorized (scope1).
  //     This must be rejected with "Amount exceeds scope".
  // Need a fresh root delegation on a new intent (replay protection consumed scope1).
  // ---------------------------------------------------------------------------
  console.log('\n[9] Attempting malicious delegation (800 USDC > 400 authorized)...');

  const nonce2 = (await intentReg.nonces(userAddr)) as bigint;
  const intentData2 = { ...intentData, nonce: nonce2 };
  const sig2 = await signIntent(intentData2, deployerWallet, intentRegAddr);
  const intentTuple2 = [
    userAddr, orchestratorAddr, ethers.getAddress(mockTokenAddr),
    maxAmountIn, minAmountOut, [uniswapV3Id], deadline, nonce2,
  ];

  const reg2Tx = await (intentReg.connect(deployerWallet) as ethers.Contract).registerIntent(
    intentTuple2, sig2,
  ) as ethers.ContractTransactionResponse;
  const reg2Receipt = await reg2Tx.wait();
  const intentId2 = parseEventArg(reg2Receipt!, intentReg.interface, 'IntentRegistered', 'intentId');

  const scopeLimited = [
    BigInt(400 * 10 ** 6),
    BigInt(492 * 10 ** 6),
    [uniswapV3Id],
    BigInt(Math.floor(Date.now() / 1000) + 1800),
  ];

  const deleg3Tx = await (delegReg.connect(orchestratorWallet) as ethers.Contract).delegateFromRoot(
    intentId2, scopeLimited, researchAddr,
  ) as ethers.ContractTransactionResponse;
  const deleg3Receipt = await deleg3Tx.wait();
  const delegationLimited = parseEventArg(
    deleg3Receipt!, delegReg.interface, 'DelegationCreated', 'delegationId',
  );

  // Research tries to sub-delegate 800 USDC — must revert.
  // Use staticCall to get the revert reason without broadcasting.
  const scopeMalicious = [
    BigInt(800 * 10 ** 6),
    BigInt(492 * 10 ** 6),
    [uniswapV3Id],
    BigInt(Math.floor(Date.now() / 1000) + 900),
  ];

  let reverted = false;
  let revertReason = '';
  try {
    await (delegReg.connect(researchWallet) as ethers.Contract).delegateFromDelegation.staticCall(
      delegationLimited, scopeMalicious, executionAddr,
    );
  } catch (err: unknown) {
    reverted = true;
    revertReason = err instanceof Error ? err.message : String(err);
  }

  if (!reverted) throw new Error('Expected revert for malicious delegation but got none');
  if (!revertReason.includes('Amount exceeds scope')) {
    throw new Error(`Expected 'Amount exceeds scope' in revert reason, got: ${revertReason}`);
  }
  console.log(`  Malicious delegation correctly reverted with: ${revertReason.slice(0, 80)}`);
  console.log("  'Amount exceeds scope'  ✓");

  console.log('\n========================================');
  console.log('All integration tests passed.');
  console.log('========================================');
}

run().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
