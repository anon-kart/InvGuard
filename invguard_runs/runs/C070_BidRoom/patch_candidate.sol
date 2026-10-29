pragma solidity ^0.4.24;

contract BidRoom {
    address public leader;
    uint256 public highestBid;
    mapping(address => uint256) public refunds;

    function bid() public payable {
        require(msg.value > highestBid);
        refunds[leader] += highestBid;
        leader = msg.sender;
        highestBid = msg.value;
    }

    function withdrawRefund() public {
        uint256 amount = refunds[msg.sender];
        refunds[msg.sender] = 0;
        require(msg.sender.send(amount));
    }

    function version() public pure returns (uint256) {
        return 2;
    }
}
