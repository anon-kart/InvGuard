pragma solidity ^0.8.20;

contract Payroll {
    address public owner;
    address payable[] public staff;
    mapping(address => uint256) public salary;

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {}

    function hire(address payable who, uint256 amount) external {
        require(msg.sender == owner, "owner");
        staff.push(who);
        salary[who] = amount;
    }

    function payAll() external {
        for (uint256 i = 0; i < staff.length; i++) {
            staff[i].transfer(salary[staff[i]]);
        }
    }
}
