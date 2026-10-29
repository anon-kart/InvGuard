pragma solidity ^0.4.24;

contract SecretSeedLottery {
    uint256 private seed;
    uint256 public pot;

    struct Ticket {
        uint256 guess;
        uint256 blockNumber;
    }

    mapping(address => Ticket) public tickets;

    constructor(uint256 _seed) public payable {
        seed = _seed;
        pot = msg.value;
    }

    function play(uint256 guess) public payable {
        require(msg.value == 0.1 ether);
        require(tickets[msg.sender].blockNumber == 0);
        pot += msg.value;
        tickets[msg.sender] = Ticket(guess, block.number + 1);
    }

    function reveal() public {
        Ticket memory t = tickets[msg.sender];
        require(t.blockNumber != 0 && block.number > t.blockNumber);
        delete tickets[msg.sender];
        if (block.number - t.blockNumber > 255) {
            return;
        }
        if (t.guess == uint256(keccak256(abi.encodePacked(blockhash(t.blockNumber), msg.sender))) % 100) {
            uint256 prize = pot;
            pot = 0;
            msg.sender.transfer(prize);
        }
    }
}
