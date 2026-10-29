pragma solidity ^0.8.20;

contract VestingLock {
    address public beneficiary;
    uint256 public unlockAt;

    constructor(address b) payable {
        beneficiary = b;
        unlockAt = block.timestamp + 30 days;
    }

    function release() external {
        require(block.timestamp >= unlockAt, "locked");
        payable(beneficiary).transfer(address(this).balance);
    }
}
