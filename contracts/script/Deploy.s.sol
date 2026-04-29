// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/AgentRegistry.sol";
import "../src/IntentRegistry.sol";
import "../src/DelegationRegistry.sol";
import "../src/ExecutionGate.sol";

contract Deploy is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        vm.startBroadcast(deployerKey);

        AgentRegistry agentRegistry         = new AgentRegistry();
        IntentRegistry intentRegistry       = new IntentRegistry();
        DelegationRegistry delegationRegistry = new DelegationRegistry(address(intentRegistry), address(agentRegistry));
        ExecutionGate executionGate         = new ExecutionGate(address(intentRegistry), address(delegationRegistry));

        delegationRegistry.setExecutionGate(address(executionGate));

        // Register demo agents — skipped if the address env vars are not set
        address orchAddr = vm.envOr("ORCHESTRATOR_ADDRESS", address(0));
        if (orchAddr != address(0)) agentRegistry.registerAgent(orchAddr, "Orchestrator");

        address researchAddr = vm.envOr("RESEARCH_ADDRESS", address(0));
        if (researchAddr != address(0)) agentRegistry.registerAgent(researchAddr, "ResearchAgent");

        address execAddr = vm.envOr("EXECUTION_ADDRESS", address(0));
        if (execAddr != address(0)) agentRegistry.registerAgent(execAddr, "ExecutionAgent");

        vm.stopBroadcast();

        console.log("AGENT_REGISTRY_ADDRESS      =", address(agentRegistry));
        console.log("INTENT_REGISTRY_ADDRESS     =", address(intentRegistry));
        console.log("DELEGATION_REGISTRY_ADDRESS =", address(delegationRegistry));
        console.log("EXECUTION_GATE_ADDRESS      =", address(executionGate));

        string memory json = string.concat(
            '{\n',
            '  "agentRegistry": "',        vm.toString(address(agentRegistry)),        '",\n',
            '  "intentRegistry": "',       vm.toString(address(intentRegistry)),       '",\n',
            '  "delegationRegistry": "',   vm.toString(address(delegationRegistry)),   '",\n',
            '  "executionGate": "',        vm.toString(address(executionGate)),        '"\n',
            '}'
        );
        vm.writeFile("../config/deployed.json", json);
        console.log("Addresses written to config/deployed.json");
    }
}
