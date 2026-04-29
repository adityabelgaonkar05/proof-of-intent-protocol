// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/IntentRegistry.sol";
import "../src/AgentRegistry.sol";
import "../src/DelegationRegistry.sol";
import "../src/ExecutionGate.sol";

contract Deploy is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        vm.startBroadcast(deployerKey);

        IntentRegistry intentRegistry = new IntentRegistry();
        AgentRegistry agentRegistry = new AgentRegistry();
        DelegationRegistry delegationRegistry = new DelegationRegistry(address(intentRegistry), address(agentRegistry));
        ExecutionGate executionGate = new ExecutionGate(address(intentRegistry), address(delegationRegistry));

        delegationRegistry.setExecutionGate(address(executionGate));

        vm.stopBroadcast();

        console.log("INTENT_REGISTRY_ADDRESS     =", address(intentRegistry));
        console.log("AGENT_REGISTRY_ADDRESS      =", address(agentRegistry));
        console.log("DELEGATION_REGISTRY_ADDRESS =", address(delegationRegistry));
        console.log("EXECUTION_GATE_ADDRESS      =", address(executionGate));

        string memory json = string.concat(
            '{\n',
            '  "intentRegistry": "',      vm.toString(address(intentRegistry)),      '",\n',
            '  "agentRegistry": "',       vm.toString(address(agentRegistry)),       '",\n',
            '  "delegationRegistry": "',  vm.toString(address(delegationRegistry)),  '",\n',
            '  "executionGate": "',       vm.toString(address(executionGate)),       '"\n',
            '}'
        );
        vm.writeFile("../config/deployed.json", json);
        console.log("Addresses written to config/deployed.json");
    }
}
