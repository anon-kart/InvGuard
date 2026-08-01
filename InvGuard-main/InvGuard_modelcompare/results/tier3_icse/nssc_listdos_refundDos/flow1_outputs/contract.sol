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

    // BUG: loops over an unbounded array and pushes payments; one reverting
    // payee (or a large list) bricks the whole refund.
    function refundDos() public {
        for (uint i = 0; i < refundAddresses.length; i++) {
            payable(refundAddresses[i]).transfer(refundAmount[refundAddresses[i]]);
        }
    }

    receive() external payable {}
}
