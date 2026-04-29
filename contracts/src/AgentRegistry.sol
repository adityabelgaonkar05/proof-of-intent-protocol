// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract AgentRegistry {
    struct Agent {
        string name;
        address owner;
        bool active;
        uint256 registeredAt;
    }

    mapping(address => Agent) public agents;
    mapping(address => bool) public isRegistered;

    event AgentRegistered(address indexed agentAddress, address indexed owner, string name);
    event AgentFrozen(address indexed agentAddress, address indexed by);
    event AgentUnfrozen(address indexed agentAddress, address indexed by);

    function registerAgent(address agentAddress, string calldata name) external {
        require(!isRegistered[agentAddress], "Already registered");
        require(agentAddress != address(0), "Zero address");
        agents[agentAddress] = Agent(name, msg.sender, true, block.timestamp);
        isRegistered[agentAddress] = true;
        emit AgentRegistered(agentAddress, msg.sender, name);
    }

    function freezeAgent(address agentAddress) external {
        require(agents[agentAddress].owner == msg.sender, "Not owner");
        agents[agentAddress].active = false;
        emit AgentFrozen(agentAddress, msg.sender);
    }

    function unfreezeAgent(address agentAddress) external {
        require(agents[agentAddress].owner == msg.sender, "Not owner");
        agents[agentAddress].active = true;
        emit AgentUnfrozen(agentAddress, msg.sender);
    }

    function isActiveAgent(address agentAddress) external view returns (bool) {
        return isRegistered[agentAddress] && agents[agentAddress].active;
    }
}
