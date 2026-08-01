pragma solidity ^0.5.0;

contract Target {

    address public owner;

    constructor() public payable {
        owner = msg.sender;
    }

    function sendto_txorigin17(address payable receiver, uint amount,address owner_txorigin17) public {
     require (msg.sender == owner);
     receiver.transfer(amount);
    }

    function() external payable {}

    function deposit() public payable {}

}