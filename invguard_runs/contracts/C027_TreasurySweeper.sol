pragma solidity ^0.4.24;

contract TreasurySweeper {
    address public owner;
    address public treasury;
    uint256 public swept;

    constructor(address t) public {
        owner = msg.sender;
        treasury = t;
    }

    function() public payable {}

    function sweep() public {
        require(msg.sender == owner);
        uint256 amount = address(this).balance;
        swept += amount;
        treasury.call.value(amount)();
    }
}
