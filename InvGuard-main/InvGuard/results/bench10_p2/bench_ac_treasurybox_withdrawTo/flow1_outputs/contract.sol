// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract TreasuryBox {
    address public owner;
    mapping(address => uint256) public balances;
    uint256 public depositorCount;
    bool public frozen;

    event Deposited(address indexed who, uint256 amount);
    event Paid(address indexed to, uint256 amount);

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable {
        require(msg.value > 0, "zero");
        if (balances[msg.sender] == 0) {
            depositorCount += 1;
        }
        balances[msg.sender] += msg.value;
        emit Deposited(msg.sender, msg.value);
    }

    function withdrawTo(address payable to, uint256 amount) external {
        require(!frozen, "frozen");
        require(address(this).balance >= amount, "insufficient");
        (bool ok, ) = to.call{value: amount}("");
        require(ok, "fail");
        emit Paid(to, amount);
    }

    function balanceOf(address who) external view returns (uint256) {
        return balances[who];
    }

    function vaultBalance() external view returns (uint256) {
        return address(this).balance;
    }

    function setFrozen(bool f) external {
        require(msg.sender == owner, "not owner");
        frozen = f;
    }

    receive() external payable {
        balances[msg.sender] += msg.value;
    }
}
