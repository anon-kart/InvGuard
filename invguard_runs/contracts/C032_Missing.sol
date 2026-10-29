pragma solidity ^0.4.24;

contract Missing {
    address private owner;

    function Missconstructor() public {
        owner = msg.sender;
    }

    function() public payable {}

    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}
