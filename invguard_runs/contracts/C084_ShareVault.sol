pragma solidity ^0.8.20;

contract ShareVault {
    mapping(address => uint256) public shares;
    uint256 public totalShares;

    function deposit() external payable {
        uint256 assetsBefore = address(this).balance - msg.value;
        uint256 minted = totalShares == 0 ? msg.value : msg.value * totalShares / assetsBefore;
        shares[msg.sender] += minted;
        totalShares += minted;
    }

    function redeem(uint256 s) external {
        uint256 assets = s * address(this).balance / totalShares;
        shares[msg.sender] -= s;
        totalShares -= s;
        payable(msg.sender).transfer(assets);
    }
}
