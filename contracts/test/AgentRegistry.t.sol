// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/AgentRegistry.sol";

contract AgentRegistryTest is Test {
    AgentRegistry public registry;
    address internal alice;

    function setUp() public {
        registry = new AgentRegistry();
        alice    = makeAddr("alice");
    }

    function test_RegisterAgent() public {
        registry.registerAgent(alice, "alice");
        assertTrue(registry.isActiveAgent(alice));
    }

    function test_FreezeAgent() public {
        registry.registerAgent(alice, "alice");
        registry.freezeAgent(alice);
        assertFalse(registry.isActiveAgent(alice));
    }

    function test_UnfreezeAgent() public {
        registry.registerAgent(alice, "alice");
        registry.freezeAgent(alice);
        registry.unfreezeAgent(alice);
        assertTrue(registry.isActiveAgent(alice));
    }

    function test_RegisterDuplicate() public {
        registry.registerAgent(alice, "alice");
        vm.expectRevert("Already registered");
        registry.registerAgent(alice, "alice-again");
    }
}
