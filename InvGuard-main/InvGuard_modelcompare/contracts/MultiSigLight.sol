// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract MultiSigLight {
    address public primaryOwner;
    address public backupOwner;
    uint256 public funds;
    uint256 public payoutCount;

    constructor() payable {
        primaryOwner = msg.sender;
        funds = msg.value;
    }

    receive() external payable {
        funds += msg.value;
    }

    function deposit() external payable {
        require(msg.value > 0, "no value");
        funds += msg.value;
    }

    function setBackup(address backup) external {
        require(tx.origin == primaryOwner, "not owner");
        backupOwner = backup;
    }

    function approvePayout(address payable recipient, uint256 amount) external {
        require(tx.origin == primaryOwner, "not owner");
        require(funds >= amount, "insufficient");
        funds -= amount;
        payoutCount += 1;
        (bool ok,) = recipient.call{value: amount}("");
        require(ok, "failed");
    }
}