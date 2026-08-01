// SPDX-License-Identifier: UNLICENSED
// Real-world pattern: push-payment auction DoS (NSSC).
pragma solidity ^0.8.19;

contract DosAuction {
    address public currentFrontrunner;
    uint public currentBid;
    mapping(address => uint) public refunds;

    // BUG: refund pushed to previous bidder; a bidder whose fallback reverts
    // permanently blocks all higher bids (griefing / locked auction).
    function bid() public payable {
        require(msg.value > currentBid, "bid too low");
        if (currentFrontrunner != address(0)) {
            refunds[currentFrontrunner] += currentBid;
        }
        currentFrontrunner = msg.sender;
        currentBid = msg.value;
    }

    function withdraw() public {
        uint amount = refunds[msg.sender];
        require(amount > 0, "no funds to withdraw");
        refunds[msg.sender] = 0;
        require(payable(msg.sender).send(amount), "withdrawal failed");
    }

    receive() external payable {}
}