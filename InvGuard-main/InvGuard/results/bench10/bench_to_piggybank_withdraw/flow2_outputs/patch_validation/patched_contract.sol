// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract PiggyBank {
    address public owner;
    uint256 public totalIn;
    uint256 public totalOut;
    mapping(address => uint256) public contributed;

    event Deposited(address indexed who, uint256 amount);
    event Withdrawn(address indexed to, uint256 amount);

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable {
        require(msg.value > 0, "zero");
        contributed[msg.sender] += msg.value;
        totalIn += msg.value;
        emit Deposited(msg.sender, msg.value);
    }

    function withdraw(address payable to, uint256 amount) external {
        require(msg.sender == owner, "not owner");
        require(address(this).balance >= amount, "insufficient");
        totalOut += amount;
        (bool ok, ) = to.call{value: amount}("");
        require(ok, "fail");
        emit Withdrawn(to, amount);
    }

    function balance() external view returns (uint256) {
        return address(this).balance;
    }

    function contributionOf(address who) external view returns (uint256) {
        return contributed[who];
    }
}