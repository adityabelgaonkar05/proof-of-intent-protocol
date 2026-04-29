// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./IntentRegistry.sol";
import "./DelegationRegistry.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract ExecutionGate {
    address public intentRegistry;
    address public delegationRegistry;
    address public owner;

    struct TxParams {
        uint256 amountIn;
        uint256 minAmountOut;
        bytes32 protocol;
        address tokenIn;
        address tokenOut;
        address recipient;
    }

    event SwapExecuted(bytes32 indexed delegationId, uint256 amountIn, address recipient);
    // ChainVerificationFailed is emitted in the catch block of executeSwap.
    // Because executeSwap reverts after emitting it, the event is NOT persisted
    // on-chain — it exists as a diagnostic marker for off-chain simulation tools.
    event ChainVerificationFailed(bytes32 indexed delegationId, string reason);

    constructor(address _intentRegistry, address _delegationRegistry) {
        intentRegistry = _intentRegistry;
        delegationRegistry = _delegationRegistry;
        owner = msg.sender;
    }

    // -------------------------------------------------------------------------
    // Chain verification
    // -------------------------------------------------------------------------

    function verifyChain(bytes32 delegationId, TxParams calldata params)
        public
        view
        returns (bool)
    {
        bytes32 current = delegationId;

        while (true) {
            DelegationRegistry.Delegation memory d =
                DelegationRegistry(delegationRegistry).getDelegation(current);

            require(params.amountIn <= d.scope.maxAmountIn, "Amount exceeds scope");
            require(params.minAmountOut >= d.scope.minAmountOut, "MinOut below scope");
            require(block.timestamp <= d.scope.deadline, "Deadline passed");
            require(
                _protocolAllowed(params.protocol, d.scope.allowedProtocols),
                "Protocol not allowed"
            );

            // Advance before breaking so `current` holds the rootIntentId after the loop.
            current = d.parentId;
            if (d.isRootIntent) break;
        }

        // current is now rootIntentId
        IntentRegistry.Intent memory intent =
            IntentRegistry(intentRegistry).getIntent(current);

        require(params.amountIn <= intent.maxAmountIn, "Exceeds root intent");
        require(params.tokenIn == intent.tokenIn, "Wrong token");
        require(block.timestamp <= intent.deadline, "Root deadline passed");

        return true;
    }

    // -------------------------------------------------------------------------
    // Swap execution
    // -------------------------------------------------------------------------

    function executeSwap(bytes32 delegationId, TxParams calldata params) external {
        DelegationRegistry registry = DelegationRegistry(delegationRegistry);
        DelegationRegistry.Delegation memory delegation = registry.getDelegation(delegationId);

        require(msg.sender == delegation.delegatedTo, "Not authorized");
        require(!delegation.executed, "Already executed");

        try this.verifyChain(delegationId, params) {
            registry.markExecuted(delegationId);
            emit SwapExecuted(delegationId, params.amountIn, params.recipient);
            // Production: call the DEX router here using params.tokenIn/tokenOut/amountIn.
        } catch Error(string memory reason) {
            emit ChainVerificationFailed(delegationId, reason);
            revert(reason);
        } catch {
            emit ChainVerificationFailed(delegationId, "Unknown verification error");
            revert("Chain verification failed");
        }
    }

    // -------------------------------------------------------------------------
    // Internals
    // -------------------------------------------------------------------------

    function _protocolAllowed(bytes32 protocol, bytes32[] memory allowed)
        internal
        pure
        returns (bool)
    {
        for (uint256 i = 0; i < allowed.length; i++) {
            if (allowed[i] == protocol) return true;
        }
        return false;
    }
}
