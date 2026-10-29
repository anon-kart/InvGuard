pragma solidity ^0.4.24;

contract Missing {
    address private owner;

    constructor() public {
        owner = msg.sender;
    }

    function Missconstructor() public {
        require(msg.sender == owner);
        owner = msg.sender;
    }

    function() public payable {}

    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}
