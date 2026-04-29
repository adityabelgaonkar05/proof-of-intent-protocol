// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/IntentRegistry.sol";
import "../src/DelegationRegistry.sol";
import "../src/ExecutionGate.sol";

contract ExecutionGateTest is Test {
    IntentRegistry public intentRegistry;
    DelegationRegistry public delegationRegistry;
    ExecutionGate public executionGate;

    uint256 internal ownerKey = 0xA11CE;
    address internal owner;
    address internal agent;

    bytes32 internal intentId;
    bytes32 internal delegationId;

    function setUp() public {
        intentRegistry = new IntentRegistry();
        delegationRegistry = new DelegationRegistry(address(intentRegistry));
        executionGate = new ExecutionGate(address(intentRegistry), address(delegationRegistry));
        delegationRegistry.setExecutionGate(address(executionGate));

        owner = vm.addr(ownerKey);
        agent = makeAddr("agent");

        bytes32[] memory protocols = new bytes32[](1);
        protocols[0] = keccak256("uniswap-v3");

        IntentRegistry.Intent memory intent = IntentRegistry.Intent({
            owner: owner,
            tokenIn: address(0x1234),
            maxAmountIn: 1 ether,
            minAmountOut: 0.95 ether,
            allowedProtocols: protocols,
            deadline: block.timestamp + 1 hours,
            nonce: 0
        });

        bytes32 typehash = keccak256(
            "Intent(address owner,address tokenIn,uint256 maxAmountIn,uint256 minAmountOut,bytes32[] allowedProtocols,uint256 deadline,uint256 nonce)"
        );
        bytes32 structHash = keccak256(abi.encode(
            typehash,
            intent.owner,
            intent.tokenIn,
            intent.maxAmountIn,
            intent.minAmountOut,
            keccak256(abi.encodePacked(intent.allowedProtocols)),
            intent.deadline,
            intent.nonce
        ));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", intentRegistry.DOMAIN_SEPARATOR(), structHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(ownerKey, digest);

        intentId = intentRegistry.registerIntent(intent, abi.encodePacked(r, s, v));

        DelegationRegistry.Scope memory scope = DelegationRegistry.Scope({
            maxAmountIn: 0.5 ether,
            minAmountOut: 0.97 ether,
            allowedProtocols: protocols,
            deadline: block.timestamp + 30 minutes
        });

        vm.prank(owner);
        delegationId = delegationRegistry.delegateFromRoot(intentId, scope, agent);
    }

    // -------------------------------------------------------------------------
    // executeIntent — happy path
    // -------------------------------------------------------------------------

    function test_ExecuteIntent_Succeeds() public {
        vm.prank(agent);
        bool ok = executionGate.executeIntent(delegationId);
        assertTrue(ok);
    }

    function test_ExecuteIntent_MarksExecuted() public {
        vm.prank(agent);
        executionGate.executeIntent(delegationId);
        assertTrue(delegationRegistry.getDelegation(delegationId).executed);
    }

    function test_ExecuteIntent_EmitsEvent() public {
        vm.expectEmit(true, true, false, true);
        emit ExecutionGate.IntentExecuted(delegationId, agent, block.timestamp);
        vm.prank(agent);
        executionGate.executeIntent(delegationId);
    }

    // -------------------------------------------------------------------------
    // executeIntent — reverts
    // -------------------------------------------------------------------------

    function test_ExecuteIntent_RevertNotAuthorized() public {
        vm.prank(makeAddr("random"));
        vm.expectRevert("Not authorized agent");
        executionGate.executeIntent(delegationId);
    }

    function test_ExecuteIntent_RevertAlreadyExecuted() public {
        vm.prank(agent);
        executionGate.executeIntent(delegationId);

        vm.prank(agent);
        vm.expectRevert("Already executed");
        executionGate.executeIntent(delegationId);
    }

    function test_ExecuteIntent_RevertDeadlinePassed() public {
        vm.warp(block.timestamp + 2 hours);
        vm.prank(agent);
        vm.expectRevert("Deadline passed");
        executionGate.executeIntent(delegationId);
    }

    // -------------------------------------------------------------------------
    // Contract addresses set correctly
    // -------------------------------------------------------------------------

    function test_AddressesSetInConstructor() public view {
        assertEq(executionGate.intentRegistry(), address(intentRegistry));
        assertEq(executionGate.delegationRegistry(), address(delegationRegistry));
    }
}
