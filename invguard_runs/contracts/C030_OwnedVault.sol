pragma solidity ^0.4.24;

contract OwnedVault {
    address public owner;

    constructor() public {
        owner = msg.sender;
    }

    function() public payable {}

    function changeOwner(address newOwner) public {
        owner = newOwner;
    }

    function withdraw() public {
        require(msg.sender == owner);
        msg.sender.transfer(address(this).balance);
    }

    function version() public pure returns (uint256) {
        return 2;
    }
}
