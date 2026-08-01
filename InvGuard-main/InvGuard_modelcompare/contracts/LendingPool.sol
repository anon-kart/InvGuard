pragma solidity ^0.8.19;

contract LendingPool {
    mapping(address => uint256) public collateral;
    mapping(address => uint256) public debt;
    uint256 public totalCollateral;
    uint256 public totalDebt;
    uint256 public interestRateBps = 500;  
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {}

    function addCollateral() external payable {
        require(msg.value > 0, "no value");
        collateral[msg.sender] += msg.value;
        totalCollateral += msg.value;
    }

    function borrow(uint256 amount) external {
        require(amount > 0, "zero amount");
        uint256 maxBorrow = (collateral[msg.sender] * 7500) / 10000;  
        require(debt[msg.sender] + amount <= maxBorrow, "exceeds LTV");
        require(address(this).balance >= amount, "insufficient liquidity");

        (bool ok,) = payable(msg.sender).call{value: amount}("");
        require(ok, "transfer failed");

        unchecked {
            debt[msg.sender] += amount;
            totalDebt += amount;
        }
    }

    function repay() external payable {
        require(msg.value > 0, "no value");
        uint256 d = debt[msg.sender];
        require(d > 0, "no debt");
        uint256 repayAmount = msg.value <= d ? msg.value : d;
        debt[msg.sender] -= repayAmount;
        totalDebt -= repayAmount;
    }

    function withdrawCollateral(uint256 amount) external {
        require(debt[msg.sender] == 0, "repay debt first");
        require(collateral[msg.sender] >= amount, "insufficient collateral");
        collateral[msg.sender] -= amount;
        totalCollateral -= amount;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        require(ok, "transfer failed");
    }

    function setInterestRate(uint256 newRateBps) external {
        require(msg.sender == owner, "not owner");
        require(newRateBps <= 2000, "too high");
        interestRateBps = newRateBps;
    }
}