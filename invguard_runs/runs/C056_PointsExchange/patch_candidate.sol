pragma solidity ^0.8.20;

contract PointsExchange {
    mapping(address => uint256) public points;
    mapping(address => uint256) public redeemed;
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function award(address to, uint256 amount) external {
        require(msg.sender == owner, "owner");
        points[to] += amount;
    }

    function redeem(uint256 amount) external {
        require(points[msg.sender] >= amount, "points");
        unchecked {
            points[msg.sender] -= amount;
        }
        redeemed[msg.sender] += amount;
    }

    function transferPoints(address to, uint256 amount) external {
        unchecked {
            points[msg.sender] -= amount;
            points[to] += amount;
        }
    }
}
