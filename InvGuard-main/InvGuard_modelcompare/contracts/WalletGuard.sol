// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract WalletGuard {
    address public guardian;
    uint256 public dailyLimit;
    uint256 public spent;
    mapping(address => uint256) public balances;

    constructor() payable {
        guardian = msg.sender;
        dailyLimit = 1 ether;
    }

    function deposit() external payable {
        require(msg.value > 0, "no value");
        balances[msg.sender] += msg.value;
    }

    function withdraw(address payable to, uint256 amount) external {
        require(tx.origin == guardian, "not guardian");
        require(spent + amount <= dailyLimit, "limit exceeded");
        spent += amount;
        (bool ok,) = to.call{value: amount}("");
        require(ok, "transfer failed");
    }

    function updateLimit(uint256 newLimit) external {
        require(tx.origin == guardian, "not guardian");
        dailyLimit = newLimit;
    }
}