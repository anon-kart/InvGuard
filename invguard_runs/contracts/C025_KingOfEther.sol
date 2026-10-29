pragma solidity ^0.4.24;

contract KingOfEther {
    address public king;
    uint256 public claimPrice = 0.1 ether;
    address public owner;

    constructor() public {
        owner = msg.sender;
        king = msg.sender;
    }

    function claimThrone() public payable {
        require(msg.value >= claimPrice);
        uint256 compensation = msg.value * 9 / 10;
        king.send(compensation);
        king = msg.sender;
        claimPrice = msg.value * 3 / 2;
    }

    function sweepCommission(uint256 amount) public {
        require(msg.sender == owner);
        owner.send(amount);
    }
}
