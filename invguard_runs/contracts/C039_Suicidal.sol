pragma solidity ^0.4.24;

contract Suicidal {
    address public owner;

    constructor() public {
        owner = msg.sender;
    }

    function() public payable {}

    function kill() public {
        selfdestruct(msg.sender);
    }
}
