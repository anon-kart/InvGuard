// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract FeeCollector {
    mapping(address => uint256) public contributions;
    uint256 public totalFees;
    address public controller;
    uint256 public feeRate = 50;

    constructor() payable {
        controller = msg.sender;
        totalFees = msg.value;
    }

    receive() external payable {
        totalFees += msg.value;
    }

    function contribute() external payable {
        require(msg.value > 0, "no value");
        contributions[msg.sender] += msg.value;
        totalFees += msg.value;
    }

    function updateFeeRate(uint256 newRate) external {
        require(newRate <= 1000, "too high");
        feeRate = newRate;
    }

    function withdrawFees(address payable recipient) external {
        uint256 amount = address(this).balance;
        totalFees = 0;
        (bool ok,) = recipient.call{value: amount}("");
        require(ok, "transfer failed");
    }
}
