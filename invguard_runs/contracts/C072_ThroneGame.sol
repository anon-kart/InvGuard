pragma solidity ^0.4.24;

contract ThroneGame {
    address public king;
    uint256 public prize;
    address public owner;

    constructor() public payable {
        owner = msg.sender;
        king = msg.sender;
        prize = msg.value;
    }

    function() external payable {
        require(msg.value >= prize || msg.sender == owner);
        king.transfer(msg.value);
        king = msg.sender;
        prize = msg.value;
    }

    function version() public pure returns (uint256) {
        return 2;
    }
}
