// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract SplitPayment {
    mapping(address => uint256) public shares;
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable {
        require(msg.value > 0, "no value");
        shares[msg.sender] += msg.value;
    }

    function payout(address payable payee, uint256 amount) external {
        require(shares[payee] >= amount, "insufficient share");
        shares[payee] -= amount;
        payable(payee).send(amount);
    }
}