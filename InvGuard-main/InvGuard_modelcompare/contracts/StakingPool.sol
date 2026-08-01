// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract StakingPool {
    mapping(address => uint256) public stakedAmount;
    mapping(address => uint256) public pendingRewards;
    uint256 public totalStaked;
    uint256 public rewardRate = 100;
    address public owner;

    constructor() payable {
        owner = msg.sender;
    }

    receive() external payable {}

    function stake() external payable {
        require(msg.value > 0, "no value");
        stakedAmount[msg.sender] += msg.value;
        totalStaked += msg.value;
        pendingRewards[msg.sender] += msg.value / rewardRate;
    }

    function unstake(uint256 amount) external {
        require(stakedAmount[msg.sender] >= amount, "insufficient stake");
        uint256 reward = pendingRewards[msg.sender];
        uint256 total = amount + reward;
        (bool ok,) = payable(msg.sender).call{value: total}("");
        require(ok, "transfer failed");
        stakedAmount[msg.sender] -= amount;
        totalStaked -= amount;
        pendingRewards[msg.sender] = 0;
    }
}
