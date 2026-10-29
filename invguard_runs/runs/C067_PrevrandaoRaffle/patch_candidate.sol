pragma solidity ^0.8.20;

contract PrevrandaoRaffle {
    uint256 public constant TICKET = 0.01 ether;
    address[] public players;
    uint256 public drawBlock;

    function enter() external payable {
        require(drawBlock == 0, "drawing");
        require(msg.value == TICKET, "ticket");
        players.push(msg.sender);
    }

    function draw() external {
        require(players.length >= 2, "players");
        require(drawBlock == 0, "pending");
        drawBlock = block.number + 1;
    }

    function finalize() external {
        require(drawBlock != 0 && block.number > drawBlock, "wait");
        bytes32 h = blockhash(drawBlock);
        if (h == bytes32(0)) {
            drawBlock = block.number + 1;
            return;
        }
        uint256 idx = uint256(keccak256(abi.encodePacked(h, players.length))) % players.length;
        address winner = players[idx];
        delete players;
        drawBlock = 0;
        payable(winner).transfer(address(this).balance);
    }

    function version() external pure returns (uint256) {
        return 2;
    }
}
