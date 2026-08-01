// SPDX-License-Identifier: UNLICENSED
// Real-world: King of the Ether Throne — unchecked send / DoS (NSSC).
pragma solidity ^0.8.19;

contract KingOfTheEtherThrone {
    address public king;
    uint public claimPrice = 100;
    address payable public owner;

    constructor() { owner = payable(msg.sender); king = msg.sender; }

    function sweepCommission(uint amount) public {
        require(msg.sender == owner, "not owner");
        owner.transfer(amount);
    }

    // BUG: refund to previous king via unchecked send; if king is a contract
    // that rejects ETH, throne payout silently fails (funds misdirected/stuck).
    function claimThrone() public payable {
        require(msg.value >= claimPrice, "underpaid");
        uint compensation = (msg.value * 50) / 100;
        // unchecked: return value of send ignored (the original bug)
        payable(king).send(compensation);
        king = msg.sender;
        claimPrice = (msg.value * 150) / 100;
    }

    receive() external payable {}
}
