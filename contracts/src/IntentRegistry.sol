// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/EIP712.sol";

contract IntentRegistry is EIP712 {
    using ECDSA for bytes32;

    struct Intent {
        address owner;
        address tokenIn;
        uint256 maxAmountIn;
        uint256 minAmountOut;
        bytes32[] allowedProtocols;
        uint256 deadline;
        uint256 nonce;
    }

    bytes32 private constant INTENT_TYPEHASH = keccak256(
        "Intent(address owner,address tokenIn,uint256 maxAmountIn,uint256 minAmountOut,bytes32[] allowedProtocols,uint256 deadline,uint256 nonce)"
    );

    mapping(bytes32 => Intent) public intents;
    mapping(bytes32 => bool) public intentExists;
    mapping(address => uint256) public nonces;

    event IntentRegistered(
        bytes32 indexed intentId,
        address indexed owner,
        uint256 maxAmountIn,
        uint256 deadline
    );

    constructor() EIP712("IntentRegistry", "1") {}

    function registerIntent(Intent calldata intent, bytes calldata signature)
        external
        returns (bytes32 intentId)
    {
        require(intent.deadline > block.timestamp, "Deadline passed");
        require(intent.maxAmountIn > 0, "Zero amount");

        bytes32 structHash = keccak256(abi.encode(
            INTENT_TYPEHASH,
            intent.owner,
            intent.tokenIn,
            intent.maxAmountIn,
            intent.minAmountOut,
            keccak256(abi.encodePacked(intent.allowedProtocols)),
            intent.deadline,
            intent.nonce
        ));

        bytes32 digest = _hashTypedDataV4(structHash);
        address signer = ECDSA.recover(digest, signature);
        require(signer == intent.owner, "Invalid signature");

        intentId = keccak256(abi.encode(intent));
        intents[intentId] = intent;
        intentExists[intentId] = true;
        nonces[intent.owner]++;

        emit IntentRegistered(intentId, intent.owner, intent.maxAmountIn, intent.deadline);
    }

    function getIntent(bytes32 intentId) external view returns (Intent memory) {
        require(intentExists[intentId], "Intent not found");
        return intents[intentId];
    }

    function DOMAIN_SEPARATOR() external view returns (bytes32) {
        return _domainSeparatorV4();
    }
}
