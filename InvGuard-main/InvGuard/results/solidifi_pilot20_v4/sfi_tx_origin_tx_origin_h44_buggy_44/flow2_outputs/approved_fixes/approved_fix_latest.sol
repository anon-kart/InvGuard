pragma solidity ^0.5.0;

contract Target {

    address public owner;

    constructor() public payable {
        owner = msg.sender;
    }

    function withdrawAll_txorigin10(address payable _recipient) public {
            require(msg.sender == owner);
            _recipient.transfer(address(this).balance);
        }

    function() external payable {}

    function deposit() public payable {}

}