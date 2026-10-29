pragma solidity ^0.8.20;

contract FeeSplitter {
    address public treasury;
    uint256 public constant FEE_BPS = 250;
    mapping(address => uint256) public balances;

    constructor(address t) {
        treasury = t;
    }

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "balance");
        uint256 fee = amount * FEE_BPS / 1000;
        balances[msg.sender] -= amount;
        balances[treasury] += fee;
        payable(msg.sender).transfer(amount - fee);
    }
}
