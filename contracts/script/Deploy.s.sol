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

        console.log("INTENT_REGISTRY_ADDRESS   =", address(intentRegistry));
        console.log("DELEGATION_REGISTRY_ADDRESS =", address(delegationRegistry));
        console.log("EXECUTION_GATE_ADDRESS      =", address(executionGate));

        string memory json = string.concat(
            '{\n',
            '  "intentRegistry": "',      vm.toString(address(intentRegistry)),      '",\n',
            '  "delegationRegistry": "',  vm.toString(address(delegationRegistry)),  '",\n',
            '  "executionGate": "',       vm.toString(address(executionGate)),       '"\n',
            '}'
        );
        vm.writeFile("../config/deployed.json", json);
        console.log("Addresses written to config/deployed.json");
    }
}
