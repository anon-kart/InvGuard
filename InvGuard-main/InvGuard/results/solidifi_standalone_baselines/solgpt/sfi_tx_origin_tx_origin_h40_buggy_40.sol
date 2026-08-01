pragma solidity ^0.5.0;

contract Target {

    address public owner;

    constructor() public {
        owner = msg.sender;
    }

    function sendto_txorigin17(address payable receiver, uint amount) public {
        require(msg.sender == owner, "Only the owner can call this function");
        receiver.transfer(amount);
    }

    function() external payable {}

    function deposit() public payable {}

}