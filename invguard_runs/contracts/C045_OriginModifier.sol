pragma solidity ^0.8.20;

contract OriginModifier {
    address public owner;
    uint256 public limit = 1 ether;

    modifier onlyOwner() {
        require(tx.origin == owner, "not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {}

    function setLimit(uint256 l) external onlyOwner {
        limit = l;
    }

    function send(address payable to, uint256 amount) external onlyOwner {
        require(amount <= limit, "limit");
        to.transfer(amount);
    }
}
