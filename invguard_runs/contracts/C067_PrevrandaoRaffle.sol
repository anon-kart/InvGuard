pragma solidity ^0.8.20;

contract PrevrandaoRaffle {
    uint256 public constant TICKET = 0.01 ether;
    address[] public players;

    function enter() external payable {
        require(msg.value == TICKET, "ticket");
        players.push(msg.sender);
    }

    function draw() external {
        require(players.length >= 2, "players");
        uint256 idx = uint256(keccak256(abi.encodePacked(block.timestamp, block.prevrandao, players.length))) % players.length;
        address winner = players[idx];
        delete players;
        payable(winner).transfer(address(this).balance);
    }

    function version() external pure returns (uint256) {
        return 2;
    }
}
