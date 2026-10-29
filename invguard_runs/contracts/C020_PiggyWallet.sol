pragma solidity ^0.4.24;

contract PiggyWallet {
    mapping(address => uint256) public balances;

    function deposit() public payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount);
        balances[msg.sender] -= amount;
        msg.sender.call.value(amount)();
    }

    function version() public pure returns (uint256) {
        return 2;
    }
}
