pragma solidity ^0.4.24;

contract ThroneGame {
    address public king;
    uint256 public prize;
    address public owner;
    mapping(address => uint256) public credit;

    constructor() public payable {
        owner = msg.sender;
        king = msg.sender;
        prize = msg.value;
    }

    function() external payable {
        require(msg.value >= prize || msg.sender == owner);
        credit[king] += msg.value;
        king = msg.sender;
        prize = msg.value;
    }

    function withdrawCredit() external {
        uint256 amount = credit[msg.sender];
        credit[msg.sender] = 0;
        msg.sender.transfer(amount);
    }

    function version() public pure returns (uint256) {
        return 2;
    }
}
