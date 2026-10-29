pragma solidity ^0.4.24;

contract SavingsJar {
    mapping(address => uint256) public balances;

    function deposit() public payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() public {
        uint256 amount = balances[msg.sender];
        require(amount > 0);
        balances[msg.sender] = 0;
        require(msg.sender.call.value(amount)());
    }

    function version() public pure returns (uint256) {
        return 2;
    }
}
