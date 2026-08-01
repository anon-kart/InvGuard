// SPDX-License-Identifier: UNLICENSED
// Real-world pattern: constructor-name mismatch (Rubixi/Missing class, NSSC)
pragma solidity ^0.8.19;

contract Missing {
    address private owner;
    mapping(address => uint) public balances;

    // BUG: intended as constructor but name != contract name in original 0.4;
    // here we preserve the bug as a PUBLIC initializer anyone can call.
    function IamMissing() public { owner = msg.sender; }

    function deposit() public payable { balances[msg.sender] += msg.value; }

    function withdraw() public {
        require(msg.sender == owner, "not owner");
        payable(owner).transfer(address(this).balance);
    }

    receive() external payable {}
}


// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `Missing` has a no-arg constructor (or implicit constructor).
contract Target is Missing {
    constructor() Missing() {}
}
