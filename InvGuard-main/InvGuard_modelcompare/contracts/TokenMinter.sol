// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract TokenMinter {
    mapping(address => uint256) public balances;
    uint256 public totalSupply;
    address public admin;
    bool public mintingEnabled = true;

    constructor() {
        admin = msg.sender;
    }

    function deposit() external payable {
        require(msg.value > 0, "no value");
        balances[msg.sender] += msg.value;
        totalSupply += msg.value;
    }

    function mintTokens(address to, uint256 amount) external {
        require(mintingEnabled, "disabled");
        balances[to] += amount;
        totalSupply += amount;
    }

    function setAdmin(address newAdmin) external {
        admin = newAdmin;
    }

    function disableMinting() external {
        mintingEnabled = false;
    }

    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "insufficient");
        balances[msg.sender] -= amount;
        totalSupply -= amount;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        require(ok, "transfer failed");
    }
}
