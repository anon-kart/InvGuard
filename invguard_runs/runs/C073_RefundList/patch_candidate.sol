pragma solidity ^0.4.24;

contract RefundList {
    address[] private refundAddresses;
    mapping(address => uint256) public refunds;

    function contribute() public payable {
        require(msg.value > 0);
        if (refunds[msg.sender] == 0) {
            refundAddresses.push(msg.sender);
        }
        refunds[msg.sender] += msg.value;
    }

    function refundAll() public {
        for (uint256 x = 0; x < refundAddresses.length; x++) {
            address r = refundAddresses[x];
            uint256 amount = refunds[r];
            refunds[r] = 0;
            r.send(amount);
        }
    }
}
