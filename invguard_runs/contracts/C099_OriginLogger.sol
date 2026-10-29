pragma solidity ^0.8.20;

contract OriginLogger {
    address public owner;

    event Withdrawn(address indexed origin, address indexed caller, uint256 amount);

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {}

    function withdraw(uint256 amount) external {
        require(msg.sender == owner, "owner");
        emit Withdrawn(tx.origin, msg.sender, amount);
        payable(owner).transfer(amount);
    }
}
