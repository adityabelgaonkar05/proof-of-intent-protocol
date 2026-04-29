// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/IntentRegistry.sol";
import "../src/AgentRegistry.sol";
import "../src/DelegationRegistry.sol";

bytes32 constant UNISWAP_V3 = keccak256(abi.encodePacked("Uniswap-V3"));
bytes32 constant CURVE       = keccak256(abi.encodePacked("Curve"));

contract IntentRegistryTest is Test {
    IntentRegistry public registry;

    uint256 internal userKey = 0xA11CE;
    address internal user;

    function setUp() public {
        registry = new IntentRegistry();
        user = vm.addr(userKey);
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    function _buildIntent() internal view returns (IntentRegistry.Intent memory) {
        bytes32[] memory protocols = new bytes32[](2);
        protocols[0] = UNISWAP_V3;
        protocols[1] = CURVE;

        return IntentRegistry.Intent({
            owner: user,
            authorizedOrchestrator: address(0xC0FFEE),
            tokenIn: address(0x1234),
            maxAmountIn: 1 ether,
            minAmountOut: 0.95 ether,
            allowedProtocols: protocols,
            deadline: block.timestamp + 1 hours,
            nonce: registry.nonces(user)
        });
    }

    function _sign(IntentRegistry.Intent memory intent) internal view returns (bytes memory) {
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
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", registry.DOMAIN_SEPARATOR(), structHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(userKey, digest);
        return abi.encodePacked(r, s, v);
    }

    // -------------------------------------------------------------------------
    // registerIntent — happy path
    // -------------------------------------------------------------------------

    function test_RegisterIntent_Succeeds() public {
        IntentRegistry.Intent memory intent = _buildIntent();
        bytes32 intentId = registry.registerIntent(intent, _sign(intent));

        assertTrue(registry.intentExists(intentId));
        IntentRegistry.Intent memory stored = registry.getIntent(intentId);
        assertEq(stored.owner, user);
        assertEq(stored.maxAmountIn, 1 ether);
        assertEq(stored.minAmountOut, 0.95 ether);
        assertEq(stored.deadline, intent.deadline);
    }

    function test_RegisterIntent_IncrementsNonce() public {
        uint256 before = registry.nonces(user);
        IntentRegistry.Intent memory intent = _buildIntent();
        registry.registerIntent(intent, _sign(intent));
        assertEq(registry.nonces(user), before + 1);
    }

    function test_RegisterIntent_EmitsEvent() public {
        IntentRegistry.Intent memory intent = _buildIntent();
        bytes32 intentId = keccak256(abi.encode(intent));

        vm.expectEmit(true, true, false, true);
        emit IntentRegistry.IntentRegistered(intentId, user, address(0xC0FFEE), 1 ether, intent.deadline);
        registry.registerIntent(intent, _sign(intent));
    }

    function test_RegisterIntent_SetsIntentExists() public {
        IntentRegistry.Intent memory intent = _buildIntent();
        bytes32 intentId = registry.registerIntent(intent, _sign(intent));
        assertTrue(registry.intentExists(intentId));
    }

    // -------------------------------------------------------------------------
    // registerIntent — reverts
    // -------------------------------------------------------------------------

    function test_RegisterIntent_RevertExpiredDeadline() public {
        IntentRegistry.Intent memory intent = _buildIntent();
        intent.deadline = block.timestamp - 1;
        bytes memory sig = _sign(intent);
        vm.expectRevert("Deadline passed");
        registry.registerIntent(intent, sig);
    }

    function test_RegisterIntent_RevertZeroAmount() public {
        IntentRegistry.Intent memory intent = _buildIntent();
        intent.maxAmountIn = 0;
        bytes memory sig = _sign(intent);
        vm.expectRevert("Zero amount");
        registry.registerIntent(intent, sig);
    }

    function test_RegisterIntent_RevertInvalidSignature() public {
        IntentRegistry.Intent memory intent = _buildIntent();
        // Sign with a different key
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
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", registry.DOMAIN_SEPARATOR(), structHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(0xBEEF, digest);
        bytes memory badSig = abi.encodePacked(r, s, v);

        vm.expectRevert("Invalid signature");
        registry.registerIntent(intent, badSig);
    }

    // -------------------------------------------------------------------------
    // getIntent
    // -------------------------------------------------------------------------

    function test_GetIntent_ReturnsCorrectData() public {
        IntentRegistry.Intent memory intent = _buildIntent();
        bytes32 intentId = registry.registerIntent(intent, _sign(intent));

        IntentRegistry.Intent memory fetched = registry.getIntent(intentId);
        assertEq(fetched.owner, user);
        assertEq(fetched.tokenIn, address(0x1234));
        assertEq(fetched.nonce, 0);
    }

    function test_GetIntent_RevertNotFound() public {
        vm.expectRevert("Intent not found");
        registry.getIntent(bytes32(0));
    }

    // -------------------------------------------------------------------------
    // registerIntent — orchestrator field
    // -------------------------------------------------------------------------

    function test_RegisterIntent_RevertNoOrchestrator() public {
        IntentRegistry.Intent memory intent = _buildIntent();
        intent.authorizedOrchestrator = address(0);
        bytes memory sig = _sign(intent);
        vm.expectRevert("No orchestrator set");
        registry.registerIntent(intent, sig);
    }

    // -------------------------------------------------------------------------
    // revokeIntent
    // -------------------------------------------------------------------------

    function test_RevokeIntent() public {
        IntentRegistry.Intent memory intent = _buildIntent();
        bytes32 intentId = registry.registerIntent(intent, _sign(intent));

        vm.prank(user);
        registry.revokeIntent(intentId);

        assertFalse(registry.intentExists(intentId));
    }

    function test_RevokeIntent_RevertNotOwner() public {
        IntentRegistry.Intent memory intent = _buildIntent();
        bytes32 intentId = registry.registerIntent(intent, _sign(intent));

        vm.prank(makeAddr("attacker"));
        vm.expectRevert("Not owner");
        registry.revokeIntent(intentId);
    }

    function test_RevokedIntentBlocked() public {
        // Stand up a minimal DelegationRegistry to prove the revoked intent is rejected
        AgentRegistry agentReg = new AgentRegistry();
        DelegationRegistry delReg = new DelegationRegistry(address(registry), address(agentReg));

        address agent = makeAddr("agent");
        agentReg.registerAgent(agent, "agent");

        IntentRegistry.Intent memory intent = _buildIntent();
        bytes32 intentId = registry.registerIntent(intent, _sign(intent));

        vm.prank(user);
        registry.revokeIntent(intentId);

        bytes32[] memory protocols = new bytes32[](1);
        protocols[0] = UNISWAP_V3;
        DelegationRegistry.Scope memory scope = DelegationRegistry.Scope({
            maxAmountIn: 0.5 ether,
            minAmountOut: 0.97 ether,
            allowedProtocols: protocols,
            deadline: block.timestamp + 30 minutes
        });

        vm.prank(address(0xC0FFEE));
        vm.expectRevert("Intent not found");
        delReg.delegateFromRoot(intentId, scope, agent);
    }
}
