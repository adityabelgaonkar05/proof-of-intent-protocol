// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/IntentRegistry.sol";
import "../src/DelegationRegistry.sol";
import "../src/ExecutionGate.sol";

contract Deploy is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        vm.startBroadcast(deployerKey);

        IntentRegistry intentRegistry = new IntentRegistry();
        DelegationRegistry delegationRegistry = new DelegationRegistry(address(intentRegistry));
        ExecutionGate executionGate = new ExecutionGate(address(intentRegistry), address(delegationRegistry));

        delegationRegistry.setExecutionGate(address(executionGate));

        vm.stopBroadcast();

        console.log("INTENT_REGISTRY_ADDRESS=%s", address(intentRegistry));
        console.log("DELEGATION_REGISTRY_ADDRESS=%s", address(delegationRegistry));
        console.log("EXECUTION_GATE_ADDRESS=%s", address(executionGate));
    }
}
