pragma solidity ^0.4.24;

contract OverflowToken {
    mapping(address => uint256) public balanceOf;
    uint256 public totalSupply;

    constructor(uint256 supply) public {
        balanceOf[msg.sender] = supply;
        totalSupply = supply;
    }

    function transfer(address to, uint256 value) public returns (bool) {
        require(balanceOf[msg.sender] - value >= 0);
        balanceOf[msg.sender] -= value;
        balanceOf[to] += value;
        return true;
    }
}
