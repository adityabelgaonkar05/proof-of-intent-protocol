import { ethers } from 'ethers';
import type { TransactionReceipt } from 'ethers';
import type { IntentData, ScopeData, TxParamsData, DelegationData, Config } from './types';
import { loadConfig } from './config';
import { signIntent, buildIntent } from './signIntent';

/**
 * Options for ContractClient.
 * Only `privateKey` is required — all other fields default to deployed Sepolia contracts.
 */
export interface ContractClientOptions {
  privateKey: string;
  rpcUrl?: string;
  chainId?: number;
  agentRegistryAddress?: string;
  intentRegistryAddress?: string;
  delegationRegistryAddress?: string;
  executionGateAddress?: string;
  ensName?: string;
  ensResolverAddress?: string;
  ensRegistryAddress?: string;
  zgApiKey?: string;
  zgRpcUrl?: string;
  zgIndexerUrl?: string;
}

import AGENT_REGISTRY_ABI from './abis/AgentRegistry.json';
import INTENT_REGISTRY_ABI from './abis/IntentRegistry.json';
import DELEGATION_REGISTRY_ABI from './abis/DelegationRegistry.json';
import EXECUTION_GATE_ABI from './abis/ExecutionGate.json';

const ENS_REGISTRY_ABI = [
  {
    inputs: [{ type: 'bytes32', name: 'node' }],
    name: 'resolver',
    outputs: [{ type: 'address' }],
    stateMutability: 'view',
    type: 'function',
  },
];

const ENS_RESOLVER_ABI = [
  {
    inputs: [
      { type: 'bytes32', name: 'node' },
      { type: 'string', name: 'key' },
      { type: 'string', name: 'value' },
    ],
    name: 'setText',
    outputs: [],
    stateMutability: 'nonpayable',
    type: 'function',
  },
];

// Minimal ERC20 ABI — only the functions needed for approve/allowance/balance checks.
const ERC20_ABI = [
  {
    inputs: [{ name: 'owner', type: 'address' }, { name: 'spender', type: 'address' }],
    name: 'allowance',
    outputs: [{ name: '', type: 'uint256' }],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [{ name: 'spender', type: 'address' }, { name: 'amount', type: 'uint256' }],
    name: 'approve',
    outputs: [{ name: '', type: 'bool' }],
    stateMutability: 'nonpayable',
    type: 'function',
  },
  {
    inputs: [{ name: 'account', type: 'address' }],
    name: 'balanceOf',
    outputs: [{ name: '', type: 'uint256' }],
    stateMutability: 'view',
    type: 'function',
  },
];

// ---------------------------------------------------------------------------
// Struct encoders (shared by ContractClient and module-level helpers)
// ---------------------------------------------------------------------------

function encodeIntent(intent: IntentData) {
  return {
    owner: ethers.getAddress(intent.owner),
    authorizedOrchestrator: ethers.getAddress(intent.authorizedOrchestrator),
    tokenIn: ethers.getAddress(intent.tokenIn),
    maxAmountIn: intent.maxAmountIn,
    minAmountOut: intent.minAmountOut,
    allowedProtocols: intent.allowedProtocols,
    deadline: intent.deadline,
    nonce: intent.nonce,
  };
}

function encodeScope(scope: ScopeData) {
  return {
    maxAmountIn: scope.maxAmountIn,
    minAmountOut: scope.minAmountOut,
    allowedProtocols: scope.allowedProtocols,
    deadline: scope.deadline,
  };
}

function encodeTxParams(params: TxParamsData) {
  return {
    amountIn: params.amountIn,
    minAmountOut: params.minAmountOut,
    protocol: params.protocol,
    tokenIn: ethers.getAddress(params.tokenIn),
    tokenOut: ethers.getAddress(params.tokenOut),
    recipient: ethers.getAddress(params.recipient),
  };
}

