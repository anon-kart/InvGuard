pragma solidity ^0.8.20;

interface IERC20Like {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
}

contract TokenBank {
    IERC20Like public immutable token;
    mapping(address => uint256) public deposited;

    constructor(IERC20Like t) {
        token = t;
    }

    function deposit(uint256 amount) external {
        token.transferFrom(msg.sender, address(this), amount);
        deposited[msg.sender] += amount;
    }

    function withdraw(uint256 amount) external {
        require(deposited[msg.sender] >= amount, "insufficient");
        deposited[msg.sender] -= amount;
        token.transfer(msg.sender, amount);
    }
}
