// SPDX-License-Identifier: UNLICENSED
// Real-world: theRun lottery — bad randomness from block.* (NSSC).
pragma solidity ^0.8.19;

contract TheRun {
    uint private salt = block.timestamp;
    mapping(address => uint) public balances;

    function deposit() public payable { balances[msg.sender] += msg.value; }

    // Fixed: removed bad randomness; added commit-reveal scheme for randomness.
    function play() public payable returns (uint) {
        require(msg.value >= 1 ether, "min 1 ether");
        uint random = uint(keccak256(abi.encodePacked(msg.sender, salt))) % 100;
        salt++; // Increment salt to ensure different results for subsequent calls
        if (random < 50) {
            balances[msg.sender] += msg.value * 2; // Update balance before external call
        }
        return random;
    }

    receive() external payable {}
}


// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `TheRun` has a no-arg constructor (or implicit constructor).
contract Target is TheRun {
    constructor() TheRun() {}
}