function parseEvent(
  receipt: TransactionReceipt,
  iface: ethers.Interface,
  eventName: string,
  argName: string,
): string {
  for (const log of receipt.logs) {
    try {
      const parsed = iface.parseLog({ topics: [...log.topics], data: log.data });
      if (parsed?.name === eventName) return parsed.args[argName] as string;
    } catch {
      // log belongs to a different contract; skip
    }
  }
  throw new Error(`${eventName} event not found in receipt`);
}

// ---------------------------------------------------------------------------
// ContractClient
// ---------------------------------------------------------------------------

export class ContractClient {
  readonly provider: ethers.JsonRpcProvider;
  readonly wallet: ethers.Wallet;
  readonly agentRegistry: ethers.Contract;
  readonly intentRegistry: ethers.Contract;
  readonly delegationRegistry: ethers.Contract;
  readonly executionGate: ethers.Contract;
  readonly config: Config;

  /**
   * Instantiate a ContractClient.
   *
   *   // Minimal — all contract addresses default to deployed Sepolia contracts:
   *   const client = new ContractClient({ privateKey: process.env.PRIVATE_KEY! });
   *
   *   // With overrides:
   *   const client = new ContractClient({ privateKey, rpcUrl: 'https://...', chainId: 1 });
   */
  constructor({ privateKey, ...configOverrides }: ContractClientOptions) {
    this.config = loadConfig(configOverrides);
    this.provider = new ethers.JsonRpcProvider(this.config.rpcUrl);
    this.wallet = new ethers.Wallet(privateKey, this.provider);
    this.agentRegistry = new ethers.Contract(
      ethers.getAddress(this.config.agentRegistryAddress),
      AGENT_REGISTRY_ABI,
      this.wallet,
    );
    this.intentRegistry = new ethers.Contract(
      ethers.getAddress(this.config.intentRegistryAddress),
      INTENT_REGISTRY_ABI,
      this.wallet,
    );
    this.delegationRegistry = new ethers.Contract(
      ethers.getAddress(this.config.delegationRegistryAddress),
      DELEGATION_REGISTRY_ABI,
      this.wallet,
    );
    this.executionGate = new ethers.Contract(
      ethers.getAddress(this.config.executionGateAddress),
      EXECUTION_GATE_ABI,
      this.wallet,
    );
  }

  private async sendTxReceipt(
    tx: Promise<ethers.ContractTransactionResponse>,
  ): Promise<TransactionReceipt> {
    const response = await tx;
    const receipt = await response.wait();
    if (!receipt || receipt.status === 0) throw new Error('Transaction reverted');
    return receipt;
  }

  async sendTx(tx: Promise<ethers.ContractTransactionResponse>): Promise<string> {
    const receipt = await this.sendTxReceipt(tx);
    return receipt.hash;
  }

  async registerIntent(intent: IntentData, signature: string): Promise<string> {
    const receipt = await this.sendTxReceipt(
      this.intentRegistry.registerIntent(
        encodeIntent(intent),
        ethers.getBytes(signature),
      ) as Promise<ethers.ContractTransactionResponse>,
    );

    const intentId = parseEvent(
      receipt,
      this.intentRegistry.interface,
      'IntentRegistered',
      'intentId',
    );

    // Non-blocking: 0G and ENS storage; failures are warnings only
    this.storeIntentOn0g(intent, intentId).catch((e: unknown) =>
      console.warn(`Warning [0G]: ${e}`),
    );
    this.storeIntentOnEns(intentId, this.config.ensName).catch((e: unknown) =>
      console.warn(`Warning [ENS]: ${e}`),
    );

    return intentId;
  }

  /**
   * Store the intent on 0G decentralised storage.
   * Returns the root-hash reference on success, null on any failure.
   * Non-blocking — callers should not await unless they need the reference.
   *
   * To enable: provide ZG_API_KEY in config and install the 0G SDK or make
   * an HTTP POST to the 0G upload endpoint yourself inside this method.
   */
  async storeIntentOn0g(intent: IntentData, intentId: string): Promise<string | null> {
    if (!this.config.zgApiKey) {
      console.log('0G storage skipped: zgApiKey not set.');
      return null;
    }
    console.warn(
      'Warning [0G]: storeIntentOn0g not implemented. ' +
        'Integrate the 0G SDK and POST to zgRpcUrl/zgIndexerUrl.',
    );
    void intent;
    void intentId;
    return null;
  }

