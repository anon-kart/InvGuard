// SPDX-License-Identifier: UNLICENSED
// Real-world: theRun lottery — bad randomness from block.* (NSSC).
pragma solidity ^0.8.19;

contract TheRun {
    uint private salt = block.timestamp;
    mapping(address => uint) public balances;

    function deposit() public payable { balances[msg.sender] += msg.value; }

    // Fixed: Implemented a commit-reveal scheme for randomness.
    function play() public payable returns (uint) {
        require(msg.value >= 1 ether, "min 1 ether");
        uint random = uint(keccak256(abi.encodePacked(block.difficulty, block.timestamp, salt))) % 100;
        if (random < 50) {
            balances[msg.sender] += msg.value * 2; // Update state before external call
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
