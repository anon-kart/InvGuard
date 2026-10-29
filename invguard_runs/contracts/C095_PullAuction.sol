pragma solidity ^0.8.20;

contract PullAuction {
    address public leader;
    uint256 public highestBid;
    mapping(address => uint256) public refunds;

    function bid() external payable {
        require(msg.value > highestBid, "low");
        refunds[leader] += highestBid;
        leader = msg.sender;
        highestBid = msg.value;
    }

    function withdrawRefund() external {
        uint256 amount = refunds[msg.sender];
        refunds[msg.sender] = 0;
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
    }
}
