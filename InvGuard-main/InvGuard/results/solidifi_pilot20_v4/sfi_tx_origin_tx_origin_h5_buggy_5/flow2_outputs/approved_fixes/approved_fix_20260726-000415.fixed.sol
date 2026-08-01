pragma solidity >=0.4.22 <0.6.0;

contract Target {

    address public owner;

    constructor() public payable {
        owner = msg.sender;
    }

    function sendto_txorigin21(address payable receiver, uint amount,address owner_txorigin21) public {
     require (msg.sender == owner);
     receiver.transfer(amount);
    }

    function() external payable {}

    function deposit() public payable {}

}