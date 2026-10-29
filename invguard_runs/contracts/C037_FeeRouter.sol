pragma solidity ^0.8.20;

contract FeeRouter {
    address public owner;
    address public operator;
    uint256 public feeBps = 100;

    constructor(address op) {
        owner = msg.sender;
        operator = op;
    }

    receive() external payable {}

    function setOperator(address op) external {
        require(msg.sender == owner, "owner");
        operator = op;
    }

    function setFee(uint256 bps) external {
        require(bps <= 1000, "cap");
        feeBps = bps;
    }

    function payOut(address payable to, uint256 amount) external {
        require(msg.sender == owner || msg.sender == operator, "role");
        to.transfer(amount - amount * feeBps / 10000);
    }
}
