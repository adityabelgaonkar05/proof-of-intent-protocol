// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./IntentRegistry.sol";
import "./DelegationRegistry.sol";

contract ExecutionGate {
    address public intentRegistry;
    address public delegationRegistry;

    event IntentExecuted(
        bytes32 indexed delegationId,
        address indexed executor,
        uint256 timestamp
    );

    constructor(address _intentRegistry, address _delegationRegistry) {
        intentRegistry = _intentRegistry;
        delegationRegistry = _delegationRegistry;
    }

    function executeIntent(bytes32 delegationId) external returns (bool) {
        DelegationRegistry registry = DelegationRegistry(delegationRegistry);
        DelegationRegistry.Delegation memory delegation = registry.getDelegation(delegationId);

        require(msg.sender == delegation.delegatedTo, "Not authorized agent");
        require(!delegation.executed, "Already executed");
        require(delegation.scope.deadline >= block.timestamp, "Deadline passed");

        registry.markExecuted(delegationId);

        emit IntentExecuted(delegationId, msg.sender, block.timestamp);
        return true;
    }
}
