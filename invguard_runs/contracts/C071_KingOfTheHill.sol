pragma solidity ^0.4.24;

contract KingOfTheHill {
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
}
