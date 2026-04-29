// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/IntentRegistry.sol";
import "../src/AgentRegistry.sol";
import "../src/DelegationRegistry.sol";
import "../src/ExecutionGate.sol";

bytes32 constant UNISWAP_V3 = keccak256(abi.encodePacked("Uniswap-V3"));
bytes32 constant CURVE       = keccak256(abi.encodePacked("Curve"));

contract DelegationRegistryTest is Test {
    IntentRegistry public intentRegistry;
    AgentRegistry public agentRegistry;
    DelegationRegistry public delegationRegistry;
    ExecutionGate public executionGate;

    uint256 internal ownerKey = 0xA11CE;
    address internal owner;
    address internal agent;
    address internal subAgent;

    // address(0xC0FFEE) is the authorizedOrchestrator embedded in all intents
    address internal constant ORCHESTRATOR = address(0xC0FFEE);

    bytes32 internal intentId;
    IntentRegistry.Intent internal rootIntent;

    function setUp() public {
        intentRegistry    = new IntentRegistry();
        agentRegistry     = new AgentRegistry();
        delegationRegistry = new DelegationRegistry(address(intentRegistry), address(agentRegistry));
        executionGate     = new ExecutionGate(address(intentRegistry), address(delegationRegistry));
        delegationRegistry.setExecutionGate(address(executionGate));

        owner    = vm.addr(ownerKey);
        agent    = makeAddr("agent");
        subAgent = makeAddr("subAgent");

        // Register both agents so isActiveAgent checks pass
        agentRegistry.registerAgent(agent, "agent");
        agentRegistry.registerAgent(subAgent, "subAgent");

        bytes32[] memory protocols = new bytes32[](2);
        protocols[0] = UNISWAP_V3;
        protocols[1] = CURVE;

        rootIntent = IntentRegistry.Intent({
            owner: owner,
            authorizedOrchestrator: ORCHESTRATOR,
            tokenIn: address(0x1234),
            maxAmountIn: 1 ether,
            minAmountOut: 0.95 ether,
            allowedProtocols: protocols,
            deadline: block.timestamp + 1 hours,
            nonce: 0
        });

        intentId = intentRegistry.registerIntent(rootIntent, _signIntent(rootIntent));
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
            intent.owner,
            intent.authorizedOrchestrator,
            intent.tokenIn,
            intent.maxAmountIn,
            intent.minAmountOut,
            keccak256(abi.encodePacked(intent.allowedProtocols)),
            intent.deadline,
            intent.nonce
        ));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", intentRegistry.DOMAIN_SEPARATOR(), structHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(ownerKey, digest);
        return abi.encodePacked(r, s, v);
    }

    function _narrowScope() internal view returns (DelegationRegistry.Scope memory) {
        bytes32[] memory protocols = new bytes32[](1);
        protocols[0] = UNISWAP_V3;
        return DelegationRegistry.Scope({
            maxAmountIn: 0.5 ether,
            minAmountOut: 0.97 ether,
            allowedProtocols: protocols,
            deadline: block.timestamp + 30 minutes
        });
    }

    function _createRootDelegation() internal returns (bytes32) {
        vm.prank(ORCHESTRATOR);
        return delegationRegistry.delegateFromRoot(intentId, _narrowScope(), agent);
    }

    // -------------------------------------------------------------------------
    // delegateFromRoot — happy path
    // -------------------------------------------------------------------------

    function test_DelegateFromRoot_Succeeds() public {
        DelegationRegistry.Scope memory scope = _narrowScope();
        vm.prank(ORCHESTRATOR);
        bytes32 delId = delegationRegistry.delegateFromRoot(intentId, scope, agent);

        assertTrue(delegationRegistry.delegationExists(delId));
        DelegationRegistry.Delegation memory d = delegationRegistry.getDelegation(delId);
        assertEq(d.delegatedTo, agent);
        assertEq(d.parentId, intentId);
        assertTrue(d.isRootIntent);
        assertFalse(d.executed);
        assertEq(d.scope.maxAmountIn, 0.5 ether);
    }

    function test_DelegateFromRoot_EmitsEvent() public {
        DelegationRegistry.Scope memory scope = _narrowScope();
        vm.prank(ORCHESTRATOR);
        vm.recordLogs();
        bytes32 delId = delegationRegistry.delegateFromRoot(intentId, scope, agent);

        Vm.Log[] memory logs = vm.getRecordedLogs();
        assertGt(logs.length, 0);
        // Topic[0] = event sig, topic[1] = delegationId, topic[2] = parentId, topic[3] = delegatedTo
        assertEq(logs[0].topics[1], delId);
        assertEq(logs[0].topics[2], intentId);
        assertEq(address(uint160(uint256(logs[0].topics[3]))), agent);
    }

    // -------------------------------------------------------------------------
    // delegateFromRoot — reverts
    // -------------------------------------------------------------------------

    function test_DelegateFromRoot_RevertNotOwner() public {
        vm.prank(agent);
        vm.expectRevert("Not authorized orchestrator");
        delegationRegistry.delegateFromRoot(intentId, _narrowScope(), agent);
    }

    function test_DelegateFromRoot_RevertAmountExceedsRoot() public {
        DelegationRegistry.Scope memory scope = _narrowScope();
        scope.maxAmountIn = 2 ether;
        vm.prank(ORCHESTRATOR);
        vm.expectRevert("Amount exceeds root");
        delegationRegistry.delegateFromRoot(intentId, scope, agent);
    }

    function test_DelegateFromRoot_RevertMinOutBelowRoot() public {
        DelegationRegistry.Scope memory scope = _narrowScope();
        scope.minAmountOut = 0.5 ether;
        vm.prank(ORCHESTRATOR);
        vm.expectRevert("MinOut below root");
        delegationRegistry.delegateFromRoot(intentId, scope, agent);
    }

    function test_DelegateFromRoot_RevertDeadlineExceedsRoot() public {
        DelegationRegistry.Scope memory scope = _narrowScope();
        scope.deadline = block.timestamp + 2 hours;
        vm.prank(ORCHESTRATOR);
        vm.expectRevert("Deadline exceeds root");
        delegationRegistry.delegateFromRoot(intentId, scope, agent);
    }

    function test_DelegateFromRoot_RevertProtocolsNotSubset() public {
        DelegationRegistry.Scope memory scope = _narrowScope();
        bytes32[] memory bad = new bytes32[](1);
        bad[0] = keccak256("sushiswap");
        scope.allowedProtocols = bad;
        vm.prank(ORCHESTRATOR);
        vm.expectRevert("Protocols not subset");
        delegationRegistry.delegateFromRoot(intentId, scope, agent);
    }

    function test_DelegateFromRoot_RevertIntentNotFound() public {
        vm.prank(ORCHESTRATOR);
        vm.expectRevert("Intent not found");
        delegationRegistry.delegateFromRoot(bytes32(0), _narrowScope(), agent);
    }

    // -------------------------------------------------------------------------
    // delegateFromDelegation — happy path
    // -------------------------------------------------------------------------

    function test_DelegateFromDelegation_Succeeds() public {
        bytes32 parentId = _createRootDelegation();

        bytes32[] memory protocols = new bytes32[](1);
        protocols[0] = UNISWAP_V3;
        DelegationRegistry.Scope memory childScope = DelegationRegistry.Scope({
            maxAmountIn: 0.3 ether,
            minAmountOut: 0.98 ether,
            allowedProtocols: protocols,
            deadline: block.timestamp + 15 minutes
        });

        vm.prank(agent);
        bytes32 subId = delegationRegistry.delegateFromDelegation(parentId, childScope, subAgent);

        assertTrue(delegationRegistry.delegationExists(subId));
        DelegationRegistry.Delegation memory d = delegationRegistry.getDelegation(subId);
        assertEq(d.delegatedTo, subAgent);
        assertEq(d.parentId, parentId);
        assertFalse(d.isRootIntent);
    }

    // -------------------------------------------------------------------------
    // delegateFromDelegation — reverts
    // -------------------------------------------------------------------------

    function test_DelegateFromDelegation_RevertParentNotFound() public {
        vm.prank(agent);
        vm.expectRevert("Parent not found");
        delegationRegistry.delegateFromDelegation(bytes32(0), _narrowScope(), subAgent);
    }

    function test_DelegateFromDelegation_RevertNotDelegatedAgent() public {
        bytes32 parentId = _createRootDelegation();
        vm.prank(subAgent);
        vm.expectRevert("Not delegated agent");
        delegationRegistry.delegateFromDelegation(parentId, _narrowScope(), subAgent);
    }

    function test_DelegateFromDelegation_RevertAlreadyExecuted() public {
        bytes32 parentId = _createRootDelegation();

        // Mark executed via the gate
        vm.prank(address(executionGate));
        delegationRegistry.markExecuted(parentId);

        vm.prank(agent);
        vm.expectRevert("Already executed");
        delegationRegistry.delegateFromDelegation(parentId, _narrowScope(), subAgent);
    }

    function test_DelegateFromDelegation_RevertAmountExceedsParent() public {
        bytes32 parentId = _createRootDelegation(); // maxAmountIn = 0.5 ether
        DelegationRegistry.Scope memory scope = _narrowScope();
        scope.maxAmountIn = 0.6 ether;
        vm.prank(agent);
        vm.expectRevert("Amount exceeds root");
        delegationRegistry.delegateFromDelegation(parentId, scope, subAgent);
    }

    function test_DelegateFromDelegation_RevertProtocolsNotSubset() public {
        bytes32 parentId = _createRootDelegation(); // only uniswap-v3
        DelegationRegistry.Scope memory scope = _narrowScope();
        bytes32[] memory bad = new bytes32[](1);
        bad[0] = CURVE; // not in parent scope
        scope.allowedProtocols = bad;
        vm.prank(agent);
        vm.expectRevert("Protocols not subset");
        delegationRegistry.delegateFromDelegation(parentId, scope, subAgent);
    }

    // -------------------------------------------------------------------------
    // setExecutionGate / markExecuted
    // -------------------------------------------------------------------------

    function test_SetExecutionGate_RevertNotOwner() public {
        DelegationRegistry fresh = new DelegationRegistry(address(intentRegistry), address(agentRegistry));
        vm.prank(agent);
        vm.expectRevert("Not owner");
        fresh.setExecutionGate(makeAddr("gate"));
    }

    function test_SetExecutionGate_RevertAlreadySet() public {
        // delegationRegistry already has executionGate set in setUp
        vm.expectRevert("Already set");
        delegationRegistry.setExecutionGate(makeAddr("gate2"));
    }

    function test_MarkExecuted_RevertNotGate() public {
        bytes32 parentId = _createRootDelegation();
        vm.prank(agent);
        vm.expectRevert("Not execution gate");
        delegationRegistry.markExecuted(parentId);
    }

    function test_MarkExecuted_SetsFlag() public {
        bytes32 parentId = _createRootDelegation();
        vm.prank(address(executionGate));
        delegationRegistry.markExecuted(parentId);
        assertTrue(delegationRegistry.getDelegation(parentId).executed);
    }
}
