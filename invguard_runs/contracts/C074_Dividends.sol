pragma solidity ^0.8.20;

contract Dividends {
    address[] public holders;
    mapping(address => uint256) public credit;

    function join() external {
        holders.push(msg.sender);
    }

    function distribute() external payable {
        require(holders.length > 0, "none");
        uint256 share = msg.value / holders.length;
        for (uint256 i = 0; i < holders.length; i++) {
            credit[holders[i]] += share;
        }
    }

    function withdraw() external {
        uint256 c = credit[msg.sender];
        credit[msg.sender] = 0;
        payable(msg.sender).transfer(c);
    }
}
