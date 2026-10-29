pragma solidity ^0.8.20;

contract UncheckedVault {
    mapping(address => uint256) public balance;

    function deposit() external payable {
        balance[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(balance[msg.sender] >= amount, "balance");
        unchecked {
            balance[msg.sender] -= amount;
        }
        require(address(this).balance >= amount, "liquidity");
        payable(msg.sender).transfer(amount);
    }
}
