pragma solidity ^0.4.24;

contract WalletLibrary {
    address public owner;
    uint256 public dailyLimit;
    bool public initialized;

    function initWallet(address _owner, uint256 _limit) public {
        require(!initialized);
        initialized = true;
        owner = _owner;
        dailyLimit = _limit;
    }

    function() public payable {}

    function execute(address to, uint256 value) public {
        require(msg.sender == owner);
        require(value <= dailyLimit);
        to.transfer(value);
    }
}
