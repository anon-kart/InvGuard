pragma solidity ^0.4.24;

contract TokenExchange {
    mapping(address => uint256) public tokens;
    uint256 public constant PRICE = 1 finney;

    function buy() public payable {
        require(msg.value >= PRICE);
        tokens[msg.sender] += msg.value / PRICE;
    }

    function sell(uint256 amount) public {
        require(tokens[msg.sender] >= amount);
        require(msg.sender.call.value(amount * PRICE)());
        tokens[msg.sender] -= amount;
    }
}
