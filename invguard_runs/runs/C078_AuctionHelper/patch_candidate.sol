pragma solidity ^0.4.24;

contract AuctionHelper {
    address public leader;
    uint256 public highestBid;
    uint256 public bidCount;
    mapping(address => uint256) public refunds;

    function _refundLeader() internal {
        if (leader != address(0)) {
            refunds[leader] += highestBid;
        }
    }

    function bid() public payable {
        require(msg.value > highestBid);
        _refundLeader();
        leader = msg.sender;
        highestBid = msg.value;
        bidCount += 1;
    }

    function withdrawRefund() public {
        uint256 amount = refunds[msg.sender];
        refunds[msg.sender] = 0;
        require(msg.sender.send(amount));
    }
}
