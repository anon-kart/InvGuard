// SPDX-License-Identifier: UNLICENSED
// Real-world pattern: unbounded-loop refund DoS (NSSC).
pragma solidity ^0.8.19;

contract CrowdFundBad {
    address[] public refundAddresses;
    mapping(address => uint) public refundAmount;
    mapping(address => bool) public hasWithdrawn;

    function join() public payable {
        refundAddresses.push(msg.sender);
        refundAmount[msg.sender] += msg.value;
    }

    // Fixed: converted to a pull-payment pattern
    function refundDos() public {
        require(!hasWithdrawn[msg.sender], "Already withdrawn");
        uint amount = refundAmount[msg.sender];
        require(amount > 0, "No funds to withdraw");
        hasWithdrawn[msg.sender] = true;
        refundAmount[msg.sender] = 0;
        payable(msg.sender).transfer(amount);
    }

    receive() external payable {}
}