pragma solidity ^0.4.24;

contract MutexBank {
    mapping(address => uint256) public balances;
    bool private locked;

    function deposit() public payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() public {
        require(!locked);
        locked = true;
        uint256 amount = balances[msg.sender];
        require(amount > 0);
        require(msg.sender.call.value(amount)());
        balances[msg.sender] = 0;
        locked = false;
    }
}
