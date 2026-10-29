pragma solidity ^0.4.24;

contract ShortAddressCoin {
    mapping(address => uint256) public balances;

    constructor() public {
        balances[msg.sender] = 10000;
    }

    function sendCoin(address to, uint256 amount) public returns (bool) {
        if (balances[msg.sender] < amount) {
            return false;
        }
        balances[msg.sender] -= amount;
        balances[to] += amount;
        return true;
    }
}
