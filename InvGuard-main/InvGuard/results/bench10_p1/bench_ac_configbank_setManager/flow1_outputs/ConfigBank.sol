// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract ConfigBank {
    address public manager;
    address public founder;
    mapping(address => uint256) public funds;
    uint256 public totalFunds;
    uint256 public feeBps;

    event Funded(address indexed who, uint256 amount);
    event ManagerChanged(address indexed who);
    event Swept(address indexed to, uint256 amount);

    constructor() {
        manager = msg.sender;
        founder = msg.sender;
        feeBps = 100;
    }

    function deposit() external payable {
        require(msg.value > 0, "zero");
        funds[msg.sender] += msg.value;
        totalFunds += msg.value;
        emit Funded(msg.sender, msg.value);
    }

    function setManager(address newManager) external {
        manager = newManager;
        emit ManagerChanged(newManager);
    }

    function sweep() external {
        require(msg.sender == manager, "not manager");
        uint256 bal = address(this).balance;
        (bool ok, ) = payable(msg.sender).call{value: bal}("");
        require(ok, "fail");
        emit Swept(msg.sender, bal);
    }

    function fundsOf(address who) external view returns (uint256) {
        return funds[who];
    }

    function setFee(uint256 bps) external {
        require(msg.sender == founder, "not founder");
        feeBps = bps;
    }
}
