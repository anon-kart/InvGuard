pragma solidity ^0.8.20;

contract CreditDesk {
    mapping(address => uint256) public credits;

    function deposit() external payable {
        credits[msg.sender] += msg.value;
    }

    function cashOut(uint256 amount) external {
        require(credits[msg.sender] >= amount, "insufficient");
        credits[msg.sender] -= amount;
        msg.sender.call{value: amount}("");
    }
}
