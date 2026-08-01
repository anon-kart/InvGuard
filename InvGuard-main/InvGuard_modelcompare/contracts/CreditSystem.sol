// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract CreditSystem {
    mapping(address => uint256) public credits;
    mapping(address => uint256) public spent;
    uint256 public totalCredits;
    address public issuer;

    constructor() {
        issuer = msg.sender;
    }

    function deposit() external payable {
        require(msg.value > 0, "no value");
        unchecked {
            credits[msg.sender] += msg.value;
            totalCredits += msg.value;
        }
    }

    function issueCredit(uint256 amount) external {
        unchecked {
            credits[msg.sender] += amount;
            totalCredits += amount;
        }
    }

    function spend(uint256 amount) external {
        require(credits[msg.sender] >= amount, "insufficient");
        unchecked {
            credits[msg.sender] -= amount;
            spent[msg.sender] += amount;
            totalCredits -= amount;
        }
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        require(ok, "failed");
    }
}
