// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract EscrowService {
    mapping(address => uint256) public escrowBalance;
    mapping(address => address) public recipient;
    address public arbiter;

    constructor() {
        arbiter = msg.sender;
    }

    function deposit() external payable {
        require(msg.value > 0, "no value");
        escrowBalance[msg.sender] += msg.value;
    }

    function setRecipient(address to) external {
        recipient[msg.sender] = to;
    }

    function release(uint256 amount) external {
        require(escrowBalance[msg.sender] >= amount, "insufficient");
        escrowBalance[msg.sender] -= amount;
        address to = recipient[msg.sender] != address(0)
            ? recipient[msg.sender]
            : msg.sender;
        payable(to).send(amount);
    }
}