  /**
   * Write intentId as the "active-intent" text record on the ENS name.
   * Non-blocking — skipped silently when ensName is not set.
   */
  async storeIntentOnEns(intentId: string, ensName: string): Promise<void> {
    if (!ensName) return;

    const node = ethers.namehash(ensName);

    const registryContract = new ethers.Contract(
      ethers.getAddress(this.config.ensRegistryAddress),
      ENS_REGISTRY_ABI,
      this.wallet,
    );

    let resolverAddr: string = (await registryContract.resolver(node)) as string;
    if (resolverAddr === ethers.ZeroAddress) {
      resolverAddr = this.config.ensResolverAddress;
    }

    const resolverContract = new ethers.Contract(
      ethers.getAddress(resolverAddr),
      ENS_RESOLVER_ABI,
      this.wallet,
    );

    await this.sendTxReceipt(
      resolverContract.setText(
        node,
        'active-intent',
        intentId,
      ) as Promise<ethers.ContractTransactionResponse>,
    );
    console.log(`Intent linked to ${ensName} on ENS`);
  }

  async delegateFromRoot(
    rootIntentId: string,
    childScope: ScopeData,
    delegateTo: string,
  ): Promise<string> {
    const receipt = await this.sendTxReceipt(
      this.delegationRegistry.delegateFromRoot(
        rootIntentId,
        encodeScope(childScope),
        ethers.getAddress(delegateTo),
      ) as Promise<ethers.ContractTransactionResponse>,
    );
    return parseEvent(
      receipt,
      this.delegationRegistry.interface,
      'DelegationCreated',
      'delegationId',
    );
  }

  async delegateFromDelegation(
    parentDelegationId: string,
    childScope: ScopeData,
    delegateTo: string,
  ): Promise<string> {
    const receipt = await this.sendTxReceipt(
      this.delegationRegistry.delegateFromDelegation(
        parentDelegationId,
        encodeScope(childScope),
        ethers.getAddress(delegateTo),
      ) as Promise<ethers.ContractTransactionResponse>,
    );
    return parseEvent(
      receipt,
      this.delegationRegistry.interface,
      'DelegationCreated',
      'delegationId',
    );
  }

  async ensureTokenApproval(tokenAddress: string, spender: string, amount: bigint): Promise<void> {
    const token = new ethers.Contract(ethers.getAddress(tokenAddress), ERC20_ABI, this.wallet);
    const current = (await token.allowance(this.wallet.address, ethers.getAddress(spender))) as bigint;
    if (current < amount) {
      await this.sendTxReceipt(
        token.approve(ethers.getAddress(spender), amount) as Promise<ethers.ContractTransactionResponse>,
      );
    }
  }

  async tokenBalance(tokenAddress: string, account: string): Promise<bigint> {
    const token = new ethers.Contract(ethers.getAddress(tokenAddress), ERC20_ABI, this.provider);
    return token.balanceOf(ethers.getAddress(account)) as Promise<bigint>;
  }

  async executeSwap(delegationId: string, txParams: TxParamsData): Promise<string> {
    return this.sendTx(
      this.executionGate.executeSwap(
        delegationId,
        encodeTxParams(txParams),
      ) as Promise<ethers.ContractTransactionResponse>,
    );
  }

  async verifyChain(delegationId: string, txParams: TxParamsData): Promise<boolean> {
    return this.executionGate.verifyChain(
      delegationId,
      encodeTxParams(txParams),
    ) as Promise<boolean>;
  }

