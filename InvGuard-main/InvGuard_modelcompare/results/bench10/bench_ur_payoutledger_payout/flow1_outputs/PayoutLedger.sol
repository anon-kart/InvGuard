// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract PayoutLedger {
    mapping(address => uint256) public owed;
    mapping(address => uint256) public paidTotal;
    uint256 public totalOwed;
    address public controller;
    bool public active;

    event Funded(address indexed who, uint256 amount);
    event PaidOut(address indexed who, uint256 amount);

    constructor() {
        controller = msg.sender;
        active = true;
    }

    function fund(address who) external payable {
        require(active, "inactive");
        require(msg.value > 0, "zero");
        owed[who] += msg.value;
        totalOwed += msg.value;
        emit Funded(who, msg.value);
    }

    function payout(address payable who) external {
        uint256 amount = owed[who];
        require(amount > 0, "nothing owed");
        owed[who] = 0;
        totalOwed -= amount;
        bool ok = who.send(amount);
        if (ok) {
            paidTotal[who] += amount;
        }
        emit PaidOut(who, amount);
    }

    function balanceOf(address who) external view returns (uint256) {
        return owed[who];
    }

    function setActive(bool a) external {
        require(msg.sender == controller, "not controller");
        active = a;
    }
}
