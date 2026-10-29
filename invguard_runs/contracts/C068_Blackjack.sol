pragma solidity ^0.4.24;

contract Blackjack {
    struct Game {
        uint256 bet;
        uint8 total;
        bool active;
    }

    mapping(address => Game) public games;

    constructor() public payable {}

    function card(uint256 salt) internal view returns (uint8) {
        return uint8(uint256(keccak256(abi.encodePacked(blockhash(block.number - 1), msg.sender, salt))) % 10) + 1;
    }

    function deal() public payable {
        require(!games[msg.sender].active && msg.value > 0 && msg.value <= 1 ether);
        games[msg.sender] = Game(msg.value, card(1) + card(2), true);
    }

    function hit() public {
        Game storage g = games[msg.sender];
        require(g.active);
        g.total += card(g.total);
        if (g.total > 21) {
            g.active = false;
        }
    }

    function stand() public {
        Game storage g = games[msg.sender];
        require(g.active);
        g.active = false;
        uint8 dealer = card(99) + 10;
        if (g.total <= 21 && g.total > dealer) {
            msg.sender.transfer(g.bet * 2);
        }
    }
}
