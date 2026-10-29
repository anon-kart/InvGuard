pragma solidity ^0.8.20;

contract RebateBox {
    mapping(address => uint256) public credits;

    function deposit() external payable {
        credits[msg.sender] += msg.value;
    }

    function cashOut(uint256 amount) external {
        require(credits[msg.sender] >= amount, "insufficient");
        credits[msg.sender] -= amount;
        msg.sender.call{value: amount}("");
    }

    function version() external pure returns (uint256) {
        return 2;
    }
}
