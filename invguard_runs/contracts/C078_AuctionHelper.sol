pragma solidity ^0.4.24;

contract AuctionHelper {
    address public leader;
    uint256 public highestBid;
    uint256 public bidCount;

    function _refundLeader() internal {
        if (leader != address(0)) {
            require(leader.send(highestBid));
        }
    }

    function bid() public payable {
        require(msg.value > highestBid);
        _refundLeader();
        leader = msg.sender;
        highestBid = msg.value;
        bidCount += 1;
    }
}
