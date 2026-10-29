pragma solidity ^0.8.20;

contract HelperToken {
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    constructor() {
        balanceOf[msg.sender] = 1000000;
    }

    function approve(address s, uint256 a) external returns (bool) {
        allowance[msg.sender][s] = a;
        return true;
    }

    function transferFrom(address from, address to, uint256 a) external returns (bool) {
        require(allowance[from][msg.sender] >= a, "allowance");
        allowance[from][msg.sender] -= a;
        _doMove(from, to, a);
        return true;
    }

    function _move(address from, address to, uint256 a) public {
        require(msg.sender == from, "not holder");
        _doMove(from, to, a);
    }

    function _doMove(address from, address to, uint256 a) internal {
        require(balanceOf[from] >= a, "balance");
        balanceOf[from] -= a;
        balanceOf[to] += a;
    }
}
