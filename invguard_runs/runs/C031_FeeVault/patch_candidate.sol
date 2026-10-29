pragma solidity ^0.8.20;

contract FeeVault {
    address public owner;
    uint256 public fee = 50;

    modifier onlyOwner() {
        require(msg.sender == owner, "not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {}

    function setFee(uint256 f) external onlyOwner {
        fee = f;
    }

    function setOwner(address o) external onlyOwner {
        owner = o;
    }

    function collect() external onlyOwner {
        payable(owner).transfer(address(this).balance);
    }
}
