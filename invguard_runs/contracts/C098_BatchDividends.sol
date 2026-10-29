pragma solidity ^0.8.20;

contract BatchDividends {
    address[] public holders;
    mapping(address => bool) public joined;
    mapping(address => uint256) public credit;
    uint256 public pendingShare;
    uint256 public cursor;

    function join() external {
        require(!joined[msg.sender], "joined");
        joined[msg.sender] = true;
        holders.push(msg.sender);
    }

    function fund() external payable {
        require(holders.length > 0 && cursor == 0, "busy");
        pendingShare = msg.value / holders.length;
    }

    function distributeBatch(uint256 n) external {
        uint256 end = cursor + n;
        if (end > holders.length) {
            end = holders.length;
        }
        for (uint256 i = cursor; i < end; i++) {
            credit[holders[i]] += pendingShare;
        }
        cursor = end == holders.length ? 0 : end;
    }
}
