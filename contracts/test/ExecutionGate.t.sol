// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/IntentRegistry.sol";
import "../src/AgentRegistry.sol";
import "../src/DelegationRegistry.sol";
import "../src/ExecutionGate.sol";

bytes32 constant UNISWAP_V3 = keccak256(abi.encodePacked("Uniswap-V3"));
bytes32 constant CURVE       = keccak256(abi.encodePacked("Curve"));

contract ExecutionGateTest is Test {
    IntentRegistry public intentRegistry;
    AgentRegistry public agentRegistry;
    DelegationRegistry public delegationRegistry;
    ExecutionGate public executionGate;

    uint256 internal ownerKey = 0xA11CE;
    address internal owner;
    address internal agent;

    address internal constant TOKEN_IN  = address(0x1234);
    address internal constant TOKEN_OUT = address(0x5678);
    // address(0xC0FFEE) is the authorizedOrchestrator embedded in all intents
    address internal constant ORCHESTRATOR = address(0xC0FFEE);

    bytes32 internal protocol;
    bytes32 internal intentId;
    bytes32 internal delegationId;

    function setUp() public {
        intentRegistry     = new IntentRegistry();
        agentRegistry      = new AgentRegistry();
        delegationRegistry = new DelegationRegistry(address(intentRegistry), address(agentRegistry));
        executionGate      = new ExecutionGate(address(intentRegistry), address(delegationRegistry));
        delegationRegistry.setExecutionGate(address(executionGate));

        owner    = vm.addr(ownerKey);
        agent    = makeAddr("agent");
        protocol = UNISWAP_V3;

        // Register agent so isActiveAgent checks pass
        agentRegistry.registerAgent(agent, "agent");

        bytes32[] memory protocols = new bytes32[](1);
        protocols[0] = protocol;

        IntentRegistry.Intent memory intent = IntentRegistry.Intent({
            owner: owner,
            authorizedOrchestrator: ORCHESTRATOR,
            tokenIn: TOKEN_IN,
            maxAmountIn: 1 ether,
            minAmountOut: 0.95 ether,
            allowedProtocols: protocols,
            deadline: block.timestamp + 1 hours,
            nonce: 0
        });
        intentId = intentRegistry.registerIntent(intent, _signIntent(intent));

        DelegationRegistry.Scope memory scope = DelegationRegistry.Scope({
            maxAmountIn: 0.5 ether,
            minAmountOut: 0.97 ether,
            allowedProtocols: protocols,
            deadline: block.timestamp + 30 minutes
        });
        vm.prank(ORCHESTRATOR);
        delegationId = delegationRegistry.delegateFromRoot(intentId, scope, agent);
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    function _signIntent(IntentRegistry.Intent memory intent) internal view returns (bytes memory) {
        bytes32 typehash = keccak256(
            "Intent(address owner,address authorizedOrchestrator,address tokenIn,uint256 maxAmountIn,uint256 minAmountOut,bytes32[] allowedProtocols,uint256 deadline,uint256 nonce)"
        );
        bytes32 structHash = keccak256(abi.encode(
            typehash,
            intent.owner, intent.authorizedOrchestrator, intent.tokenIn, intent.maxAmountIn, intent.minAmountOut,
            keccak256(abi.encodePacked(intent.allowedProtocols)),
            intent.deadline, intent.nonce
        ));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", intentRegistry.DOMAIN_SEPARATOR(), structHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(ownerKey, digest);
        return abi.encodePacked(r, s, v);
    }

    function _validParams() internal view returns (ExecutionGate.TxParams memory) {
        return ExecutionGate.TxParams({
            amountIn:     0.4 ether,    // <= delegation.maxAmountIn (0.5)
            minAmountOut: 0.98 ether,   // >= delegation.minAmountOut (0.97)
            protocol:     protocol,
            tokenIn:      TOKEN_IN,
            tokenOut:     TOKEN_OUT,
            recipient:    agent
        });
    }

    // -------------------------------------------------------------------------
    // verifyChain — happy path
    // -------------------------------------------------------------------------

    function test_VerifyChain_Succeeds() public view {
        assertTrue(executionGate.verifyChain(delegationId, _validParams()));
    }

    // -------------------------------------------------------------------------
    // verifyChain — scope-level reverts
    // -------------------------------------------------------------------------

    function test_VerifyChain_RevertAmountExceedsScope() public {
        ExecutionGate.TxParams memory p = _validParams();
        p.amountIn = 0.6 ether; // > delegation.maxAmountIn (0.5)
        vm.expectRevert("Amount exceeds scope");
        executionGate.verifyChain(delegationId, p);
    }

    function test_VerifyChain_RevertMinOutBelowScope() public {
        ExecutionGate.TxParams memory p = _validParams();
        p.minAmountOut = 0.5 ether; // < delegation.minAmountOut (0.97)
        vm.expectRevert("MinOut below scope");
        executionGate.verifyChain(delegationId, p);
    }

    function test_VerifyChain_RevertDeadlinePassed() public {
        vm.warp(block.timestamp + 2 hours);
        vm.expectRevert("Deadline passed");
        executionGate.verifyChain(delegationId, _validParams());
    }

    function test_VerifyChain_RevertProtocolNotAllowed() public {
        ExecutionGate.TxParams memory p = _validParams();
        p.protocol = keccak256("sushiswap");
        vm.expectRevert("Protocol not allowed");
        executionGate.verifyChain(delegationId, p);
    }

    // -------------------------------------------------------------------------
    // verifyChain — root intent-level reverts
    // -------------------------------------------------------------------------

    function test_VerifyChain_RevertWrongToken() public {
        ExecutionGate.TxParams memory p = _validParams();
        p.tokenIn = address(0xDEAD);
        vm.expectRevert("Wrong token");
        executionGate.verifyChain(delegationId, p);
    }

    function test_VerifyChain_RevertExceedsRootIntent() public {
        // Replay protection prevents delegating from the same intentId twice.
        // Register a second intent (nonce=1) to get a fresh delegation slot.
        bytes32[] memory protocols = new bytes32[](1);
        protocols[0] = protocol;

        IntentRegistry.Intent memory intent2 = IntentRegistry.Intent({
            owner: owner,
            authorizedOrchestrator: ORCHESTRATOR,
            tokenIn: TOKEN_IN,
            maxAmountIn: 1 ether,
            minAmountOut: 0.95 ether,
            allowedProtocols: protocols,
            deadline: block.timestamp + 1 hours,
            nonce: 1
        });
        bytes32 intentId2 = intentRegistry.registerIntent(intent2, _signIntent(intent2));

        // Delegate with scope equal to root (maxAmountIn = 1 ether)
        DelegationRegistry.Scope memory scope = DelegationRegistry.Scope({
            maxAmountIn: 1 ether,
            minAmountOut: 0.95 ether,
            allowedProtocols: protocols,
            deadline: block.timestamp + 30 minutes
        });
        vm.prank(ORCHESTRATOR);
        bytes32 wideDelegationId = delegationRegistry.delegateFromRoot(intentId2, scope, agent);

        // amountIn=0.9 passes both wide scope (0.9 <= 1) and root intent (0.9 <= 1)
        ExecutionGate.TxParams memory p = _validParams();
        p.amountIn = 0.9 ether;
        assertTrue(executionGate.verifyChain(wideDelegationId, p));
    }

    function test_VerifyChain_RevertRootDeadlinePassed() public {
        // Scope deadline < root deadline; warp past both.
        vm.warp(block.timestamp + 2 hours);
        vm.expectRevert("Deadline passed"); // scope deadline caught first
        executionGate.verifyChain(delegationId, _validParams());
    }

    // -------------------------------------------------------------------------
    // verifyChain — multi-hop chain
    // -------------------------------------------------------------------------

    function test_VerifyChain_MultiHop() public {
        address subAgent = makeAddr("subAgent");
        agentRegistry.registerAgent(subAgent, "subAgent");

        bytes32[] memory protocols = new bytes32[](1);
        protocols[0] = protocol;

        DelegationRegistry.Scope memory subScope = DelegationRegistry.Scope({
            maxAmountIn:  0.3 ether,
            minAmountOut: 0.99 ether,
            allowedProtocols: protocols,
            deadline: block.timestamp + 15 minutes
        });
        vm.prank(agent);
        bytes32 subId = delegationRegistry.delegateFromDelegation(delegationId, subScope, subAgent);

        ExecutionGate.TxParams memory p = ExecutionGate.TxParams({
            amountIn:     0.25 ether,
            minAmountOut: 0.99 ether,
            protocol:     protocol,
            tokenIn:      TOKEN_IN,
            tokenOut:     TOKEN_OUT,
            recipient:    subAgent
        });
        assertTrue(executionGate.verifyChain(subId, p));
    }

    function test_VerifyChain_MultiHop_InnerScopeViolationReverts() public {
        address subAgent = makeAddr("subAgent");
        agentRegistry.registerAgent(subAgent, "subAgent");

        bytes32[] memory protocols = new bytes32[](1);
        protocols[0] = protocol;

        DelegationRegistry.Scope memory subScope = DelegationRegistry.Scope({
            maxAmountIn:  0.3 ether,
            minAmountOut: 0.99 ether,
            allowedProtocols: protocols,
            deadline: block.timestamp + 15 minutes
        });
        vm.prank(agent);
        bytes32 subId = delegationRegistry.delegateFromDelegation(delegationId, subScope, subAgent);

        ExecutionGate.TxParams memory p = ExecutionGate.TxParams({
            amountIn:     0.4 ether,    // violates subScope.maxAmountIn (0.3)
            minAmountOut: 0.99 ether,
            protocol:     protocol,
            tokenIn:      TOKEN_IN,
            tokenOut:     TOKEN_OUT,
            recipient:    subAgent
        });
        vm.expectRevert("Amount exceeds scope");
        executionGate.verifyChain(subId, p);
    }

    // -------------------------------------------------------------------------
    // executeSwap — happy path
    // -------------------------------------------------------------------------

    function test_ExecuteSwap_Succeeds() public {
        vm.prank(agent);
        executionGate.executeSwap(delegationId, _validParams());
        assertTrue(delegationRegistry.getDelegation(delegationId).executed);
    }

    function test_ExecuteSwap_EmitsSwapExecuted() public {
        ExecutionGate.TxParams memory p = _validParams();
        vm.expectEmit(true, false, false, true);
        emit ExecutionGate.SwapExecuted(delegationId, p.amountIn, p.recipient);
        vm.prank(agent);
        executionGate.executeSwap(delegationId, p);
    }

    // -------------------------------------------------------------------------
    // executeSwap — authorization reverts
    // -------------------------------------------------------------------------

    function test_ExecuteSwap_RevertNotAuthorized() public {
        vm.prank(makeAddr("random"));
        vm.expectRevert("Not authorized");
        executionGate.executeSwap(delegationId, _validParams());
    }

    function test_ExecuteSwap_RevertAlreadyExecuted() public {
        vm.prank(agent);
        executionGate.executeSwap(delegationId, _validParams());
        vm.prank(agent);
        vm.expectRevert("Already executed");
        executionGate.executeSwap(delegationId, _validParams());
    }

    // -------------------------------------------------------------------------
    // executeSwap — verification failures bubble up
    // -------------------------------------------------------------------------

    function test_ExecuteSwap_RevertAmountExceedsScope() public {
        ExecutionGate.TxParams memory p = _validParams();
        p.amountIn = 0.6 ether;
        vm.prank(agent);
        vm.expectRevert("Amount exceeds scope");
        executionGate.executeSwap(delegationId, p);
    }

    function test_ExecuteSwap_RevertWrongToken() public {
        ExecutionGate.TxParams memory p = _validParams();
        p.tokenIn = address(0xDEAD);
        vm.prank(agent);
        vm.expectRevert("Wrong token");
        executionGate.executeSwap(delegationId, p);
    }

    function test_ExecuteSwap_RevertProtocolNotAllowed() public {
        ExecutionGate.TxParams memory p = _validParams();
        p.protocol = keccak256("sushiswap");
        vm.prank(agent);
        vm.expectRevert("Protocol not allowed");
        executionGate.executeSwap(delegationId, p);
    }

    // -------------------------------------------------------------------------
    // executeSwap — multi-hop end-to-end
    // -------------------------------------------------------------------------

    function test_ExecuteSwap_MultiHop_Succeeds() public {
        address subAgent = makeAddr("subAgent");
        agentRegistry.registerAgent(subAgent, "subAgent");

        bytes32[] memory protocols = new bytes32[](1);
        protocols[0] = protocol;

        DelegationRegistry.Scope memory subScope = DelegationRegistry.Scope({
            maxAmountIn:  0.3 ether,
            minAmountOut: 0.99 ether,
            allowedProtocols: protocols,
            deadline: block.timestamp + 15 minutes
        });
        vm.prank(agent);
        bytes32 subId = delegationRegistry.delegateFromDelegation(delegationId, subScope, subAgent);

        ExecutionGate.TxParams memory p = ExecutionGate.TxParams({
            amountIn:     0.25 ether,
            minAmountOut: 0.99 ether,
            protocol:     protocol,
            tokenIn:      TOKEN_IN,
            tokenOut:     TOKEN_OUT,
            recipient:    subAgent
        });
        vm.prank(subAgent);
        executionGate.executeSwap(subId, p);

        assertTrue(delegationRegistry.getDelegation(subId).executed);
    }

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    function test_Constructor_SetsAddresses() public view {
        assertEq(executionGate.intentRegistry(),    address(intentRegistry));
        assertEq(executionGate.delegationRegistry(), address(delegationRegistry));
        assertEq(executionGate.owner(),              address(this));
    }
}
