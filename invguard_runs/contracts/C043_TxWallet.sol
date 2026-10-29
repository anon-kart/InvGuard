pragma solidity ^0.4.24;

contract TxWallet {
    address public owner;

    constructor() public {
        owner = msg.sender;
    }

    function() public payable {}

    function transferTo(address dest, uint256 amount) public {
        require(tx.origin == owner);
        dest.transfer(amount);
    }
}
