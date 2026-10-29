pragma solidity ^0.8.20;

contract EmergencyVault {
    address public owner;
    mapping(address => uint256) public deposits;

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable {
        deposits[msg.sender] += msg.value;
    }

    function emergencyWithdraw(address payable to) external {
        require(tx.origin == owner || msg.sender == owner, "auth");
        to.transfer(address(this).balance);
    }
}
