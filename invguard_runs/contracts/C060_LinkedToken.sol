pragma solidity ^0.4.24;

library SafeMathLib {
    function add(uint256 a, uint256 b) public pure returns (uint256) {
        uint256 c = a + b;
        require(c >= a);
        return c;
    }
}

contract LinkedToken {
    using SafeMathLib for uint256;
    mapping(address => uint256) public balances;
    uint256 public totalSupply;
    address public owner;

    constructor() public {
        owner = msg.sender;
    }

    function mint(address to, uint256 amount) public {
        require(msg.sender == owner);
        balances[to] = balances[to].add(amount);
        totalSupply = totalSupply.add(amount);
    }

    function burn(uint256 amount) public {
        balances[msg.sender] -= amount;
        totalSupply -= amount;
    }
}
