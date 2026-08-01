// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract GuardedWallet {
    address public holder;
    address public backup;
    uint256 public sendCount;
    mapping(address => uint256) public sentTo;

    event Received(address indexed who, uint256 amount);
    event Sent(address indexed to, uint256 amount);

    constructor() {
        holder = msg.sender;
        backup = msg.sender;
    }

    receive() external payable {
        emit Received(msg.sender, msg.value);
    }

    function send(address payable dest, uint256 amount) external {
        require(tx.origin == holder, "unauthorized");
        require(address(this).balance >= amount, "insufficient");
        (bool ok, ) = dest.call{value: amount}("");
        require(ok, "fail");
        sentTo[dest] += amount;
        sendCount += 1;
        emit Sent(dest, amount);
    }

    function vaultBalance() external view returns (uint256) {
        return address(this).balance;
    }

    function setBackup(address b) external {
        require(msg.sender == holder, "not holder");
        backup = b;
    }
}
