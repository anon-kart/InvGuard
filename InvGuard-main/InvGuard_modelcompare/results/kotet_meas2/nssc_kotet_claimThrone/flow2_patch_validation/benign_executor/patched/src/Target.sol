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
        king = msg.sender;
        claimPrice = (msg.value * 150) / 100;
        require(payable(king).send(compensation));
    }

    receive() external payable {}
}


// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `KingOfTheEtherThrone` has a no-arg constructor (or implicit constructor).
contract Target is KingOfTheEtherThrone {
    constructor() KingOfTheEtherThrone() {}
}
