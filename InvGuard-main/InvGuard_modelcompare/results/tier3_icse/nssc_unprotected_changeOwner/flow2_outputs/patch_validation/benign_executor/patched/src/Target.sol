// SPDX-License-Identifier: UNLICENSED
// Real-world pattern: unprotected ownership change (Trail of Bits NSSC)
pragma solidity ^0.8.19;

contract Unprotected {
    address public owner;
    mapping(address => uint) public balances;

    constructor() payable { owner = msg.sender; }

    function deposit() public payable { balances[msg.sender] += msg.value; }

    // BUG: missing access control — anyone can seize ownership
    function changeOwner(address _newOwner) public {
        require(msg.sender == owner, "not owner");
        owner = _newOwner;
    }

    // Owner can sweep the contract (becomes exploitable once owner is hijacked)
    function withdrawAll() public {
        require(msg.sender == owner, "not owner");
        payable(owner).transfer(address(this).balance);
    }

    receive() external payable {}
}


// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `Unprotected` has a no-arg constructor (or implicit constructor).
contract Target is Unprotected {
    constructor() Unprotected() {}
}
