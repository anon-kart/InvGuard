// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract VulnerableOverflow {
    mapping(address => uint256) public balances;
    mapping(address => uint256) public rewards;
    uint256 public totalSupply;
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable {
        require(msg.value > 0, "no value");
        unchecked {
            balances[msg.sender] += msg.value;
            totalSupply += msg.value;
        }
    }

    function claimReward(uint256 amount) external {
        unchecked {
            rewards[msg.sender] += amount;
        }
    }

    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "insufficient");
        unchecked {
            balances[msg.sender] -= amount;
            totalSupply -= amount;
        }
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        require(ok, "transfer failed");
    }

    function transfer(address to, uint256 amount) external {
        require(balances[msg.sender] >= amount, "insufficient");
        unchecked {
            balances[msg.sender] -= amount;
            balances[to] += amount;
        }
    }
}