// SPDX-License-Identifier: UNLICENSED
// Real-world: Parity multisig WalletLibrary ($150M frozen). Isolated core.
// Unprotected initWallet lets anyone re-initialize ownership, then kill/drain (NSSC).
pragma solidity ^0.8.19;

contract WalletLibrary {
    address[] public m_owners;
    uint public m_required;
    bool initialized;

    address public owner;

    constructor() {
        owner = msg.sender; // Set the owner to the contract creator
    }

    // BUG: no guard — anyone can (re)initialize and seize ownership.
    function initWallet(address[] memory _owners, uint _required) public {
        require(msg.sender == owner, "not authorized"); // Access control check
        m_owners = _owners;
        m_required = _required;
        initialized = true;
    }

    function deposit() public payable {}

    function isOwner(address a) public view returns (bool) {
        for (uint i = 0; i < m_owners.length; i++) if (m_owners[i] == a) return true;
        return false;
    }

    // Drain restricted to "owners" — but ownership is hijackable via initWallet.
    function execute(address payable to, uint amount) public {
        require(isOwner(msg.sender), "not owner");
        to.transfer(amount);
    }

    // BUG: unprotected self-destruct (the actual Parity freeze trigger).
    function kill(address payable to) public {
        require(isOwner(msg.sender), "not owner");
        selfdestruct(to);
    }

    receive() external payable {}
}


// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `WalletLibrary` has a no-arg constructor (or implicit constructor).
contract Target is WalletLibrary {
    constructor() WalletLibrary() {}
}
