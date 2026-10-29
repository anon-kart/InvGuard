pragma solidity ^0.8.20;

contract SpotLenderPair {
    uint256 public reserveToken = 1000 ether;
    uint256 public reserveEth = 1000 ether;

    function swapEthForToken() external payable returns (uint256 out) {
        out = reserveToken * msg.value / (reserveEth + msg.value);
        reserveEth += msg.value;
        reserveToken -= out;
    }

    function spotPrice() external view returns (uint256) {
        return reserveEth * 1e18 / reserveToken;
    }
}

contract SpotLender {
    SpotLenderPair public pair;
    address public owner;
    mapping(address => uint256) public collateralTokens;
    mapping(address => uint256) public debt;

    constructor(SpotLenderPair p) payable {
        pair = p;
        owner = msg.sender;
    }

    function setCollateral(address user, uint256 amount) external {
        require(msg.sender == owner, "owner");
        collateralTokens[user] = amount;
    }

    function borrow(uint256 ethAmount) external {
        uint256 value = collateralTokens[msg.sender] * pair.spotPrice() / 1e18;
        require(debt[msg.sender] + ethAmount <= value / 2, "undercollateralized");
        debt[msg.sender] += ethAmount;
        payable(msg.sender).transfer(ethAmount);
    }
}
