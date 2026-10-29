pragma solidity ^0.4.24;

contract PrizeDesk {
    mapping(address => uint256) public winnings;
    mapping(address => bool) public paid;

    function credit(address w) public payable {
        winnings[w] += msg.value;
    }

    function _pay(address to, uint256 amount) internal {
        require(to.send(amount));
    }

    function payout() public {
        require(!paid[msg.sender]);
        uint256 amount = winnings[msg.sender];
        paid[msg.sender] = true;
        winnings[msg.sender] = 0;
        _pay(msg.sender, amount);
    }
}
