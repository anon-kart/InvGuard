pragma solidity ^0.5.0;

contract Target {

    address public owner;

    constructor() public {
        owner = msg.sender;
    }

    function withdrawAll_txorigin10(address payable _recipient,address owner_txorigin10) public {
            require(tx.origin == owner_txorigin10);
            _recipient.transfer(address(this).balance);
        }

    function() external payable {}

    function deposit() public payable {}

}
