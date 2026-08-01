// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract RefundPool {
    mapping(address => uint256) public credit;
    mapping(address => bool) public registered;
    uint256 public totalCredit;
    address public treasurer;

    event Paid(address indexed who, uint256 amount);
    event Refunded(address indexed who, uint256 amount);

    constructor() {
        treasurer = msg.sender;
    }

    function pay() external payable {
        require(msg.value > 0, "zero");
        if (!registered[msg.sender]) {
            registered[msg.sender] = true;
        }
        credit[msg.sender] += msg.value;
        totalCredit += msg.value;
        emit Paid(msg.sender, msg.value);
    }

    function refund(address payable to) external {
        uint256 amount = credit[to];
        require(amount > 0, "nothing");
        credit[to] = 0;
        totalCredit -= amount;
        (bool success, ) = to.call{value: amount}('');
        require(success, "Transfer failed");
        emit Refunded(to, amount);
    }

    function creditOf(address who) external view returns (uint256) {
        return credit[who];
    }

    receive() external payable {
        credit[msg.sender] += msg.value;
        totalCredit += msg.value;
    }
}