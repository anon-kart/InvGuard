pragma solidity ^0.5.11;

contract Target {

    address public owner;

    constructor() public {
        owner = msg.sender;
    }

    function withdrawAll(address payable _recipient) public {
            require(msg.sender == owner);
            _recipient.transfer(address(this).balance);
        }

    function() external payable {}

    function deposit() public payable {}

}