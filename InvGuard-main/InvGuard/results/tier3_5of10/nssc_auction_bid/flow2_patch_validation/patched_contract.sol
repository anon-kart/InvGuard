// SPDX-License-Identifier: UNLICENSED
// Real-world pattern: push-payment auction DoS (NSSC).
pragma solidity ^0.8.19;

contract DosAuction {
    address public currentFrontrunner;
    uint public currentBid;

    // BUG: refund pushed to previous bidder; a bidder whose fallback reverts
    // permanently blocks all higher bids (griefing / locked auction).
    function bid() public payable {
        require(msg.value > currentBid, "bid too low");
        if (currentFrontrunner != address(0)) {
            require(payable(currentFrontrunner).send(currentBid), "refund failed");
        }
        currentFrontrunner = msg.sender;
        currentBid = msg.value;
    }

    receive() external payable {}
}