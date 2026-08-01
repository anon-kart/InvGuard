// SPDX-License-Identifier: UNLICENSED
// Real-world: theRun lottery — bad randomness from block.* (NSSC).
pragma solidity ^0.8.19;

contract TheRun {
    uint private salt = block.timestamp;
    mapping(address => uint) public balances;

    function deposit() public payable { balances[msg.sender] += msg.value; }

    // BUG: "random" winner derived from manipulable block values; an attacker
    // contract can compute the same value in the same block and always win.
    function play() public payable returns (uint) {
        require(msg.value >= 1 ether, "min 1 ether");
        uint random = uint(keccak256(abi.encodePacked(msg.sender, block.difficulty, block.timestamp, salt))) % 100;
        if (random < 50) {
            balances[msg.sender] += msg.value * 2; // Update state before external call
            payable(msg.sender).transfer(msg.value * 2);
        }
        return random;
    }

    receive() external payable {}
}