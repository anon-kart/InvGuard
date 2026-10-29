pragma solidity ^0.4.24;

contract Auction {
    address public leader;
    uint256 public highestBid;

    function bid() public payable {
        require(msg.value > highestBid);
        require(leader.send(highestBid));
        leader = msg.sender;
        highestBid = msg.value;
    }
}
