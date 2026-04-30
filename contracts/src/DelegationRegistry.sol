// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./IntentRegistry.sol";
import "./AgentRegistry.sol";

contract DelegationRegistry {
    struct Scope {
        uint256 maxAmountIn;
        uint256 minAmountOut;
        bytes32[] allowedProtocols;
        uint256 deadline;
    }

    struct Delegation {
        bytes32 parentId;
        bool isRootIntent;
        Scope scope;
        address delegatedTo;
        bool executed;
    }

    mapping(bytes32 => Delegation) public delegations;
    mapping(bytes32 => bool) public delegationExists;
    mapping(bytes32 => bool) public delegationUsed;
    address public intentRegistry;
    address public agentRegistry;
    address public executionGate;
    address private _owner;

    event DelegationCreated(
        bytes32 indexed delegationId,
        bytes32 indexed parentId,
        address indexed delegatedTo
    );

    constructor(address _intentRegistry, address _agentRegistry) {
        intentRegistry = _intentRegistry;
        agentRegistry = _agentRegistry;
        _owner = msg.sender;
    }

    function setExecutionGate(address _executionGate) external {
        require(msg.sender == _owner, "Not owner");
        require(executionGate == address(0), "Already set");
        executionGate = _executionGate;
    }

    function delegateFromRoot(
        bytes32 rootIntentId,
        Scope calldata childScope,
        address delegateTo
    ) external returns (bytes32 delegationId) {
        IntentRegistry.Intent memory intent = IntentRegistry(intentRegistry).getIntent(rootIntentId);
        require(msg.sender == intent.authorizedOrchestrator, "Not authorized orchestrator");
        require(AgentRegistry(agentRegistry).isActiveAgent(delegateTo), "Target not registered agent");
        require(childScope.maxAmountIn <= intent.maxAmountIn, "Amount exceeds root");
        require(childScope.minAmountOut >= intent.minAmountOut, "MinOut below root");
        require(childScope.deadline <= intent.deadline, "Deadline exceeds root");
        require(
            _isSubset(childScope.allowedProtocols, intent.allowedProtocols),
            "Protocols not subset"
        );

        delegationId = keccak256(abi.encode(rootIntentId, childScope.maxAmountIn, childScope.minAmountOut, childScope.allowedProtocols, childScope.deadline, delegateTo, block.timestamp));

        require(!delegationUsed[rootIntentId], "Root already delegated");
        delegationUsed[rootIntentId] = true;

        delegations[delegationId] = Delegation({
            parentId: rootIntentId,
            isRootIntent: true,
            scope: childScope,
            delegatedTo: delegateTo,
            executed: false
        });
        delegationExists[delegationId] = true;

        emit DelegationCreated(delegationId, rootIntentId, delegateTo);
    }

    function delegateFromDelegation(
        bytes32 parentDelegationId,
        Scope calldata childScope,
        address delegateTo
    ) external returns (bytes32 delegationId) {
        require(delegationExists[parentDelegationId], "Parent not found");
        Delegation storage delegation = delegations[parentDelegationId];
        require(msg.sender == delegation.delegatedTo, "Not delegated agent");
        require(AgentRegistry(agentRegistry).isActiveAgent(delegateTo), "Target not registered agent");
        require(!delegation.executed, "Already executed");

        Scope storage parentScope = delegation.scope;
        require(childScope.maxAmountIn <= parentScope.maxAmountIn, "Amount exceeds scope");
        require(childScope.minAmountOut >= parentScope.minAmountOut, "MinOut below scope");
        require(childScope.deadline <= parentScope.deadline, "Deadline exceeds scope");
        require(
            _isSubset(childScope.allowedProtocols, parentScope.allowedProtocols),
            "Protocols not subset"
        );

        delegationId = keccak256(abi.encode(parentDelegationId, childScope.maxAmountIn, childScope.minAmountOut, childScope.allowedProtocols, childScope.deadline, delegateTo, block.timestamp));

        require(!delegationUsed[parentDelegationId], "Already sub-delegated");
        delegationUsed[parentDelegationId] = true;

        delegations[delegationId] = Delegation({
            parentId: parentDelegationId,
            isRootIntent: false,
            scope: childScope,
            delegatedTo: delegateTo,
            executed: false
        });
        delegationExists[delegationId] = true;

        emit DelegationCreated(delegationId, parentDelegationId, delegateTo);
    }

    function _isSubset(bytes32[] memory child, bytes32[] memory parent) internal pure returns (bool) {
        for (uint256 i = 0; i < child.length; i++) {
            bool found = false;
            for (uint256 j = 0; j < parent.length; j++) {
                if (child[i] == parent[j]) {
                    found = true;
                    break;
                }
            }
            if (!found) return false;
        }
        return true;
    }

    function getDelegation(bytes32 delegationId) external view returns (Delegation memory) {
        return delegations[delegationId];
    }

    function markExecuted(bytes32 delegationId) external {
        require(msg.sender == executionGate, "Not execution gate");
        delegations[delegationId].executed = true;
    }
}
