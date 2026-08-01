// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract YieldVault {
    mapping(address => uint256) public deposits;
    mapping(address => uint256) public yieldAccrued;
    uint256 public totalDeposits;
    uint256 public yieldBps = 200;

    receive() external payable {}

    function fund() external payable {
        require(msg.value > 0, "no value");
        deposits[msg.sender] += msg.value;
        totalDeposits += msg.value;
        yieldAccrued[msg.sender] += (msg.value * yieldBps) / 10000;
    }

    function redeem(uint256 amount) external {
        require(deposits[msg.sender] >= amount, "insufficient");
        uint256 yield = yieldAccrued[msg.sender];
        uint256 payout = amount + yield;
        (bool ok,) = payable(msg.sender).call{value: payout}("");
        require(ok, "transfer failed");
        deposits[msg.sender] -= amount;
        totalDeposits -= amount;
        yieldAccrued[msg.sender] = 0;
    }
}
