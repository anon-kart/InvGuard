// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract PointsLedger {
    mapping(address => uint256) public points;
    mapping(address => uint256) public level;
    uint256 public totalPoints;
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable {
        require(msg.value > 0, "no value");
        unchecked {
            points[msg.sender] += msg.value * 100;
            totalPoints += msg.value * 100;
        }
    }

    function awardBonus(uint256 amount) external {
        unchecked {
            points[msg.sender] += amount;
            totalPoints += amount;
        }
    }

    function withdraw(uint256 amount) external {
        require(points[msg.sender] / 100 >= amount, "not enough points");
        unchecked {
            points[msg.sender] -= amount * 100;
            totalPoints -= amount * 100;
        }
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        require(ok, "transfer failed");
    }
}
