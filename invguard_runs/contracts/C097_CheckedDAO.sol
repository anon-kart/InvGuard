pragma solidity ^0.8.20;

contract CheckedDAO {
    mapping(address => uint256) public credit;

    function donate(address to) external payable {
        credit[to] += msg.value;
    }

    function withdraw(uint256 amount) external {
        if (credit[msg.sender] >= amount) {
            (bool ok, ) = msg.sender.call{value: amount}("");
            require(ok, "send failed");
            credit[msg.sender] -= amount;
        }
    }
}
