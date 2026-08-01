// SPDX-License-Identifier: MIT
pragma solidity ^0.7.6;

contract TokenSale {
    mapping(address => uint256) public balanceOf;
    mapping(address => uint256) public spent;
    uint256 public constant PRICE = 1 ether;
    uint256 public totalSupply;
    address public issuer;

    event Bought(address indexed who, uint256 numTokens);
    event Transferred(address indexed from, address indexed to, uint256 amount);

    constructor() {
        issuer = msg.sender;
    }

    function buy(uint256 numTokens) external payable {
        require(msg.value == numTokens * PRICE, "wrong value");
        balanceOf[msg.sender] += numTokens;
        spent[msg.sender] += msg.value;
        totalSupply += numTokens;
        emit Bought(msg.sender, numTokens);
    }

    function transfer(address to, uint256 amount) external {
        require(balanceOf[msg.sender] - amount >= 0, "underflow guard");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        emit Transferred(msg.sender, to, amount);
    }

    function tokensOf(address who) external view returns (uint256) {
        return balanceOf[who];
    }
}