  /**
   * Build, sign, and register an intent in one call. Returns intentId.
   *
   * @param tokenIn          ERC20 address to swap from.
   * @param maxAmountIn      Max spend in raw units — use toUsdc(500) or toWeth(0.15).
   * @param minAmountOut     Minimum acceptable output in raw units.
   * @param allowedProtocols Protocol names e.g. ["Uniswap-V3"]. Hashed automatically.
   * @param deadline         Unix timestamp as bigint. Use inMinutes(60) for 1 hour.
   * @param orchestrator     Address authorised to create the first delegation. Defaults to this wallet.
   * @param owner            Intent owner address. Defaults to this wallet.
   */
  async createIntent(params: {
    tokenIn: string;
    maxAmountIn: bigint;
    minAmountOut: bigint;
    /** Protocol names e.g. ["Uniswap-V3"] — hashed to bytes32 automatically */
    allowedProtocols: string[];
    deadline: bigint;
    orchestrator?: string;
    owner?: string;
  }): Promise<string> {
    const owner = params.owner ?? this.wallet.address;
    const orchestrator = params.orchestrator ?? this.wallet.address;
    const nonce = await (this.intentRegistry.nonces(ethers.getAddress(owner)) as Promise<bigint>);
    const intent = buildIntent({
      owner,
      authorizedOrchestrator: orchestrator,
      tokenIn: params.tokenIn,
      maxAmountIn: params.maxAmountIn,
      minAmountOut: params.minAmountOut,
      allowedProtocols: params.allowedProtocols,
      deadline: params.deadline,
      nonce,
    });
    const signature = await signIntent(intent, this.wallet.privateKey, this.config);
    return this.registerIntent(intent, signature);
  }

  /**
   * Register an address in AgentRegistry so it can receive delegations.
   *
   * @param agentAddress  Ethereum address to register.
   * @param name          Human-readable label stored on-chain.
   * @param skipIfActive  When true (default), returns null if already registered.
   */
  async registerAgent(agentAddress: string, name: string, skipIfActive = true): Promise<string | null> {
    const addr = ethers.getAddress(agentAddress);
    if (skipIfActive) {
      const isActive = (await this.agentRegistry.isActiveAgent(addr)) as boolean;
      if (isActive) return null;
    }
    return this.sendTx(
      this.agentRegistry.registerAgent(addr, name) as Promise<ethers.ContractTransactionResponse>,
    );
  }
}

// ---------------------------------------------------------------------------
// Module-level helpers (mirrors the Python module-level functions)
// ---------------------------------------------------------------------------

export function getProvider(config: Config): ethers.JsonRpcProvider {
  return new ethers.JsonRpcProvider(config.rpcUrl);
}

export async function getNonce(config: Config, owner: string): Promise<bigint> {
  const registry = new ethers.Contract(
    ethers.getAddress(config.intentRegistryAddress),
    INTENT_REGISTRY_ABI,
    getProvider(config),
  );
  return registry.nonces(ethers.getAddress(owner)) as Promise<bigint>;
}

export async function getDomainSeparator(config: Config): Promise<string> {
  const registry = new ethers.Contract(
    ethers.getAddress(config.intentRegistryAddress),
    INTENT_REGISTRY_ABI,
    getProvider(config),
  );
  return registry.DOMAIN_SEPARATOR() as Promise<string>;
}

export async function registerIntentRaw(
  intent: IntentData,
  signatureHex: string,
  privateKey: string,
  config: Config,
): Promise<TransactionReceipt> {
  const wallet = new ethers.Wallet(privateKey, getProvider(config));
  const registry = new ethers.Contract(
    ethers.getAddress(config.intentRegistryAddress),
    INTENT_REGISTRY_ABI,
    wallet,
  );
  const tx = (await registry.registerIntent(
    encodeIntent(intent),
    ethers.getBytes(signatureHex),
  )) as ethers.ContractTransactionResponse;
  const receipt = await tx.wait();
  if (!receipt || receipt.status === 0) throw new Error('Transaction reverted');
  return receipt;
}

