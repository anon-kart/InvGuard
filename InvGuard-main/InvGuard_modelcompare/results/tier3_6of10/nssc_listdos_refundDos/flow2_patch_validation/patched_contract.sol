// SPDX-License-Identifier: UNLICENSED
// Real-world pattern: unbounded-loop refund DoS (NSSC).
pragma solidity ^0.8.19;

contract CrowdFundBad {
    address[] public refundAddresses;
    mapping(address => uint) public refundAmount;

    function join() public payable {
        refundAddresses.push(msg.sender);
        refundAmount[msg.sender] += msg.value;
    }

    // Fixed: converted to a pull-payment pattern
    function refundDos() public {
        uint amount = refundAmount[msg.sender];
        require(amount > 0, "No funds to withdraw");
        refundAmount[msg.sender] = 0; // Update state before external call
        payable(msg.sender).transfer(amount);
    }

    receive() external payable {}
}