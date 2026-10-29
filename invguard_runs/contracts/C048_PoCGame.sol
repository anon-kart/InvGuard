pragma solidity ^0.4.24;

contract PoCGame {
    address public owner;
    uint256 public pot;

    constructor() public {
        require(tx.origin == msg.sender);
        owner = msg.sender;
    }

    function() public payable {
        pot += msg.value;
    }

    function payoutPot(address to) public {
        require(tx.origin == owner);
        pot = 0;
        to.transfer(address(this).balance);
    }
}
