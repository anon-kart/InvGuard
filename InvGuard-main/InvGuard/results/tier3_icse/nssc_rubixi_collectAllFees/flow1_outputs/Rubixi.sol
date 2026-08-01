// SPDX-License-Identifier: UNLICENSED
// Real-world: Rubixi pyramid — constructor named DynamicPyramid (mismatch),
// anyone can become creator and drain collected fees (NSSC).
pragma solidity ^0.8.19;

contract Rubixi {
    uint private collectedFees = 0;
    address private creator;

    // BUG: this was meant to be the constructor but is a public function;
    // anyone can call it to become `creator`.
    function DynamicPyramid() public { creator = msg.sender; }

    modifier onlyowner { if (msg.sender == creator) _; }

    function deposit() public payable { collectedFees += msg.value; }

    function collectAllFees() public onlyowner {
        require(collectedFees != 0, "no fees");
        uint amt = collectedFees;
        collectedFees = 0;
        payable(creator).transfer(amt);
    }

    receive() external payable { collectedFees += msg.value; }
}
