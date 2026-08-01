// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract VulnerableTxOrigin {
    address public owner;
    uint256 public totalFunds;
    mapping(address => uint256) public balances;

    constructor() payable {
        owner = msg.sender;
        totalFunds = msg.value;
    }

    receive() external payable {
        totalFunds += msg.value;
    }

    function deposit() external payable {
        require(msg.value > 0, "no value");
        balances[msg.sender] += msg.value;
        totalFunds += msg.value;
    }

    function transferOwnership(address newOwner) external {
        require(tx.origin == owner, "not owner");
        owner = newOwner;
    }

    function withdraw(uint256 amount) external {
        require(tx.origin == owner, "not owner");
        require(address(this).balance >= amount, "insufficient");
        totalFunds -= amount;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        require(ok, "transfer failed");
    }

    function setOwner(address newOwner) external {
        require(msg.sender == owner, "not owner");
        owner = newOwner;
    }
}