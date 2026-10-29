pragma solidity ^0.4.24;

contract BidRoom {
    address public leader;
    uint256 public highestBid;

    function bid() public payable {
        require(msg.value > highestBid);
        require(leader.send(highestBid));
        leader = msg.sender;
        highestBid = msg.value;
    }

    function version() public pure returns (uint256) {
        return 2;
    }
}
