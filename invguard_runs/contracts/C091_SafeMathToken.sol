pragma solidity ^0.4.24;

library SafeMath {
    function sub(uint256 a, uint256 b) internal pure returns (uint256) {
        require(b <= a);
        return a - b;
    }

    function add(uint256 a, uint256 b) internal pure returns (uint256) {
        uint256 c = a + b;
        require(c >= a);
        return c;
    }
}

contract SafeMathToken {
    using SafeMath for uint256;
    mapping(address => uint256) public balanceOf;

    constructor(uint256 supply) public {
        balanceOf[msg.sender] = supply;
    }

    function transfer(address to, uint256 value) public returns (bool) {
        balanceOf[msg.sender] = balanceOf[msg.sender].sub(value);
        balanceOf[to] = balanceOf[to].add(value);
        return true;
    }
}