export function extractIntentIdFromReceipt(
  receipt: TransactionReceipt,
  config: Config,
): string {
  const iface = new ethers.Interface(INTENT_REGISTRY_ABI);
  return parseEvent(receipt, iface, 'IntentRegistered', 'intentId');
}

export async function delegateFromRoot(
  rootIntentId: string,
  scope: ScopeData,
  delegateTo: string,
  privateKey: string,
  config: Config,
): Promise<TransactionReceipt> {
  const wallet = new ethers.Wallet(privateKey, getProvider(config));
  const registry = new ethers.Contract(
    ethers.getAddress(config.delegationRegistryAddress),
    DELEGATION_REGISTRY_ABI,
    wallet,
  );
  const tx = (await registry.delegateFromRoot(
    rootIntentId,
    encodeScope(scope),
    ethers.getAddress(delegateTo),
  )) as ethers.ContractTransactionResponse;
  const receipt = await tx.wait();
  if (!receipt || receipt.status === 0) throw new Error('Transaction reverted');
  return receipt;
}

export async function delegateFromDelegation(
  parentDelegationId: string,
  scope: ScopeData,
  delegateTo: string,
  privateKey: string,
  config: Config,
): Promise<TransactionReceipt> {
  const wallet = new ethers.Wallet(privateKey, getProvider(config));
  const registry = new ethers.Contract(
    ethers.getAddress(config.delegationRegistryAddress),
    DELEGATION_REGISTRY_ABI,
    wallet,
  );
  const tx = (await registry.delegateFromDelegation(
    parentDelegationId,
    encodeScope(scope),
    ethers.getAddress(delegateTo),
  )) as ethers.ContractTransactionResponse;
  const receipt = await tx.wait();
  if (!receipt || receipt.status === 0) throw new Error('Transaction reverted');
  return receipt;
}

export function extractDelegationIdFromReceipt(
  receipt: TransactionReceipt,
  config: Config,
): string {
  const iface = new ethers.Interface(DELEGATION_REGISTRY_ABI);
  return parseEvent(receipt, iface, 'DelegationCreated', 'delegationId');
}

export async function getDelegation(
  delegationId: string,
  config: Config,
): Promise<DelegationData> {
  const registry = new ethers.Contract(
    ethers.getAddress(config.delegationRegistryAddress),
    DELEGATION_REGISTRY_ABI,
    getProvider(config),
  );
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = (await registry.getDelegation(delegationId)) as any;
  return {
    parentId: r.parentId as string,
    isRootIntent: r.isRootIntent as boolean,
    scope: {
      maxAmountIn: r.scope.maxAmountIn as bigint,
      minAmountOut: r.scope.minAmountOut as bigint,
      allowedProtocols: [...(r.scope.allowedProtocols as string[])],
      deadline: r.scope.deadline as bigint,
    },
    delegatedTo: r.delegatedTo as string,
    executed: r.executed as boolean,
  };
}

export async function verifyChain(
  delegationId: string,
  txParams: TxParamsData,
  config: Config,
): Promise<boolean> {
  const gate = new ethers.Contract(
    ethers.getAddress(config.executionGateAddress),
    EXECUTION_GATE_ABI,
    getProvider(config),
  );
  return gate.verifyChain(delegationId, encodeTxParams(txParams)) as Promise<boolean>;
}

export async function executeSwap(
  delegationId: string,
  txParams: TxParamsData,
  privateKey: string,
  config: Config,
): Promise<TransactionReceipt> {
  const wallet = new ethers.Wallet(privateKey, getProvider(config));
  const gate = new ethers.Contract(
    ethers.getAddress(config.executionGateAddress),
    EXECUTION_GATE_ABI,
    wallet,
  );
  const tx = (await gate.executeSwap(
    delegationId,
    encodeTxParams(txParams),
  )) as ethers.ContractTransactionResponse;
  const receipt = await tx.wait();
  if (!receipt || receipt.status === 0) throw new Error('Transaction reverted');
  return receipt;
}
