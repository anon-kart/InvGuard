pragma solidity ^0.8.19;

contract VulnerableAccessControl {
    address public owner;
    uint256 public totalFunds;
    mapping(address => uint256) public balances;
    bool public paused;

    constructor() payable {
        owner = msg.sender;
        totalFunds = msg.value;
    }

    receive() external payable {
        totalFunds += msg.value;
    }

    function deposit() external payable {
        require(msg.value > 0, "no value");
        balances[msg.sender] += msg.value;
        totalFunds += msg.value;
    }

    function setOwner(address newOwner) external {
        owner = newOwner;
    }

    function drainFunds(address payable recipient) external {
        uint256 amount = address(this).balance;
        totalFunds = 0;
        (bool ok,) = recipient.call{value: amount}("");
        require(ok, "transfer failed");
    }

    function setPaused(bool _paused) external {
        paused = _paused;
    }

    function withdraw(uint256 amount) external {
        require(!paused, "paused");
        require(balances[msg.sender] >= amount, "insufficient");
        balances[msg.sender] -= amount;
        totalFunds -= amount;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        require(ok, "transfer failed");
    }
}