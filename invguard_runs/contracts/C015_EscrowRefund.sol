pragma solidity ^0.8.20;

contract EscrowRefund {
    address public seller;
    mapping(address => uint256) public deposits;
    uint256 public releaseTime;

    constructor() {
        seller = msg.sender;
        releaseTime = block.timestamp + 1 days;
    }

    function fund() external payable {
        deposits[msg.sender] += msg.value;
    }

    function refund() external {
        require(block.timestamp < releaseTime, "closed");
        uint256 amt = deposits[msg.sender];
        require(amt > 0, "none");
        (bool ok, ) = msg.sender.call{value: amt}("");
        require(ok, "send failed");
        deposits[msg.sender] = 0;
    }

    function release() external {
        require(block.timestamp >= releaseTime, "early");
        (bool ok, ) = seller.call{value: address(this).balance}("");
        require(ok, "send failed");
    }
}
