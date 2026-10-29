pragma solidity ^0.4.24;

contract PhishableWallet {
    address public owner;

    constructor() public {
        owner = msg.sender;
    }

    function() public payable {}

    function transferTo(address dest, uint256 amount) public {
        require(msg.sender == owner);
        dest.transfer(amount);
    }

    function version() public pure returns (uint256) {
        return 2;
    }
}
