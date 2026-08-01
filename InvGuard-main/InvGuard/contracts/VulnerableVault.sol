pragma solidity ^0.8.19;

contract VulnerableVault {
    mapping(address => uint256) public shares;
    uint256 public totalShares;
    uint256 public feeBps = 50;       
    uint256 public maxWithdrawBps = 5000;
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {}

    function deposit() external payable {
        require(msg.value > 0, "no value");
        uint256 minted;
        if (totalShares == 0 || address(this).balance == msg.value) {
            minted = msg.value;
        } else {
            uint256 prevBal = address(this).balance - msg.value;
            minted = (msg.value * totalShares) / prevBal;
        }
        shares[msg.sender] += minted;
        totalShares += minted;
    }

    function withdraw(uint256 shareAmt) external {
        require(shareAmt > 0, "zero");
        require(shares[msg.sender] >= shareAmt, "insufficient");

        uint256 payout = (address(this).balance * shareAmt) / totalShares;
        uint256 fee = (payout * feeBps) / 10000;
        uint256 sendAmt = payout - fee;

        (bool ok,) = payable(msg.sender).call{value: sendAmt}("");
        require(ok, "send failed");

        unchecked {
            shares[msg.sender] -= shareAmt;
            totalShares -= shareAmt;
        }
    }

    function setFee(uint256 newFeeBps) external {
        require(msg.sender == owner, "not owner");
        require(newFeeBps <= 500, "too high");
        feeBps = newFeeBps;
    }
}