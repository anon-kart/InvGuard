pragma solidity ^0.8.20;

contract TwoStepOwnable {
    address public owner;
    address public pendingOwner;

    constructor() {
        owner = msg.sender;
    }

    function proposeOwner(address p) external {
        require(msg.sender == owner, "owner");
        pendingOwner = p;
    }

    function acceptOwnership() external {
        require(msg.sender == pendingOwner, "pending");
        owner = pendingOwner;
        pendingOwner = address(0);
    }
}
