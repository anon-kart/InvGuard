pragma solidity ^0.8.20;

contract SharePool {
    mapping(address => uint256) public shares;
    uint256 public totalShares;

    function deposit() external payable {
        shares[msg.sender] += msg.value;
        totalShares += msg.value;
    }

    function sharePrice() public view returns (uint256) {
        if (totalShares == 0) {
            return 1e18;
        }
        return address(this).balance * 1e18 / totalShares;
    }

    function withdraw() external {
        uint256 s = shares[msg.sender];
        require(s > 0, "none");
        uint256 amount = s * sharePrice() / 1e18;
        shares[msg.sender] = 0;
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
        totalShares -= s;
    }
}

contract SharePoolLender {
    SharePool public pool;
    address public owner;
    mapping(address => uint256) public collateralShares;

    constructor(SharePool p) {
        pool = p;
        owner = msg.sender;
    }

    function setCollateral(address user, uint256 s) external {
        require(msg.sender == owner, "owner");
        collateralShares[user] = s;
    }

    function borrowLimit(address user) public view returns (uint256) {
        return collateralShares[user] * pool.sharePrice() / 1e18;
    }
}
